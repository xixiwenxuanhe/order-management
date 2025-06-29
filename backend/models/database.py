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
            交易时间 TEXT,
            状态 TEXT,
            商品名称 TEXT,
            数量 INTEGER,
            单价 INTEGER,
            金额 INTEGER,
            Complete BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # 创建需要详细显示的订单表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders_need_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            Complete BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_id ON order_products (订单编号)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_need_details_order_id ON orders_need_details (order_id)')
    
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

def save_orders_to_database(orders_data: List[Dict[str, Any]], raw_orders_data: List[Dict[str, Any]] = None):
    """保存订单数据到数据库"""
    
    conn = sqlite3.connect(DB_PATH, timeout=30.0)  # 增加超时时间
    cursor = conn.cursor()
    
    saved_records = 0
    orders_need_details_count = 0
    
    try:
        for i, order in enumerate(orders_data):
            order_info = order.get('orderInfo', {})
            products = order.get('products', [])
            
            # 获取订单基本信息
            order_id = order_info.get('orderId', '')
            if not order_id:
                continue
            
            # 获取原始数据中的productNum用于判断
            product_num = 0
            if raw_orders_data and i < len(raw_orders_data):
                raw_order = raw_orders_data[i]
                product_num = int(raw_order.get('productNum', 0))
            
            # 计算products数组中所有商品的数量总和
            actual_products_total = sum(product.get('amount', 0) for product in products)
            
            # 判断是否需要详细显示：如果productNum大于实际商品总数，说明有商品没显示完整
            if product_num > actual_products_total:
                # 保存到需要详细显示的订单表 - 使用当前连接
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO orders_need_details 
                        (order_id)
                        VALUES (?)
                    ''', (order_id,))
                    orders_need_details_count += 1
                except Exception as e:
                    print(f"保存需要详细显示的订单失败: {str(e)}")
                # 跳过保存到主表
                continue
                
            paid_at = timestamp_to_date(order_info.get('paidAt', ''))
            status = order_info.get('status', {}).get('name', '')
            
            # 删除该订单的旧记录
            cursor.execute('DELETE FROM order_products WHERE 订单编号 = ?', (order_id,))
            
            # 检查是否有商品，如果没有商品则插入一条空记录
            if not products:
                # 没有商品的情况，插入一条订单记录但商品信息为空
                is_complete = status == "交易成功"
                cursor.execute('''
                    INSERT INTO order_products 
                    (订单编号, 交易时间, 状态, 商品名称, 数量, 单价, 金额, Complete)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (order_id, paid_at, status, '', 0, 0, 0, is_complete))
                saved_records += 1
            else:
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
                        (订单编号, 交易时间, 状态, 商品名称, 数量, 单价, 金额, Complete)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (order_id, paid_at, status, product_name, amount, price, total_amount, is_complete))
                    
                    saved_records += 1
        
        conn.commit()
        
        message_parts = [f"成功保存 {saved_records} 条记录到数据库"]
        if orders_need_details_count > 0:
            message_parts.append(f"发现 {orders_need_details_count} 个订单需要详细显示")
        
        return {
            "saved_records": saved_records,
            "orders_need_details_count": orders_need_details_count,
            "message": "，".join(message_parts)
        }
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"保存数据库失败: {str(e)}")
    finally:
        conn.close()

def get_database_status():
    """获取数据库状态信息"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    try:
        # 获取记录总数
        cursor.execute('SELECT COUNT(*) FROM order_products')
        total_records = cursor.fetchone()[0]
        
        # 获取订单总数（去重）
        cursor.execute('SELECT COUNT(DISTINCT 订单编号) FROM order_products')
        total_orders = cursor.fetchone()[0]
        
        # 获取所有记录的最后时间（最近的时间）
        cursor.execute('''
            SELECT MAX(交易时间) 
            FROM order_products 
            WHERE 交易时间 IS NOT NULL AND 交易时间 != ""
        ''')
        latest_time_result = cursor.fetchone()
        latest_time = latest_time_result[0] if latest_time_result and latest_time_result[0] else None
        
        # 获取状态不为"交易成功"的记录的最早时间
        cursor.execute('''
            SELECT MIN(交易时间) 
            FROM order_products 
            WHERE 状态 != "交易成功" 
            AND 交易时间 IS NOT NULL AND 交易时间 != ""
        ''')
        incomplete_earliest_time_result = cursor.fetchone()
        incomplete_earliest_time = incomplete_earliest_time_result[0] if incomplete_earliest_time_result and incomplete_earliest_time_result[0] else None
        
        # 获取状态不为"交易成功"的记录中最早的那条对应的订单ID
        cursor.execute('''
            SELECT 订单编号 
            FROM order_products 
            WHERE 状态 != "交易成功" 
            AND 交易时间 IS NOT NULL AND 交易时间 != ""
            ORDER BY 交易时间 ASC
            LIMIT 1
        ''')
        incomplete_earliest_order_result = cursor.fetchone()
        incomplete_earliest_order_id = incomplete_earliest_order_result[0] if incomplete_earliest_order_result else None
        
        return {
            "total_records": total_records,
            "total_orders": total_orders,
            "latest_time": latest_time,
            "incomplete_earliest_time": incomplete_earliest_time,
            "incomplete_earliest_order_id": incomplete_earliest_order_id
        }
        
    finally:
        conn.close()

def get_record_count():
    """获取记录总数（保持兼容性）"""
    status = get_database_status()
    return status["total_records"]

def get_order_count():
    """获取订单总数（保持兼容性）"""
    status = get_database_status()
    return status["total_orders"]

def save_order_need_details(order_id: str):
    """保存需要详细显示的订单ID"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO orders_need_details 
            (order_id)
            VALUES (?)
        ''', (order_id,))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"保存需要详细显示的订单失败: {str(e)}")
        return False
    finally:
        conn.close()

def get_orders_need_details():
    """获取需要详细显示的订单列表"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, Complete 
        FROM orders_need_details 
        WHERE Complete = FALSE
        ORDER BY id DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [
        {
            "order_id": row[0],
            "complete": row[1]
        }
        for row in results
    ]

# 模块导入时自动检查并初始化数据库
if not os.path.exists(DB_PATH):
    init_database()
