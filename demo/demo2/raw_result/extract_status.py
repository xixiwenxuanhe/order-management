# 从optimized_orders.json中提取订单号和状态信息
import json
import os

def extract_status_info():
    """提取订单状态信息"""
    print("开始提取订单状态信息...")
    
    # 读取优化后的订单数据
    input_file = "optimized_orders.json"
    output_file = "status_info.json"
    
    if not os.path.exists(input_file):
        print(f"文件不存在: {input_file}")
        return
    
    print(f"正在读取文件: {input_file}")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            orders_data = json.load(f)
        
        print(f"成功加载 {len(orders_data)} 条订单数据")
        
        # 提取状态信息
        status_info = []
        status_count = {}
        
        for i, order in enumerate(orders_data):
            order_info = order.get('orderInfo', {})
            order_id = order_info.get('orderId')
            status = order_info.get('status', {})
            
            if order_id and status:
                status_name = status.get('name', '未知状态')
                
                # 收集状态信息
                status_item = {
                    'orderId': order_id,
                    'statusName': status_name
                }
                status_info.append(status_item)
                
                # 统计状态数量
                if status_name in status_count:
                    status_count[status_name] += 1
                else:
                    status_count[status_name] = 1
            
            # 进度显示
            if (i + 1) % 1000 == 0:
                print(f"已处理 {i + 1} 条订单...")
        
        # 准备输出数据
        output_data = {
            "total_orders": len(status_info),
            "status_statistics": status_count,
            "orders": status_info
        }
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== 提取完成 ===")
        print(f"总订单数: {len(status_info)}")
        print(f"结果已保存到: {output_file}")
        
        print("\n=== 状态统计 ===")
        for status_name, count in sorted(status_count.items(), key=lambda x: x[1], reverse=True):
            print(f"{status_name}: {count} 个订单")
            
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
    except Exception as e:
        print(f"处理失败: {e}")

if __name__ == "__main__":
    extract_status_info()
