#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务逻辑服务层
"""

import json
import os
import requests
from typing import Tuple, List, Dict, Any



def extract_order_ids_from_response(response_data: Dict[str, Any]) -> Tuple[List[str], int, str]:
    """从响应JSON中提取所有的orderId"""
    order_ids = []
    try:
        if 'data' in response_data and 'rowList' in response_data['data']:
            for row in response_data['data']['rowList']:
                if 'orderInfo' in row and 'orderId' in row['orderInfo']:
                    order_ids.append(row['orderInfo']['orderId'])
    except Exception as e:
        print(f"提取orderId时出错: {e}")
    
    count = len(order_ids)
    last_id = order_ids[-1] if order_ids else None
    return order_ids, count, last_id

def extract_order_info(order_info: Dict[str, Any]) -> Dict[str, Any]:
    """提取订单的关键信息"""
    # 提取买家信息
    buyer = order_info.get('buyer', {})
    buyer_info = {
        'name': buyer.get('name', ''),
        'phone': buyer.get('phone', '')
    }
    
    # 提取卖家信息
    seller = order_info.get('seller', {})
    seller_info = {
        'name': seller.get('name', '')
    }
    
    # 提取状态信息
    status = order_info.get('status', {})
    status_info = {
        'name': status.get('name', ''),
        'key': status.get('key', '')
    }
    
    return {
        'orderId': order_info.get('orderId', ''),
        'status': status_info,
        'createdAt': order_info.get('createdAt', ''),
        'paidAt': order_info.get('paidAt', ''),
        'buyer': buyer_info,
        'seller': seller_info,
        'receiver': order_info.get('receiver', ''),
        'address': order_info.get('address', ''),
        'orderPrice': order_info.get('orderPrice', 0),
        'paidPrice': order_info.get('paidPrice', 0),
        'expressPrice': order_info.get('expressPrice', 0)
    }

def extract_products_info(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """提取商品的关键信息"""
    optimized_products = []
    
    for product in products:
        # 提取规格信息
        spec_values = product.get('specValues', [])
        optimized_specs = []
        for spec in spec_values:
            optimized_specs.append({
                'name': spec.get('name', ''),
                'value': spec.get('value', ''),
                'color': spec.get('color', ''),
                'labelColor': spec.get('labelColor', '')
            })
        
        optimized_product = {
            'productName': product.get('productName', ''),
            'cover': product.get('cover', ''),
            'whiteBgPng': product.get('whiteBgPng', ''),
            'price': product.get('price', 0),
            'amount': product.get('amount', 1),
            'description': product.get('description', ''),
            'specValues': optimized_specs
        }
        
        optimized_products.append(optimized_product)
    
    return optimized_products

def fetch_orders_from_api(
    x_request_sign: str,
    x_request_timestamp: str,
    authorization: str,
    limit: int = 30,
    last_id: str = None
) -> Dict[str, Any]:
    """从API获取订单数据"""
    
    # 硬编码的API配置
    url = "https://api.qiandao.cn/order-web/user/v3/load-order-list"
    method = "POST"
    
    # 固定的请求头
    headers = {
        'accept-encoding': 'gzip',
        'x-request-version': '5.91.1',
        'x-request-sign-type': 'RSA2',
        'x-echo-teen-mode': 'false',
        'x-request-utm_source': 'xiaomi',
        'x-request-package-sign-version': '0.0.3',
        'x-request-id': '',
        'x-client-package-id': '1006',
        'x-request-package-id': '1006',
        'x-device-id': '6ec1e3cac888f55d',
        'user-agent': 'Kuril+/5.91.1 (Android 15)',
        'x-echo-install-id': 'ODY5NjE4MjM0NDA2NTAyOTQ5',
        'cache-control': 'max-age=3600',
        'x-echo-city-code': '',
        'content-type': 'application/json',
        'downloadchannel': 'xiaomi',
        'x-request-sign-version': 'v1',
        'referer': 'https://qiandao.cn',
        'x-request-channel': 'xiaomi',
        'x-echo-region': 'CN',
        'accept-language': 'zh-CN',
        'host': 'api.qiandao.cn',
        'x-request-device': 'android',
        # 动态更新的认证信息
        'x-request-timestamp': x_request_timestamp,
        'x-request-sign': x_request_sign,
        'authorization': authorization
    }
    
    # 固定的请求体
    original_body = {
        "limit": 30,
        "sellerIdList": [],
        "waitPayAppointmentExpress": False,
        "deliverPattern": None,
        "statusList": [
            "REFUNDING",
            "WAIT_SELLER_CONFIRM_ORDER", 
            "WAIT_BUYER_PAY",
            "WAIT_SELLER_SEND_GOODS",
            "WAIT_BUYER_CONFIRM_GOODS",
            "BUYER_CONFIRM_GOODS",
            "WAIT_REFUND",
            "WAIT_RETURN_REFUND_APPROVE",
            "WAIT_RETURN_REFUND_CONFIRM", 
            "WAIT_BUYER_RETURN_GOODS",
            "LOCKED"
        ]
    }
    
    # 去掉 content-length，requests 会自动处理
    headers.pop('content-length', None)
    
    # 构造请求体
    current_body = original_body.copy()
    current_body['limit'] = limit
    
    if last_id:
        current_body['lastId'] = last_id
    
    # 发送请求
    current_body_str = json.dumps(current_body, separators=(',', ':'))
    
    if method.upper() == 'POST':
        resp = requests.post(url, headers=headers, data=current_body_str.encode('utf-8'))
    elif method.upper() == 'GET':
        resp = requests.get(url, headers=headers, params=current_body_str)
    else:
        raise ValueError(f"不支持的HTTP方法: {method}")
    
    if resp.status_code != 200:
        raise requests.RequestException(f"请求失败: {resp.status_code} - {resp.text}")
    
    response_json = resp.json()
    
    # 检查响应是否成功
    if response_json.get('code') != 0:
        raise ValueError(f"API返回错误: {response_json.get('message', '未知错误')}")
    
    # 提取和优化订单数据
    optimized_data = []
    row_list = response_json.get('data', {}).get('rowList', [])
    
    for order in row_list:
        if 'orderInfo' not in order:
            continue
        
        order_info = order['orderInfo']
        optimized_order = {
            'orderInfo': extract_order_info(order_info),
            'products': extract_products_info(order.get('products', []))
        }
        
        optimized_data.append(optimized_order)
    
    # 提取orderIds用于分页
    order_ids, count, last_id = extract_order_ids_from_response(response_json)
    
    return {
        "orders": optimized_data,
        "pagination": {
            "count": count,
            "last_id": last_id,
            "has_more": count >= limit
        },
        "order_ids": order_ids
    } 