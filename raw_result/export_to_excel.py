#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单数据导出到Excel工具
从optimized_orders.json文件中提取订单信息并导出到Excel文件
"""

import json
import pandas as pd
from datetime import datetime
import os

def timestamp_to_date(timestamp_str):
    """将时间戳转换为日期格式"""
    try:
        timestamp = int(timestamp_str)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str

def export_orders_to_excel(json_file_path, excel_file_path):
    """
    将订单数据导出到Excel文件
    
    Args:
        json_file_path: JSON文件路径
        excel_file_path: Excel文件输出路径
    """
    print("正在读取JSON文件...")
    
    # 读取订单JSON文件
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            orders_data = json.load(f)
    except Exception as e:
        print(f"读取订单JSON文件失败: {e}")
        return
    
    # 准备数据列表
    export_data = []
    
    print("正在处理订单数据...")
    
    # 遍历每个订单
    for order in orders_data:
        order_info = order.get('orderInfo', {})
        products = order.get('products', [])
        
        # 获取订单基本信息
        order_id = order_info.get('orderId', '')
        created_at = timestamp_to_date(order_info.get('createdAt', ''))
        status = order_info.get('status', {}).get('name', '')
        
        # 遍历每个商品
        for product in products:
            product_name = product.get('productName', '')
            price = product.get('price', 0)
            amount = product.get('amount', 0)
            
            # 计算总金额
            total_amount = price * amount
            
            # 构建数据行
            row = {
                '订单编号': order_id,
                '下单日期': created_at,
                '状态': status,
                '商品名称': product_name,
                '数量': amount,
                '单价': price,
                '金额': total_amount
            }
            
            export_data.append(row)
    
    # 创建DataFrame
    df = pd.DataFrame(export_data)
    
    # 导出到Excel
    try:
        df.to_excel(excel_file_path, index=False, engine='openpyxl')
        print(f"数据导出成功！")
        print(f"输出文件: {excel_file_path}")
        print(f"共导出 {len(export_data)} 条商品记录")
        print(f"涉及 {len(set(row['订单编号'] for row in export_data))} 个订单")
    except Exception as e:
        print(f"导出Excel文件失败: {e}")
        print("请确保已安装openpyxl: pip install openpyxl")

def main():
    """主函数"""
    # 文件路径设置
    json_file = 'optimized_orders.json'
    excel_file = '订单数据导出.xlsx'
    
    # 检查输入文件是否存在
    if not os.path.exists(json_file):
        print(f"错误: 找不到文件 {json_file}")
        return
    
    # 执行导出
    export_orders_to_excel(json_file, excel_file)

if __name__ == '__main__':
    main() 