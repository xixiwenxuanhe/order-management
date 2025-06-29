#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量更新订单脚本 - 获取所有大于latest_order_id的新订单
"""

import requests
import re

SERVER_URL = "http://localhost:8000"
API_BASE = f"{SERVER_URL}/api"

def get_database_status():
    """获取数据库状态信息"""
    response = requests.get(f"{API_BASE}/db-stats")
    return response.json()["data"]

def get_orders_with_target_from_api(auth_headers, target_order_id, last_id=None, limit=30):
    """调用获取订单列表API（带目标ID过滤）- 只保存ID大于target_order_id的订单"""
    payload = {
        "x_request_sign": auth_headers["x_request_sign"],
        "x_request_timestamp": auth_headers["x_request_timestamp"],
        "authorization": auth_headers["authorization"],
        "target_order_id": target_order_id,
        "limit": limit
    }
    
    if last_id:
        payload["last_id"] = last_id
    
    response = requests.post(f"{API_BASE}/get-orders-with-target", json=payload)
    return response

def main():
    print("=== 增量更新订单脚本 ===")
    
    # 获取数据库状态，找到latest_order_id
    print("获取数据库状态...")
    db_status = get_database_status()
    latest_order_id = db_status.get('latest_order_id')
    
    print(f"数据库状态:")
    print(f"- 总订单数: {db_status.get('total_orders', 0)}")
    print(f"- 总记录数: {db_status.get('total_records', 0)}")
    print(f"- 最新订单ID: {latest_order_id}")
    
    # 获取认证信息
    print("\n请输入认证信息:")
    authorization = input("Authorization: ").strip()
    x_request_sign = input("X-Request-Sign: ").strip()
    x_request_timestamp = input("X-Request-Timestamp: ").strip()
    
    auth_headers = {
        "authorization": authorization,
        "x_request_sign": x_request_sign,
        "x_request_timestamp": x_request_timestamp
    }
    
    # 开始增量更新
    print(f"\n开始获取所有大于 {latest_order_id} 的新订单...")
    
    last_id = None  # 从最新开始获取
    page = 1
    total_saved = 0
    total_processed = 0
    total_need_details = 0
    
    while True:
        print(f"\n=== 第 {page} 页请求 ===")
        
        # 调用带目标ID过滤的获取订单API
        response = get_orders_with_target_from_api(auth_headers, latest_order_id, last_id)
        
        # 检查是否签名失效
        if response.status_code == 401 or (response.status_code == 422 and "签名失效" in response.text):
            print("签名失效，请重新输入:")
            x_request_sign = input("X-Request-Sign: ").strip()
            x_request_timestamp = input("X-Request-Timestamp: ").strip()
            
            auth_headers.update({
                "x_request_sign": x_request_sign,
                "x_request_timestamp": x_request_timestamp
            })
            
            # 重新尝试当前页
            response = get_orders_with_target_from_api(auth_headers, latest_order_id, last_id)
        
        # 检查响应状态码
        if response.status_code != 200:
            print(f"请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            break
        
        # 尝试解析JSON
        try:
            result = response.json()
        except Exception as e:
            print(f"解析JSON失败: {e}")
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            break
        
        # 获取返回的数据信息
        current_count = result.get("total_orders", 0)
        current_last_id = result.get("last_id")
        message = result.get("message", "")
        
        # 从消息中提取保存的记录数和需要详细查看的订单数
        saved_count = 0
        need_details_count = 0
        
        if "成功保存" in message and "条记录" in message:
            save_match = re.search(r'成功保存 (\d+) 条记录', message)
            if save_match:
                saved_count = int(save_match.group(1))
                total_saved += saved_count
        
        if "发现" in message and "个订单需要详细显示" in message:
            details_match = re.search(r'发现 (\d+) 个订单需要详细显示', message)
            if details_match:
                need_details_count = int(details_match.group(1))
                total_need_details += need_details_count
        
        # 精简输出格式
        details_part = f" 需要详细查看{need_details_count}条" if need_details_count > 0 else ""
        print(f"第{page}页: 获取到{current_count}订单 保存记录{saved_count}条{details_part} lastId:{current_last_id}")
        
        total_processed += current_count
        
        # 检查API返回的found_target_or_smaller字段
        data = result.get('data', {})
        found_target_or_smaller = data.get('found_target_or_smaller', False)
        
        if found_target_or_smaller:
            print("找到目标订单或更早的订单，停止处理")
            break
        
        # 检查是否还有更多数据
        if current_count < 30:  # 默认limit是30
            print("已获取完所有数据（本页订单数小于限制数量）")
            break
        
        # 准备下一页
        last_id = current_last_id
        page += 1
        
        # 构建累计信息
        cumulative_parts = [f"累计处理: {total_processed} 个订单", f"保存: {total_saved} 条记录"]
        if total_need_details > 0:
            cumulative_parts.append(f"需要详细查看: {total_need_details} 个订单")
        print(", ".join(cumulative_parts))
    
    # 最终统计
    print(f"\n=== 增量更新完成 ===")
    print(f"总共处理了 {total_processed} 个订单")
    print(f"保存了 {total_saved} 条新记录")
    if total_need_details > 0:
        print(f"发现了 {total_need_details} 个订单需要详细查看")

if __name__ == "__main__":
    main()


'''
第1页: 获取到30订单 保存记录34条 需要详细查看1条 lastId:880133162633817536
累计处理: 30 个订单, 保存: 34 条记录, 需要详细查看: 1 个订单

=== 第 2 页请求 ===
第2页: 获取到30订单 保存记录38条 需要详细查看1条 lastId:880127043379158236
累计处理: 60 个订单, 保存: 72 条记录, 需要详细查看: 2 个订单

=== 第 3 页请求 ===
第3页: 获取到30订单 保存记录21条 lastId:879654174996060938
找到目标订单或更早的订单，停止处理

=== 增量更新完成 ===
总共处理了 90 个订单
保存了 93 条新记录
发现了 2 个订单需要详细查看
'''