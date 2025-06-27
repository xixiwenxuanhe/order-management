#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型和操作
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any

# 数据库文件路径
DB_PATH = "orders.db"

def init_database():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建订单商品表（与Excel字段完全一致）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            订单编号 TEXT NOT NULL,
            下单日期 TEXT,
            状态 TEXT,
            商品名称 TEXT,
            数量 INTEGER,
            单价 INTEGER,
            金额 INTEGER,
            Complete BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_id ON order_products (订单编号)')
    
    conn.commit()
    conn.close()

def timestamp_to_date(timestamp_str):
    """将时间戳转换为日期格式"""
    try:
        if not timestamp_str:
            return None
        timestamp = int(timestamp_str)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str

def save_orders_to_database(orders_data: List[Dict[str, Any]]):
    """保存订单数据到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    saved_records = 0
    
    try:
        for order in orders_data:
            order_info = order.get('orderInfo', {})
            products = order.get('products', [])
            
            # 获取订单基本信息
            order_id = order_info.get('orderId', '')
            if not order_id:
                continue
                
            paid_at = timestamp_to_date(order_info.get('paidAt', ''))
            status = order_info.get('status', {}).get('name', '')
            
            # 删除该订单的旧记录
            cursor.execute('DELETE FROM order_products WHERE 订单编号 = ?', (order_id,))
            
            # 插入每个商品记录（与Excel格式完全一致）
            for product in products:
                product_name = product.get('productName', '')
                amount = product.get('amount', 0)
                price = product.get('price', 0)
                total_amount = price * amount
                
                # 判断是否为交易成功
                is_complete = status == "交易成功"
                
                cursor.execute('''
                    INSERT INTO order_products 
                    (订单编号, 下单日期, 状态, 商品名称, 数量, 单价, 金额, Complete)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (order_id, paid_at, status, product_name, amount, price, total_amount, is_complete))
                
                saved_records += 1
        
        conn.commit()
        return {
            "saved_records": saved_records,
            "message": f"成功保存 {saved_records} 条记录到数据库"
        }
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"保存数据库失败: {str(e)}")
    finally:
        conn.close()

def get_record_count():
    """获取记录总数"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM order_products')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_order_count():
    """获取订单总数（去重）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(DISTINCT 订单编号) FROM order_products')
    count = cursor.fetchone()[0]
    conn.close()
    return count



# 初始化数据库
if not os.path.exists(DB_PATH):
    init_database() 