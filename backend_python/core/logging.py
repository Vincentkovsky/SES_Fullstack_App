#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志配置模块

提供标准化的日志配置，支持控制台和文件输出，
包含请求跟踪和错误报告功能。
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

def setup_logging(log_level: str = None, log_dir: Optional[Path] = None) -> logging.Logger:
    """
    配置应用日志系统
    
    Args:
        log_level: 日志级别(DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录
        
    Returns:
        根日志记录器
    """
    # 确定日志级别
    log_level = log_level or os.getenv('LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # 清除可能存在的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建标准输出处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # 创建统一的格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加处理器到根日志记录器
    root_logger.addHandler(console_handler)
    
    # 如果指定了日志目录，添加文件处理器
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(exist_ok=True, parents=True)
        
        # 创建应用日志文件处理器(每个文件最大10MB，保留5个旧文件)
        file_handler = RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 创建错误日志文件处理器(仅记录ERROR及以上级别)
        error_handler = RotatingFileHandler(
            log_dir / 'error.log',
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    # 设置其他库的日志级别
    logging.getLogger('uvicorn').setLevel(numeric_level)
    logging.getLogger('uvicorn.access').setLevel(numeric_level)
    
    # 设置请求库的日志级别为WARNING(除非在调试模式)
    if numeric_level > logging.DEBUG:
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # 返回根日志记录器
    return root_logger

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """获取指定名称的日志记录器"""
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger 