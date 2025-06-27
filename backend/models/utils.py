#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数
"""

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