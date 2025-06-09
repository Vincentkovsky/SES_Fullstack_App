#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FastAPI辅助函数模块
提供用于FastAPI应用程序的实用工具和装饰器
"""

import logging
import functools
import traceback
import time
from datetime import datetime
from typing import Callable, Any, Dict, TypeVar, Awaitable
from fastapi import HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 类型变量，用于泛型函数
T = TypeVar('T')

def async_handle_exceptions(func: Callable) -> Callable:
    """
    异步函数异常处理装饰器
    
    捕获异步路由函数中的异常，并返回标准化的错误响应
    
    Args:
        func: 要装饰的异步函数
        
    Returns:
        装饰后的函数
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Dict[str, Any]:
        try:
            return await func(*args, **kwargs)
        except HTTPException as e:
            # 重新抛出FastAPI的HTTP异常
            raise e
        except Exception as e:
            # 记录异常
            error_details = traceback.format_exc()
            logger.error(f"异步路由发生错误: {str(e)}\n{error_details}")
            
            # 返回标准化错误响应
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": "内部服务器错误",
                    "message": str(e)
                }
            )
    
    return wrapper

class StandardResponse(BaseModel):
    """标准API响应模型"""
    success: bool
    data: Any = None
    message: str = ""
    error: str = ""
    processing_time_ms: int = 0

def create_success_response(data: Any = None, message: str = "操作成功", processing_time_ms: int = 0) -> Dict[str, Any]:
    """
    创建标准成功响应

    Args:
        data: 响应数据
        message: 成功消息
        processing_time_ms: 处理时间（毫秒）

    Returns:
        标准响应字典
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "error": "",
        "processing_time_ms": processing_time_ms
    }

def create_error_response(error: str, status_code: int = 500, processing_time_ms: int = 0) -> Dict[str, Any]:
    """
    创建标准错误响应

    Args:
        error: 错误消息
        status_code: HTTP状态码
        processing_time_ms: 处理时间（毫秒）

    Returns:
        标准响应字典
    """
    return {
        "success": False,
        "data": None,
        "message": "",
        "error": error,
        "processing_time_ms": processing_time_ms
    }

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    记录所有HTTP请求的详细信息、响应状态和处理时间
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        处理请求并记录日志
        
        Args:
            request: FastAPI请求对象
            call_next: 调用链中的下一个中间件或处理函数
            
        Returns:
            FastAPI响应对象
        """
        # 记录请求开始时间
        start_time = time.time()
        
        # 生成请求ID
        request_id = f"{int(time.time() * 1000)}-{id(request)}"
        
        # 记录请求信息
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            f"开始处理请求 [ID:{request_id}] - {request.method} {request.url.path} "
            f"来自 {client_host} - 查询参数: {dict(request.query_params)}"
        )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 添加处理时间响应头
            response.headers["X-Process-Time"] = str(process_time)
            
            # 记录响应信息
            logger.info(
                f"请求完成 [ID:{request_id}] - {request.method} {request.url.path} "
                f"- 状态码: {response.status_code} - 处理时间: {process_time:.4f}秒"
            )
            
            return response
            
        except Exception as e:
            # 记录异常信息
            process_time = time.time() - start_time
            logger.error(
                f"请求处理出错 [ID:{request_id}] - {request.method} {request.url.path} "
                f"- 错误: {str(e)} - 处理时间: {process_time:.4f}秒"
            )
            logger.error(traceback.format_exc())
            
            # 重新抛出异常，让异常处理程序处理
            raise

def get_timestamp() -> str:
    """
    获取当前时间戳，格式为ISO 8601
    
    Returns:
        格式化的时间戳字符串
    """
    return datetime.now().isoformat()

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    处理HTTP异常
    
    Args:
        request: FastAPI请求对象
        exc: HTTP异常
        
    Returns:
        标准化的JSON响应
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            error=str(exc.detail),
            status_code=exc.status_code
        )
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    处理请求验证异常
    
    Args:
        request: FastAPI请求对象
        exc: 验证异常
        
    Returns:
        标准化的JSON响应
    """
    # 提取错误详情
    errors = []
    for error in exc.errors():
        loc = " -> ".join([str(loc_item) for loc_item in error.get("loc", [])])
        msg = error.get("msg", "")
        errors.append(f"{loc}: {msg}")
    
    error_msg = "请求验证失败: " + "; ".join(errors)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            error=error_msg,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    处理通用异常
    
    Args:
        request: FastAPI请求对象
        exc: 通用异常
        
    Returns:
        标准化的JSON响应
    """
    # 记录详细错误信息
    logger.error(f"未处理的异常: {str(exc)}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            error=f"服务器内部错误: {str(exc)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    ) 