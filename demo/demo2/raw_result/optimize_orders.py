#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime

def optimize_orders_json(input_file='merged_orders.json', 
                        output_file='optimized_orders.json'):
    """
    优化订单JSON文件，只保留网页展示需要的关键信息
    """
    
    if not os.path.exists(input_file):
        print(f"❌ 错误: 找不到文件 {input_file}")
        return
    
    try:
        print(f"📖 正在读取文件: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
        
        # 获取原始文件大小
        original_size = os.path.getsize(input_file)
        print(f"📏 原始文件大小: {format_file_size(original_size)}")
        
        optimized_data = []
        total_orders = 0
        
        for page_data in original_data:
            if not isinstance(page_data, dict) or 'page' not in page_data:
                continue
                
            page_num = page_data['page']
            
            if ('response' not in page_data or 
                'data' not in page_data['response'] or 
                'rowList' not in page_data['response']['data']):
                continue
            
            row_list = page_data['response']['data']['rowList']
            
            for order in row_list:
                if 'orderInfo' not in order:
                    continue
                
                # 提取订单基本信息
                order_info = order['orderInfo']
                optimized_order = {
                    'page': page_num,
                    'orderInfo': extract_order_info(order_info),
                    'products': extract_products_info(order.get('products', []))
                }
                
                optimized_data.append(optimized_order)
                total_orders += 1
        
        # 保存优化后的数据
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(optimized_data, f, ensure_ascii=False, indent=2)
        
        # 获取优化后文件大小
        optimized_size = os.path.getsize(output_file)
        reduction_percentage = ((original_size - optimized_size) / original_size) * 100
        
        print(f"\n✅ 优化完成!")
        print(f"📄 输出文件: {output_file}")
        print(f"📊 处理订单数: {total_orders}")
        print(f"📏 优化后大小: {format_file_size(optimized_size)}")
        print(f"💾 节省空间: {format_file_size(original_size - optimized_size)} ({reduction_percentage:.1f}%)")
        
        # 显示保留的字段信息
        print(f"\n📋 保留的关键字段:")
        print("   🔹 订单信息: orderId, status, createdAt, buyer, seller, receiver, address")
        print("   🔹 价格信息: orderPrice, paidPrice, expressPrice")
        print("   🔹 商品信息: productName, cover, price, amount, description, specValues")
        
    except Exception as e:
        print(f"❌ 处理文件时出错: {str(e)}")

def extract_order_info(order_info):
    """
    提取订单的关键信息
    """
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
        'buyer': buyer_info,
        'seller': seller_info,
        'receiver': order_info.get('receiver', ''),
        'address': order_info.get('address', ''),
        'orderPrice': order_info.get('orderPrice', 0),
        'paidPrice': order_info.get('paidPrice', 0),
        'expressPrice': order_info.get('expressPrice', 0)
    }

def extract_products_info(products):
    """
    提取商品的关键信息
    """
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

def format_file_size(size_bytes):
    """
    格式化文件大小显示
    """
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    size_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and size_index < len(size_names) - 1:
        size /= 1024
        size_index += 1
    
    return f"{size:.1f}{size_names[size_index]}"

def compare_files(original_file, optimized_file):
    """
    比较原始文件和优化文件的详细信息
    """
    if not os.path.exists(original_file) or not os.path.exists(optimized_file):
        print("❌ 无法比较文件，文件不存在")
        return
    
    try:
        # 读取文件
        with open(original_file, 'r', encoding='utf-8') as f:
            original_data = json.load(f)
        
        with open(optimized_file, 'r', encoding='utf-8') as f:
            optimized_data = json.load(f)
        
        # 统计信息
        original_orders = sum(len(page.get('response', {}).get('data', {}).get('rowList', [])) 
                            for page in original_data if isinstance(page, dict))
        optimized_orders = len(optimized_data)
        
        print(f"\n📊 文件对比:")
        print(f"   原始订单数: {original_orders}")
        print(f"   优化订单数: {optimized_orders}")
        print(f"   数据完整性: {'✅ 完整' if original_orders == optimized_orders else '❌ 有数据丢失'}")
        
    except Exception as e:
        print(f"❌ 比较文件时出错: {str(e)}")

if __name__ == "__main__":
    print("🚀 订单数据优化工具")
    print("=" * 50)
    
    # 执行优化
    optimize_orders_json()
    
    # 比较文件
    compare_files('demo/demo2/raw_result/merged_orders.json', 'demo/demo2/raw_result/optimized_orders.json')
    
    print("\n🎉 处理完成! 您可以将 optimized_orders.json 重命名为 merged_orders.json 来替换原文件。") 