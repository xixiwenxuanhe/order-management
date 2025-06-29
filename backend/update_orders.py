#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新订单脚本
"""

import requests

SERVER_URL = "http://localhost:8000"
API_BASE = f"{SERVER_URL}/api"

def get_database_status():
    response = requests.get(f"{API_BASE}/db-stats")
    return response.json()["data"]

def update_orders_from_target(target_order_id, auth_headers, last_id=None):
    payload = {
        "x_request_sign": auth_headers["x_request_sign"],
        "x_request_timestamp": auth_headers["x_request_timestamp"],
        "authorization": auth_headers["authorization"],
        "target_order_id": target_order_id,
        "limit": 30
    }
    
    if last_id:
        payload["last_id"] = last_id
    
    response = requests.post(f"{API_BASE}/update-orders", json=payload)
    return response.json()

def main():
    # 获取数据库状态
    db_status = get_database_status()
    target_order_id = db_status.get('incomplete_earliest_order_id')
    
    if not target_order_id:
        print("没有未完成的订单需要更新")
        return
    
    print(f"从订单ID {target_order_id} 开始更新")
    
    # 获取认证信息
    authorization = input("Authorization: ").strip()
    x_request_sign = input("X-Request-Sign: ").strip()
    x_request_timestamp = input("X-Request-Timestamp: ").strip()
    
    auth_headers = {
        "authorization": authorization,
        "x_request_sign": x_request_sign,
        "x_request_timestamp": x_request_timestamp
    }
    
    # 执行更新
    last_id = None
    result = update_orders_from_target(target_order_id, auth_headers, last_id)
    
    # 检查是否签名失效
    if not result.get('success') and "签名失效" in result.get('detail', ''):
        print("签名失效，请重新输入签名信息")
        x_request_sign = input("X-Request-Sign: ").strip()
        x_request_timestamp = input("X-Request-Timestamp: ").strip()
        
        auth_headers = {
            "authorization": authorization,
            "x_request_sign": x_request_sign,
            "x_request_timestamp": x_request_timestamp,
        }
        
        # 使用上次的last_id继续获取
        last_id = result.get('last_id')
        result = update_orders_from_target(target_order_id, auth_headers, last_id)
    
    print(result.get('message', ''))

if __name__ == "__main__":
    main()
