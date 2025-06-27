#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理API服务主入口
"""

from fastapi import FastAPI
from datetime import datetime
from .routes.orders import router as orders_router

app = FastAPI(
    title="订单管理API", 
    description="订单数据获取和管理接口",
    version="1.0.0"
)

# 注册路由
app.include_router(orders_router)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "订单管理API服务",
        "version": "1.0.0",
        "endpoints": {
            "get_orders": "/api/get-orders",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 