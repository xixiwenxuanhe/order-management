#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import glob
from datetime import datetime

def merge_json_files():
    """
    合并所有 http_req_v2_*.json 文件到一个完整的JSON文件中
    """
    
    # 获取当前目录下所有匹配的JSON文件
    json_files = sorted(glob.glob("http_req_v2_*.json"))
    
    if not json_files:
        print("未找到任何匹配的JSON文件")
        return
    
    print(f"找到 {len(json_files)} 个JSON文件需要合并")
    
    merged_responses = []
    total_order_ids = set()  # 用于去重统计订单ID
    
    for i, file_path in enumerate(json_files):
        print(f"正在处理文件 {i+1}/{len(json_files)}: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取responses数组，只保留page和response字段
            if 'responses' in data and isinstance(data['responses'], list):
                for response in data['responses']:
                    # 只保留page和response字段
                    cleaned_response = {}
                    if 'page' in response:
                        cleaned_response['page'] = response['page']
                    if 'response' in response:
                        cleaned_response['response'] = response['response']
                        
                        # 统计订单ID
                        if 'data' in response['response'] and 'rowList' in response['response']['data']:
                            for row in response['response']['data']['rowList']:
                                if 'orderInfo' in row and 'orderId' in row['orderInfo']:
                                    total_order_ids.add(row['orderInfo']['orderId'])
                    
                    if cleaned_response:  # 如果有有效的数据才添加
                        merged_responses.append(cleaned_response)
                
                print(f"  - 从 {file_path} 合并了 {len(data['responses'])} 个响应")
            else:
                print(f"  - 警告: {file_path} 中没有找到有效的responses数组")
                
        except Exception as e:
            print(f"  - 错误: 处理文件 {file_path} 时出错: {str(e)}")
            continue
    
    # 保存合并后的JSON文件
    output_file = f"merged_orders.json"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_responses, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 合并完成!")
        print(f"输出文件: {output_file}")
        print(f"总响应数: {len(merged_responses)}")
        print(f"总订单数: {len(total_order_ids)}")
        print(f"合并文件数: {len(json_files)}")
        
    except Exception as e:
        print(f"❌ 保存文件时出错: {str(e)}")

if __name__ == "__main__":
    merge_json_files()
