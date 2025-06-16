# 根据测试，当前签名有效期为1min

import requests
import json

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

if __name__ == "__main__":
    file_path = "http_req_think.hcy"
    method, url, headers, body = parse_http_file(file_path)
    # 读取 x-request-timestamp.txt 和 x-request-sign.txt 覆盖对应 header
    with open('x-request-timestamp.txt', 'r', encoding='utf-8') as f:
        headers['x-request-timestamp'] = f.read().strip()
    with open('x-request-sign.txt', 'r', encoding='utf-8') as f:
        headers['x-request-sign'] = f.read().strip()
    # 去掉 content-length，requests 会自动处理
    headers.pop('content-length', None)
    # 发送请求
    if method.upper() == 'POST':
        resp = requests.post(url, headers=headers, data=body.encode('utf-8'))
    elif method.upper() == 'GET':
        resp = requests.get(url, headers=headers, params=body)
    else:
        raise Exception(f"暂不支持的方法: {method}")
    print("状态码:", resp.status_code)
    
    try:
        response_json = resp.json()
        print("响应内容:", json.dumps(response_json, ensure_ascii=False, indent=2))
        # 只保存响应结果
        with open('http_req_v1.json', 'w', encoding='utf-8') as f:
            json.dump(response_json, f, ensure_ascii=False, indent=2)
    except Exception:
        print("响应内容:", resp.text)
        # 保存文本响应
        with open('http_req_v1.json', 'w', encoding='utf-8') as f:
            json.dump({"response_text": resp.text}, f, ensure_ascii=False, indent=2)
    
    print(f"响应结果已保存到 http_req_v1.json")
