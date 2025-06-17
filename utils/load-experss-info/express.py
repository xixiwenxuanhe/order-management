# 简单的快递信息获取脚本
import requests
import json

def parse_http_file(file_path):
    """解析HTTP请求文件"""
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

def load_signature_files():
    """读取签名文件"""
    try:
        with open('x-request-timestamp.txt', 'r', encoding='utf-8') as f:
            timestamp = f.read().strip()
        with open('x-request-sign.txt', 'r', encoding='utf-8') as f:
            sign = f.read().strip()
        return timestamp, sign
    except FileNotFoundError as e:
        print(f"签名文件未找到: {e}")
        return None, None

def send_request(http_file_path, order_id):
    """发送HTTP请求获取快递信息"""
    # print("=== 快递信息获取工具 ===")
    # print(f"HTTP文件: {http_file_path}")
    # print(f"订单ID: {order_id}")
    
    # 解析HTTP文件
    try:
        method, url, headers, body = parse_http_file(http_file_path)
        
        # 替换请求体中的订单ID
        if body:
            try:
                body_json = json.loads(body)
                if 'orderId' in body_json:
                    body_json['orderId'] = order_id
                    body = json.dumps(body_json, separators=(',', ':'))
                    # print(f"已替换请求体中的orderId为: {order_id}")
            except json.JSONDecodeError:
                print("请求体不是有效的JSON格式")
        
        # print(f"解析请求: {method} {url}")
    except Exception as e:
        print(f"解析HTTP文件失败: {e}")
        return
    
    # 读取签名信息
    timestamp, sign = load_signature_files()
    if not timestamp or not sign:
        print("无法读取签名文件")
        return
    
    # 更新签名信息
    headers['x-request-timestamp'] = timestamp
    headers['x-request-sign'] = sign
    headers.pop('content-length', None)  # 去掉content-length
    
    # 发送POST请求
    resp = requests.post(url, headers=headers, data=body.encode('utf-8'))
    
    # 直接输出原始响应
    print(resp.text)

if __name__ == "__main__":
    # 设置HTTP文件路径和订单ID
    http_file = "http_req_express.hcy"
    order_id = "875568108466915159"
    
    # 调用请求函数
    send_request(http_file, order_id)

'''
{
  "code": "0",
  "message": "",
  "data": [
    {
      "companyCode": "yuantong",
      "expressNo": "YT2556966040057",
      "subscribeStatus": "SubscribeStatus_Success",
      "traces": [
        {
          "traceState": "TraceState_Collect",
          "traceTime": "1750149373",
          "traceContext": "您的快件在【甘肃省兰州市皋兰县】已揽收，揽收人: 刘世芳（18194299662）【物流问题无需找商家或平台，请致电（0931-5720122）（专属热线:95554）更快解决】",
          "traceType": "ACCEPT",
          "status": "EXPRESS_STATUS_DEFAULT",
          "statusEx": ""
        }
      ],
      "isArrived": false,
      "companyName": "圆通速递",
      "remark": ""
    }
  ]
}
'''