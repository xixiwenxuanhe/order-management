#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单相关路由
"""

from fastapi import APIRouter, HTTPException
from ..models.schemas import GetOrdersRequest, GetOrdersWithTargetRequest, OrderResponse, GetOrderDetailsRequest, OrderDetailsResponse
from ..models.services import fetch_orders_from_api, fetch_order_details_from_api
from ..models.database import save_orders_to_database, get_order_count, get_record_count, get_orders_need_details, get_database_status

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
        db_result = save_orders_to_database(result_data["orders"], result_data["raw_orders"])
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

@router.post("/get-orders-with-target", response_model=OrderResponse)
async def get_orders_with_target(request: GetOrdersWithTargetRequest):
    """获取订单数据接口（带目标ID过滤）- 只保存ID大于target_order_id的订单"""
    try:
        result_data = fetch_orders_from_api(
            x_request_sign=request.x_request_sign,
            x_request_timestamp=request.x_request_timestamp,
            authorization=request.authorization,
            limit=request.limit,
            last_id=request.last_id
        )
        
        # 过滤订单数据，只保留ID大于target_order_id的订单
        def compare_order_ids(order_id1, order_id2):
            """比较两个订单ID的大小（作为数字比较）"""
            return int(order_id1) - int(order_id2)
        
        # 过滤订单和原始订单数据
        filtered_orders = []
        filtered_raw_orders = []
        original_count = len(result_data["orders"])
        found_target_or_smaller = False  # 新增：是否找到目标ID或更小的ID
        
        for i, order in enumerate(result_data["orders"]):
            order_info = order.get('orderInfo', {})
            current_order_id = order_info.get('orderId', '')
            
            if current_order_id:
                comparison = compare_order_ids(current_order_id, request.target_order_id)
                if comparison > 0:  # 只保留ID大于target_order_id的订单
                    filtered_orders.append(order)
                    # 同时过滤对应的原始订单数据
                    if i < len(result_data["raw_orders"]):
                        filtered_raw_orders.append(result_data["raw_orders"][i])
                elif comparison <= 0:  # 找到目标ID或更小的ID
                    found_target_or_smaller = True
        
        # 如果有过滤后的订单，保存到数据库
        if filtered_orders:
            db_result = save_orders_to_database(filtered_orders, filtered_raw_orders)
            message = f"获取订单数据成功，从 {original_count} 个订单中筛选出 {len(filtered_orders)} 个新订单，{db_result['message']}"
        else:
            message = f"获取订单数据成功，从 {original_count} 个订单中未找到ID大于 {request.target_order_id} 的新订单"
            db_result = {
                "saved_records": 0,
                "orders_need_details_count": 0
            }
        
        # 在返回的data中添加found_target_or_smaller字段
        response_data = result_data.copy()
        response_data["found_target_or_smaller"] = found_target_or_smaller
        
        return OrderResponse(
            success=True,
            message=message,
            data=response_data,  # 返回包含found_target_or_smaller的数据
            total_orders=result_data["pagination"]["count"],
            last_id=result_data["pagination"]["last_id"]
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "验签失败" in error_msg:
            raise HTTPException(status_code=401, detail="签名失效，请更新签名")
        else:
            raise HTTPException(status_code=400, detail=error_msg)

@router.post("/get-order-details", response_model=OrderDetailsResponse)
async def get_order_details(request: GetOrderDetailsRequest):
    """获取订单详情接口"""
    try:
        result_data = fetch_order_details_from_api(
            x_request_sign=request.x_request_sign,
            x_request_timestamp=request.x_request_timestamp,
            authorization=request.authorization,
            order_id=request.order_id
        )
        
        return OrderDetailsResponse(
            success=True,
            message=f"获取订单详情成功，订单ID: {request.order_id}",
            data=result_data
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "验签失败" in error_msg:
            raise HTTPException(status_code=401, detail="签名失效，请更新签名")
        else:
            raise HTTPException(status_code=400, detail=error_msg)

@router.get("/orders-need-details")
async def get_orders_need_details_list():
    """获取需要详细显示的订单列表"""
    try:
        orders = get_orders_need_details()
        
        return {
            "success": True,
            "message": f"获取需要详细显示的订单列表成功，共 {len(orders)} 个订单",
            "data": {
                "orders": orders,
                "count": len(orders)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取订单列表失败: {str(e)}")

@router.get("/db-stats")
async def get_database_stats():
    """获取数据库统计信息"""
    try:
        status = get_database_status()
        need_details_orders = get_orders_need_details()
        
        return {
            "success": True,
            "message": "获取数据库统计信息成功",
            "data": {
                "total_orders": status["total_orders"],
                "total_records": status["total_records"],
                "latest_time": status["latest_time"],
                "latest_order_id": status["latest_order_id"],
                "incomplete_earliest_time": status["incomplete_earliest_time"],
                "incomplete_earliest_order_id": status["incomplete_earliest_order_id"],
                "incomplete_order_ids": status["incomplete_order_ids"],
                "incomplete_orders_count": len(status["incomplete_order_ids"]),
                "orders_need_details": len(need_details_orders)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

 