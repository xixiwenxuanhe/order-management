#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单信息提取脚本
从原始订单数据中提取关键信息并保存到新的JSON文件中
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any


def extract_key_order_info(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取单个订单的关键信息
    
    Args:
        order_data: 单个订单的完整数据
        
    Returns:
        包含关键信息的字典
    """
    order_info = order_data.get('orderInfo', {})
    products = order_data.get('products', [])
    
    # 提取基本订单信息
    key_info = {
        'orderId': order_info.get('orderId', ''),
        'status': {
            'name': order_info.get('status', {}).get('name', ''),
            'key': order_info.get('status', {}).get('key', '')
        },
        'orderType': {
            'name': order_info.get('orderType', {}).get('name', ''),
            'key': order_info.get('orderType', {}).get('key', '')
        },
        'createdAt': order_info.get('createdAt', ''),
        'paidAt': order_info.get('paidAt', ''),
        'deliverPattern': {
            'name': order_info.get('deliverPattern', {}).get('name', ''),
            'key': order_info.get('deliverPattern', {}).get('key', '')
        }
    }
    
    # 买家信息
    buyer = order_info.get('buyer', {})
    key_info['buyer'] = {
        'id': buyer.get('id', ''),
        'name': buyer.get('name', ''),
        'phone': buyer.get('phone', '')
    }
    
    # 卖家信息
    seller = order_info.get('seller', {})
    key_info['seller'] = {
        'id': seller.get('id', ''),
        'name': seller.get('name', ''),
        'phone': seller.get('phone', '')
    }
    
    # 收货信息
    key_info['receiver'] = {
        'name': order_info.get('receiver', ''),
        'phone': order_info.get('receiverPhone', ''),
        'address': order_info.get('address', ''),
        'province': order_info.get('receiverProvince', ''),
        'city': order_info.get('receiverCity', ''),
        'district': order_info.get('receiverDistrict', '')
    }
    
    # 价格信息
    key_info['pricing'] = {
        'orderPrice': order_info.get('orderPrice', 0),
        'expressPrice': order_info.get('expressPrice', 0),
        'paidPrice': order_info.get('paidPrice', 0),
        'originalPrice': order_info.get('orderOriginalPrice', 0),
        'afterDiscountPrice': order_info.get('afterDiscountPrice', 0)
    }
    
    # 商品信息
    key_info['products'] = []
    for product in products:
        product_info = {
            'productId': product.get('productId', ''),
            'productName': product.get('productName', ''),
            'unitPrice': product.get('uintPrice', 0),
            'amount': product.get('amount', 0),
            'totalPrice': product.get('price', 0),
            'description': product.get('description', ''),
            'specValues': product.get('specValues', [])
        }
        key_info['products'].append(product_info)
    
    # 可执行操作
    active_actions = order_data.get('activeActions', [])
    key_info['availableActions'] = [
        {
            'action': action.get('action', ''),
            'actionName': action.get('actionName', '')
        }
        for action in active_actions
    ]
    
    # 其他重要字段
    key_info['productNum'] = order_data.get('productNum', '0')
    key_info['relatedId'] = order_info.get('relatedId', '')
    key_info['relatedType'] = order_info.get('relatedType', '')
    key_info['expiredAt'] = order_info.get('expiredAt', '0')
    
    return key_info


def process_order_data(input_file: str, output_file: str) -> None:
    """
    处理订单数据文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
    """
    try:
        # 读取原始数据
        with open(input_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # 检查数据结构
        if raw_data.get('code') != 0:
            print(f"警告: 响应码不为0，当前为 {raw_data.get('code')}")
        
        # 提取订单列表
        order_list = raw_data.get('data', {}).get('rowList', [])
        
        if not order_list:
            print("警告: 未找到订单数据")
            return
        
        # 处理每个订单
        extracted_orders = []
        for i, order in enumerate(order_list):
            try:
                key_info = extract_key_order_info(order)
                extracted_orders.append(key_info)
                print(f"已处理订单 {i+1}/{len(order_list)}: {key_info['orderId']}")
            except Exception as e:
                print(f"处理订单 {i+1} 时出错: {e}")
                continue
        
        # 准备输出数据
        output_data = {
            'extractTime': datetime.now().isoformat(),
            'totalOrders': len(extracted_orders),
            'originalMessage': raw_data.get('message', ''),
            'orders': extracted_orders
        }
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 处理完成!")
        print(f"📊 总共处理了 {len(extracted_orders)} 个订单")
        print(f"💾 结果已保存到: {output_file}")
        
        # 显示订单状态统计
        status_count = {}
        for order in extracted_orders:
            status = order['status']['name']
            status_count[status] = status_count.get(status, 0) + 1
        
        print("\n📈 订单状态统计:")
        for status, count in status_count.items():
            print(f"  {status}: {count} 个")
            
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {input_file}")
    except json.JSONDecodeError as e:
        print(f"❌ 错误: JSON解析失败 - {e}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def main():
    """主函数"""
    input_file = '1749469724351_body'
    output_file = 'extracted_orders.json'
    
    print("🔄 开始提取订单关键信息...")
    print(f"📖 输入文件: {input_file}")
    print(f"📝 输出文件: {output_file}")
    print("-" * 50)
    
    process_order_data(input_file, output_file)


if __name__ == '__main__':
    main() 