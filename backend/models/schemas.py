#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic数据模型定义
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class GetOrdersRequest(BaseModel):
    """获取订单请求模型"""
    x_request_sign: str
    x_request_timestamp: str
    authorization: str
    limit: Optional[int] = 30
    last_id: Optional[str] = None

class OrderResponse(BaseModel):
    """订单响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    total_orders: Optional[int] = None
    last_id: Optional[str] = None

