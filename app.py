#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的订单管理Web应用
"""

from flask import Flask, render_template, send_from_directory
import os

# 创建Flask应用，设置模板和静态文件目录为当前目录
app = Flask(__name__, 
           template_folder='.', 
           static_folder='.')

@app.route('/')
def index():
    """首页 - 单页面应用"""
    return render_template('index.html')

@app.route('/style.css')
def style():
    """提供CSS文件"""
    return send_from_directory('.', 'style.css', mimetype='text/css')

@app.route('/main.js')
def script():
    """提供JS文件"""
    return send_from_directory('.', 'main.js', mimetype='application/javascript')

if __name__ == '__main__':
    print("🚀 订单管理系统启动中...")
    print("📝 访问地址: http://localhost:8080")
    print("⚠️  按 Ctrl+C 停止服务器")
    app.run(debug=True, host='0.0.0.0', port=8080) 