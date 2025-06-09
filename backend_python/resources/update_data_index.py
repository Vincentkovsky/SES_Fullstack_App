#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据索引更新脚本

用于更新数据索引，扫描目录并添加新的模拟和降雨事件到索引中
可以作为定时任务运行，定期更新索引
"""

import argparse
import logging
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("update_index.log")
    ]
)
logger = logging.getLogger(__name__)

# 添加父目录到路径，以便导入utils模块
sys.path.append(str(Path(__file__).parent.parent))

from utils.data_index_manager import DataIndexManager

def update_index(force_refresh: bool = False, verbose: bool = False):
    """
    更新数据索引
    
    Args:
        force_refresh: 是否强制刷新索引
        verbose: 是否输出详细信息
    """
    if verbose:
        logger.info("开始更新数据索引...")
    
    # 创建数据索引管理器
    manager = DataIndexManager()
    
    if force_refresh:
        # 强制刷新时，创建新的索引
        if verbose:
            logger.info("强制刷新索引文件...")
        
        # 清空索引
        manager.index = {"simulations": [], "rainfall_events": []}
    
    # 更新索引
    result = manager.update_index()
    
    if result:
        if verbose:
            logger.info(f"索引更新成功: {len(manager.get_all_simulations())} 个模拟, {len(manager.get_all_rainfall_events())} 个降雨事件")
        
        # 打印模拟列表
        if verbose:
            simulations = manager.get_all_simulations()
            if simulations:
                logger.info("模拟列表:")
                for sim in simulations:
                    logger.info(f"  {sim['id']} [{sim.get('type', 'unknown')}] - {sim.get('name', 'No Name')}")
            else:
                logger.info("没有找到模拟数据")
        
            # 打印降雨事件列表
            rainfall_events = manager.get_all_rainfall_events()
            if rainfall_events:
                logger.info("降雨事件列表:")
                for rain in rainfall_events:
                    logger.info(f"  {rain['id']} - {rain.get('name', 'No Name')}")
            else:
                logger.info("没有找到降雨事件数据")
    else:
        logger.error("索引更新失败")

if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='数据索引更新脚本')
    parser.add_argument('--force-refresh', action='store_true', help='强制刷新索引，删除现有索引并重新创建')
    parser.add_argument('--verbose', action='store_true', help='输出详细信息')
    
    args = parser.parse_args()
    
    # 执行更新
    update_index(args.force_refresh, args.verbose) 