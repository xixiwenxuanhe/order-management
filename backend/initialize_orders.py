#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据初始化脚本
不断调用后端API获取全部数据到数据库中
支持签名过期处理和断点续传
"""

import requests
import json
import os
import time
from datetime import datetime

# 后端API配置
BACKEND_URL = "http://localhost:8000"
GET_ORDERS_ENDPOINT = "/api/get-orders"
DB_STATS_ENDPOINT = "/api/db-stats"

def get_user_input_for_authorization():
    """获取用户输入的authorization信息"""
    print("\n=== 请输入认证信息 ===")
    authorization = input("请输入 authorization: ").strip()
    return authorization

def get_user_input_for_signature():
    """获取用户输入的签名信息"""
    print("\n=== 需要更新签名信息 ===")
    x_request_sign = input("请输入 x-request-sign: ").strip()
    x_request_timestamp = input("请输入 x-request-timestamp: ").strip()
    return x_request_sign, x_request_timestamp

def call_backend_api(x_request_sign, x_request_timestamp, authorization, limit=30, last_id=None):
    """调用后端API获取订单数据"""
    url = f"{BACKEND_URL}{GET_ORDERS_ENDPOINT}"
    
    payload = {
        "x_request_sign": x_request_sign,
        "x_request_timestamp": x_request_timestamp,
        "authorization": authorization,
        "limit": limit
    }
    
    if last_id:
        payload["last_id"] = last_id
    
    try:
        response = requests.post(url, json=payload)
        return response
    except requests.RequestException as e:
        print(f"请求后端API失败: {e}")
        return None

def get_db_stats():
    """获取数据库统计信息"""
    url = f"{BACKEND_URL}{DB_STATS_ENDPOINT}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
        return None
    except requests.RequestException as e:
        print(f"获取数据库统计失败: {e}")
        return None

def main():
    """主函数"""
    print("=== 订单数据初始化工具 ===")
    print("此工具将不断调用后端API获取全部订单数据到数据库中")
    
    # 检查后端服务是否运行
    try:
        response = requests.get(f"{BACKEND_URL}/docs", timeout=5)
        if response.status_code != 200:
            print(f"后端服务似乎未正常运行，请确保后端服务已启动在 {BACKEND_URL}")
            return
    except requests.RequestException:
        print(f"无法连接到后端服务 {BACKEND_URL}，请确保后端服务已启动")
        return
    
    # 显示当前数据库状态
    db_stats = get_db_stats()
    if db_stats:
        print(f"当前数据库状态: 订单数 {db_stats.get('total_orders', 0)}, 记录数 {db_stats.get('total_records', 0)}")
    
    # 第一次运行，只获取authorization
    authorization = get_user_input_for_authorization()
    
    # 初始化签名信息（第一次需要用户输入）
    x_request_sign, x_request_timestamp = get_user_input_for_signature()
    
    # 初始化变量
    total_fetched = 0
    last_id = None
    page = 1
    limit = 30
    
    print(f"\n开始获取数据，将持续获取直到所有数据获取完毕")
    
    while True:
        print(f"\n=== 第 {page} 页请求 ===")
        
        # 调用后端API
        response = call_backend_api(x_request_sign, x_request_timestamp, authorization, limit, last_id)
        
        # 统一处理所有失败情况
        success = False
        if response and response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get("success"):
                    success = True
                    
                    # 获取返回的数据信息
                    current_count = response_data.get("total_orders", 0)
                    current_last_id = response_data.get("last_id")
                    
                    print(f"本页获取到 {current_count} 条订单")
                    print(f"API消息: {response_data.get('message', '')}")
                    
                    if current_count > 0:
                        total_fetched += current_count
                        print(f"累计已获取 {total_fetched} 条订单")
                        
                        # 检查是否还有更多数据
                        if current_count < limit:
                            print("已获取完所有数据（本页订单数小于限制数量）")
                            break
                        
                        # 更新last_id用于下一页
                        last_id = current_last_id
                        print(f"下一页的lastId: {current_last_id}")
                        page += 1
                        
                        # 移除延迟，加快获取速度
                        # time.sleep(1)
                    else:
                        print("本页未获取到任何订单，数据获取完成")
                        break
            except Exception:
                pass
        
        # 如果不成功，统一处理
        if not success:
            if response:
                print(f"请求失败，状态码: {response.status_code}")
                if hasattr(response, 'text'):
                    print(f"响应内容: {response.text}")
            else:
                print("API调用失败")
            
            # 统一的失败处理：重新输入签名信息
            x_request_sign = input("请输入 x-request-sign: ").strip()
            x_request_timestamp = input("请输入 x-request-timestamp: ").strip()
            continue
    
    # 显示最终结果
    final_db_stats = get_db_stats()
    if final_db_stats:
        print(f"\n=== 最终数据库状态 ===")
        print(f"订单数: {final_db_stats.get('total_orders', 0)}")
        print(f"记录数: {final_db_stats.get('total_records', 0)}")
    
    print(f"\n=== 数据获取完成 ===")
    print(f"总共获取了 {total_fetched} 条订单")

if __name__ == "__main__":
    main()
