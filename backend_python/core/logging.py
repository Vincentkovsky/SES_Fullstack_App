import logging
from typing import Optional

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """配置日志系统"""
    # 获取根日志记录器
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # 移除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 将处理器添加到logger
    logger.addHandler(console_handler)
    
    logger.info("日志系统已初始化")
    
    return logger

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """获取指定名称的日志记录器"""
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger 