# 根据测试，当前签名有效期为1min

import requests
import json
import os
from datetime import datetime

# 读取并解析 http 报文文件
def parse_http_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    # 解析请求行
    request_line = lines[0]
    method, path, _ = request_line.split()
    headers = {}
    host = None
    body = ''
    is_body = False
    for line in lines[1:]:
        if line.strip() == '':
            is_body = True
            continue
        if not is_body:
            if ':' in line:
                k, v = line.split(':', 1)
                k = k.strip()
                v = v.strip()
                if k.lower() == 'host':
                    host = v
                headers[k] = v
        else:
            body += line.strip()
    if not host:
        raise ValueError('host 头缺失')
    scheme = 'https' if host.startswith('api.') or host.endswith(':443') else 'http'
    url = f"{scheme}://{host}{path}"
    return method, url, headers, body

def extract_order_ids_from_response(response_data):
    """
    从响应JSON中提取所有的orderId
    返回: (order_ids列表, 数量, 最后一个orderId)
    """
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

def send_request(method, url, headers, body):
    """发送HTTP请求"""
    if method.upper() == 'POST':
        resp = requests.post(url, headers=headers, data=body.encode('utf-8'))
    elif method.upper() == 'GET':
        resp = requests.get(url, headers=headers, params=body)
    else:
        raise Exception(f"暂不支持的方法: {method}")
    return resp

def save_progress(order_ids, filename='order_progress.json', is_completed=False):
    """保存当前进度到文件"""
    progress_data = {
        "order_ids": order_ids,
        "count": len(order_ids),
        "last_id": order_ids[-1] if order_ids else None,
        "is_completed": is_completed,
        "status": "已完成全部提取" if is_completed else "需要更新签名继续"
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)
    status_msg = "已完成全部提取" if is_completed else "需要更新签名继续"
    print(f"进度已保存到 {filename}，共 {len(order_ids)} 个OrderID，状态: {status_msg}")

def load_progress(filename='order_progress.json'):
    """从文件加载进度"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        order_ids = data.get('order_ids', [])
        last_id = data.get('last_id', None)
        print(f"加载进度成功，已有 {len(order_ids)} 个OrderID，最后ID: {last_id}")
        return order_ids, last_id
    except FileNotFoundError:
        print(f"进度文件 {filename} 不存在")
        return [], None
    except Exception as e:
        print(f"加载进度文件失败: {e}")
        return [], None

def is_signature_error(resp):
    """判断是否为签名错误"""
    if resp.status_code == 405:
        try:
            error_data = resp.json()
            return error_data.get('errCode') == 'SIG.FAIL'
        except:
            pass
    return False

if __name__ == "__main__":
    file_path = "http_req_think.hcy"
    method, url, headers, body = parse_http_file(file_path)
    
    # 解析原始请求体获取limit
    original_body = json.loads(body)
    limit = original_body.get('limit', 30)
    
    # 创建保存目录和文件名
    os.makedirs('raw_result', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_filename = f'raw_result/http_req_v2_{timestamp}.json'
    
    # 存储所有成功的响应
    all_responses = []
    
    # 选择模式
    print("请选择运行模式:")
    print("1. 从头开始获取")
    print("2. 从上次断点继续")
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == '2':
        # 从断点继续
        all_order_ids, last_id = load_progress()
        if not all_order_ids:
            print("没有找到有效的进度文件，将从头开始")
            all_order_ids = []
            last_id = None
        else:
            print(f"将从 lastId: {last_id} 继续获取")
    else:
        # 从头开始
        print("从头开始获取")
        all_order_ids = []
        last_id = None
    
    print(f"开始分页请求，每页limit: {limit}")
    page = len(all_order_ids) // limit + 1
    
    while True:
        print(f"\n=== 第 {page} 页请求 ===")
        
        # 构造当前请求体
        current_body = original_body.copy()
        if last_id:
            current_body['lastId'] = last_id
        
        # 读取最新的签名信息
        with open('x-request-timestamp.txt', 'r', encoding='utf-8') as f:
            headers['x-request-timestamp'] = f.read().strip()
        with open('x-request-sign.txt', 'r', encoding='utf-8') as f:
            headers['x-request-sign'] = f.read().strip()
        
        # 去掉 content-length，requests 会自动处理
        headers.pop('content-length', None)
        
        # 发送请求
        current_body_str = json.dumps(current_body, separators=(',', ':'))
        resp = send_request(method, url, headers, current_body_str)
        
        print(f"状态码: {resp.status_code}")
        
        # 检查是否为签名错误
        if is_signature_error(resp):
            print("检测到签名失效!")
            save_progress(all_order_ids)
            print("请更新签名文件后重新运行，选择模式2继续获取")
            break
        
        if resp.status_code != 200:
            print(f"请求失败: {resp.text}")
            save_progress(all_order_ids)
            break
        
        try:
            response_json = resp.json()
            
            # 保存成功的响应到列表
            all_responses.append({
                "page": page,
                "timestamp": datetime.now().isoformat(),
                "response": response_json
            })
            
            # 提取当前页的orderIds
            page_order_ids, count, current_last_id = extract_order_ids_from_response(response_json)
            
            if page_order_ids:
                all_order_ids.extend(page_order_ids)
                print(f"本页获取到 {count} 个OrderID")
                for i, order_id in enumerate(page_order_ids, 1):
                    print(f"  {len(all_order_ids) - count + i}. {order_id}")
                
                # 判断是否还有下一页
                if count < limit:
                    print(f"本页数量({count}) < limit({limit})，已获取完所有数据")
                    # 保存完成状态
                    save_progress(all_order_ids, is_completed=True)
                    break
                else:
                    last_id = current_last_id
                    page += 1
                    print(f"准备请求下一页，lastId: {last_id}")
            else:
                print("本页未获取到任何OrderID，结束请求")
                # 保存完成状态
                save_progress(all_order_ids, is_completed=True)
                break
                
        except Exception as e:
            print("响应内容:", resp.text)
            print(f"JSON解析失败: {e}")
            save_progress(all_order_ids)
            break
    
    # 保存所有成功的响应到JSON文件
    if all_responses:
        response_summary = {
            "summary": {
                "total_pages": len(all_responses),
                "total_order_ids": len(all_order_ids),
                "timestamp": datetime.now().isoformat(),
                "is_completed": len(all_order_ids) % limit != 0 if all_order_ids else True
            },
            "responses": all_responses
        }
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(response_summary, f, ensure_ascii=False, indent=2)
        print(f"成功响应已保存到 {json_filename}")
    
    # 输出最终结果
    print(f"\n=== 最终结果: 共获取到 {len(all_order_ids)} 个 OrderID ===")
