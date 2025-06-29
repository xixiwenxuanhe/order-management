#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单数据导出到Excel工具
从SQLite数据库中的order_products表提取订单信息并导出到Excel文件
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os
import sys

# 数据库路径
DB_PATH = "orders.db"

def export_orders_to_excel(excel_file_path, filter_incomplete_only=False, filter_complete_only=False):
    """
    从数据库导出订单数据到Excel文件
    
    Args:
        excel_file_path: Excel文件输出路径
        filter_incomplete_only: 只导出未完成的订单（状态不是"交易成功"且不是"交易关闭"）
        filter_complete_only: 只导出已完成的订单（状态为"交易成功"或"交易关闭"）
    """
    print("正在连接数据库...")
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        print(f"错误: 找不到数据库文件 {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cursor = conn.cursor()
        
        # 构建查询SQL
        base_sql = '''
            SELECT 
                订单编号,
                交易时间,
                状态,
                商品名称,
                数量,
                单价,
                金额
            FROM order_products
        '''
        
        params = []
        
        if filter_incomplete_only:
            base_sql += ' WHERE 状态 != "交易成功" AND 状态 != "交易关闭"'
        elif filter_complete_only:
            base_sql += ' WHERE 状态 = "交易成功" OR 状态 = "交易关闭"'
        
        base_sql += ' ORDER BY 交易时间 DESC, 订单编号'
        
        print("正在查询数据库...")
        cursor.execute(base_sql, params)
        
        # 获取数据
        columns = ['订单编号', '交易时间', '状态', '商品名称', '数量', '单价', '金额']
        data = cursor.fetchall()
        
        if not data:
            print("数据库中没有找到符合条件的订单数据")
            return
        
        print(f"查询到 {len(data)} 条商品记录")
        
        # 创建DataFrame
        df = pd.DataFrame(data, columns=columns)
        
        # 数据处理：转换数据类型
        df['数量'] = pd.to_numeric(df['数量'], errors='coerce').fillna(0).astype(int)
        df['单价'] = pd.to_numeric(df['单价'], errors='coerce').fillna(0).astype(int)
        df['金额'] = pd.to_numeric(df['金额'], errors='coerce').fillna(0).astype(int)
        
        # 添加统计信息
        total_orders = df['订单编号'].nunique()
        total_amount = df['金额'].sum()
        
        print(f"涉及 {total_orders} 个订单")
        print(f"总金额: {total_amount}")
        
        # 导出到Excel
        try:
            with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
                # 主数据表
                df.to_excel(writer, sheet_name='订单详情', index=False)
                
                # 统计表
                summary_data = [
                    ['总商品记录数', len(data)],
                    ['总订单数', total_orders],
                    ['总金额', total_amount],
                    ['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                ]
                
                if filter_incomplete_only:
                    summary_data.append(['筛选条件', '仅未完成订单'])
                elif filter_complete_only:
                    summary_data.append(['筛选条件', '仅已完成订单'])
                else:
                    summary_data.append(['筛选条件', '全部订单'])
                
                summary_df = pd.DataFrame(summary_data, columns=['项目', '值'])
                summary_df.to_excel(writer, sheet_name='统计信息', index=False)
                
                # 按状态分组统计
                status_summary = df.groupby('状态').agg({
                    '订单编号': 'nunique',
                    '数量': 'sum',
                    '金额': 'sum'
                }).reset_index()
                status_summary.columns = ['状态', '订单数', '总数量', '总金额']
                status_summary.to_excel(writer, sheet_name='状态统计', index=False)
            
            print(f"数据导出成功！")
            print(f"输出文件: {excel_file_path}")
            
        except Exception as e:
            print(f"导出Excel文件失败: {e}")
            print("请确保已安装openpyxl: pip install openpyxl")
        
    except Exception as e:
        print(f"数据库操作失败: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def export_orders_need_details_to_excel(excel_file_path):
    """
    导出orders_need_details表中的订单信息到Excel
    """
    print("正在导出需要详细显示的订单...")
    
    if not os.path.exists(DB_PATH):
        print(f"错误: 找不到数据库文件 {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cursor = conn.cursor()
        
        # 获取orders_need_details中的订单详情
        cursor.execute('''
            SELECT 
                ond.order_id,
                ond.Complete as need_details_complete,
                op.交易时间,
                op.状态,
                COUNT(op.id) as 商品条数,
                SUM(op.金额) as 总金额
            FROM orders_need_details ond
            LEFT JOIN order_products op ON ond.order_id = op.订单编号
            GROUP BY ond.order_id, ond.Complete, op.交易时间, op.状态
            ORDER BY op.交易时间 DESC
        ''')
        
        columns = ['订单编号', '详情获取完成', '交易时间', '状态', '商品条数', '总金额']
        data = cursor.fetchall()
        
        if not data:
            print("orders_need_details表中没有订单数据")
            return
        
        # 创建DataFrame
        df = pd.DataFrame(data, columns=columns)
        
        # 导出到Excel
        df.to_excel(excel_file_path, index=False, engine='openpyxl')
        print(f"需要详细显示的订单导出成功: {excel_file_path}")
        print(f"共 {len(data)} 个需要详细显示的订单")
        
    except Exception as e:
        print(f"导出需要详细显示的订单失败: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='订单数据导出工具')
    parser.add_argument('--output', '-o', default='订单数据导出.xlsx', help='输出Excel文件名')
    parser.add_argument('--incomplete-only', action='store_true', help='只导出未完成的订单')
    parser.add_argument('--complete-only', action='store_true', help='只导出已完成的订单')
    parser.add_argument('--need-details', action='store_true', help='导出需要详细显示的订单列表')
    
    args = parser.parse_args()
    
    if args.incomplete_only and args.complete_only:
        print("错误: --incomplete-only 和 --complete-only 不能同时使用")
        return
    
    if args.need_details:
        export_orders_need_details_to_excel(args.output)
    else:
        # 执行主要导出
        export_orders_to_excel(args.output, args.incomplete_only, args.complete_only)

if __name__ == '__main__':
    main() 