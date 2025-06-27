#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单相关路由
"""

from fastapi import APIRouter, HTTPException
from ..models.schemas import GetOrdersRequest, OrderResponse
from ..models.services import fetch_orders_from_api
from ..models.database import save_orders_to_database, get_order_count, get_record_count

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
        
        # 如果API请求成功，自动保存到数据库
        db_result = save_orders_to_database(result_data["orders"])
        message = f"获取订单数据成功，{db_result['message']}"
        
        return OrderResponse(
            success=True,
            message=message,
            data=result_data,
            total_orders=result_data["pagination"]["count"],
            last_id=result_data["pagination"]["last_id"]
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "验签失败" in error_msg:
            raise HTTPException(status_code=401, detail="签名失效，请更新签名")
        else:
            raise HTTPException(status_code=400, detail=error_msg)

@router.get("/db-stats")
async def get_database_stats():
    """获取数据库统计信息"""
    try:
        order_count = get_order_count()
        record_count = get_record_count()
        
        return {
            "success": True,
            "message": "获取数据库统计信息成功",
            "data": {
                "total_orders": order_count,
                "total_records": record_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}") 