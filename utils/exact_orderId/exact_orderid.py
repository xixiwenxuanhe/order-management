import json

def extract_order_ids(json_file_path):
    """
    从JSON文件中提取所有的orderId
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        order_ids = []
        
        # 使用JSON解析提取orderId
        if 'data' in data and 'rowList' in data['data']:
            for row in data['data']['rowList']:
                if 'orderInfo' in row and 'orderId' in row['orderInfo']:
                    order_ids.append(row['orderInfo']['orderId'])
        
        return order_ids
    
    except Exception as e:
        print(f"提取orderId时出错: {e}")
        return []

def save_order_ids(order_ids, output_file='extracted_order_ids.txt'):
    """
    将提取的orderId保存到文件
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for order_id in order_ids:
                f.write(order_id + '\n')
        print(f"成功保存 {len(order_ids)} 个orderId到 {output_file}")
    except Exception as e:
        print(f"保存文件时出错: {e}")

if __name__ == "__main__":
    json_file = "info.json"
    
    # 提取orderId
    order_ids = extract_order_ids(json_file)
    
    if order_ids:
        print(f"找到 {len(order_ids)} 个orderId:")
        for i, order_id in enumerate(order_ids, 1):
            print(f"{i}. {order_id}")
        
        # 保存到文件
        save_order_ids(order_ids)
        
        # 也可以保存为JSON格式
        output_json = {
            "order_ids": order_ids,
            "count": len(order_ids)
        }
        with open("extracted_order_ids.json", 'w', encoding='utf-8') as f:
            json.dump(output_json, f, ensure_ascii=False, indent=2)
        print("同时保存为JSON格式: extracted_order_ids.json")
    else:
        print("未找到任何orderId")
