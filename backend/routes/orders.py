#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单相关路由
"""

from fastapi import APIRouter, HTTPException
from ..models.schemas import GetOrdersRequest, OrderResponse
from ..models.services import fetch_orders_from_api

router = APIRouter(prefix="/api", tags=["orders"])

@router.post("/get-orders", response_model=OrderResponse)
async def get_orders(request: GetOrdersRequest):
    """获取订单数据接口"""
    try:
        result_data = fetch_orders_from_api(
            x_request_sign=request.x_request_sign,
            x_request_timestamp=request.x_request_timestamp,
            authorization=request.authorization,
            limit=request.limit,
            last_id=request.last_id
        )
        
        return OrderResponse(
            success=True,
            message="获取订单数据成功",
            data=result_data,
            total_orders=result_data["pagination"]["count"]
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"文件不存在: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}") 