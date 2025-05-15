#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FastAPI 应用主入口

提供高性能的 REST API 服务。
使用 ASGI 服务器和异步处理提高并发能力。
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn
from dotenv import load_dotenv
import os
import asyncio
from typing import List, Dict, Any

# 导入自定义模块
from core.config import Config
from core.logging import setup_logging
from core.fastapi_helpers import (
    RequestLoggingMiddleware,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
    get_timestamp
)

# 导入API路由
from api_fastapi import (
    water_depth_router,
    inference_router,
    gauging_router,
    cache_router,
    health_router,
    raster_router
)

# 加载环境变量
load_dotenv()

# 设置日志
logger = setup_logging()

def create_app() -> FastAPI:
    """
    创建并配置FastAPI应用
    
    Returns:
        FastAPI: 配置好的FastAPI应用实例
    """
    # 创建FastAPI应用
    app = FastAPI(
        title="水深度API服务",
        description="提供水深度数据和相关服务的REST API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # 添加中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.CORS_ORIGINS.split(','),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加请求日志中间件
    app.add_middleware(RequestLoggingMiddleware)
    
    # 添加异常处理
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    # 注册所有路由
    app.include_router(health_router, tags=["健康检查"])
    app.include_router(water_depth_router, tags=["水深度"])
    app.include_router(inference_router, tags=["推理"])
    app.include_router(gauging_router, tags=["测量站"])
    app.include_router(cache_router, tags=["缓存"])
    app.include_router(raster_router, tags=["栅格数据"])
    
    # 添加根路由
    @app.get("/", tags=["首页"])
    async def index() -> Dict[str, Any]:
        """首页路由"""
        return {
            "message": "欢迎使用水深度API服务",
            "status": "运行中",
            "api_version": "1.0",
            "timestamp": get_timestamp()
        }
    
    # 添加启动事件
    @app.on_event("startup")
    async def startup_event():
        """应用启动时执行"""
        logger.info("应用启动中...")
        
        # 创建必要的数据目录
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.DATA_DIR / "3di_res", exist_ok=True)
        os.makedirs(Config.DATA_DIR / "3di_res/geotiff", exist_ok=True)
        
        logger.info("应用启动完成")
    
    # 添加关闭事件
    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭时执行"""
        logger.info("应用关闭中...")
        
        try:
            # 清理资源
            # 获取当前任务
            current_task = asyncio.current_task()
            
            # 获取所有异步任务，但排除当前关闭任务
            pending = [task for task in asyncio.all_tasks() 
                      if task is not current_task and not task.done()]
            
            if pending:
                logger.info(f"等待 {len(pending)} 个异步任务完成（最多5秒）...")
                # 设置超时，最多等待5秒
                try:
                    # 取消所有任务并等待它们完成
                    for task in pending:
                        task.cancel()
                    # 使用超时等待任务完成
                    await asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("等待任务超时，强制关闭")
                except Exception as e:
                    logger.error(f"等待任务完成时出错: {str(e)}")
        except Exception as e:
            logger.error(f"关闭过程中出错: {str(e)}")
        
        logger.info("应用已关闭")
    
    return app

if __name__ == "__main__":
    # 验证配置
    if not Config.validate():
        logger.warning("配置验证失败，但应用仍将继续启动。某些功能可能不可用。")
    
    # 获取运行配置
    host = Config.HOST
    port = Config.PORT
    reload = Config.DEBUG
    workers = os.getenv("API_WORKERS", "4")  # 默认4个工作进程
    
    # 显示应用配置信息
    logger.info(f"启动应用 - 模式: {'调试' if Config.DEBUG else '生产'}, 地址: {host}:{port}, 工作进程: {workers}")
    
    # 创建并运行应用
    app = create_app()
    
    # 使用Uvicorn运行FastAPI应用
    uvicorn.run(
        "fastapi_app:create_app",
        host=host,
        port=port,
        reload=reload,
        workers=int(workers),
        factory=True,
        log_level="info" if not Config.DEBUG else "debug"
    ) 