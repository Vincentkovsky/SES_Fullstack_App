#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据索引管理工具

用于管理模拟数据和降雨数据的索引
支持两种类型的模拟：3Di模型和AI模型生成的模拟
"""

import os
import json
import glob
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from core.config import Config

logger = logging.getLogger(__name__)

class DataIndexManager:
    """数据索引管理类"""
    
    def __init__(self, index_file_path: Optional[Path] = None):
        """
        初始化数据索引管理器
        
        Args:
            index_file_path: 索引文件路径，如果不提供则使用默认路径
        """
        self.index_file_path = index_file_path or (Config.DATA_DIR / "index.json")
        self.index: Dict[str, List[Dict[str, Any]]] = {"simulations": [], "rainfall_events": []}
        
        # 初始加载索引
        self.load_index()
    
    def load_index(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        加载索引文件
        
        Returns:
            索引数据字典
        """
        if self.index_file_path.exists():
            try:
                with open(self.index_file_path, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
                logger.info(f"索引加载成功: {len(self.index.get('simulations', []))} 个模拟, {len(self.index.get('rainfall_events', []))} 个降雨事件")
            except Exception as e:
                logger.error(f"加载索引文件失败: {str(e)}")
                self.index = {"simulations": [], "rainfall_events": []}
        else:
            logger.warning(f"索引文件不存在，将创建新索引: {self.index_file_path}")
            self.index = {"simulations": [], "rainfall_events": []}
            
        return self.index
    
    def save_index(self) -> bool:
        """
        保存索引到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保父目录存在
            self.index_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.index_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
            
            logger.info(f"索引保存成功: {self.index_file_path}")
            return True
        except Exception as e:
            logger.error(f"保存索引文件失败: {str(e)}")
            return False
    
    def update_index(self) -> bool:
        """
        扫描目录并更新索引
        
        Returns:
            是否更新成功
        """
        # 首先加载现有索引
        self.load_index()
        
        # 获取现有ID列表，用于判断是否为新模拟
        existing_sim_ids = [sim['id'] for sim in self.index.get('simulations', [])]
        existing_rainfall_ids = [rain['id'] for rain in self.index.get('rainfall_events', [])]
        
        # 更新模拟数据索引
        self._update_simulations(existing_sim_ids)
        
        # 更新降雨事件索引
        self._update_rainfall_events(existing_rainfall_ids)
        
        # 保存更新后的索引
        return self.save_index()
    
    def _update_simulations(self, existing_sim_ids: List[str]):
        """
        更新模拟数据索引
        
        Args:
            existing_sim_ids: 现有模拟ID列表
        """
        # 处理3Di模拟
        self._scan_simulation_type("3di", existing_sim_ids)
        
        # 处理AI模型模拟
        self._scan_simulation_type("ai_model", existing_sim_ids)
    
    def _scan_simulation_type(self, sim_type: str, existing_sim_ids: List[str]):
        """
        扫描特定类型的模拟目录
        
        Args:
            sim_type: 模拟类型 (3di 或 ai_model)
            existing_sim_ids: 现有模拟ID列表
        """
        sim_type_dir = Config.DATA_DIR / sim_type
        
        if not sim_type_dir.exists():
            logger.warning(f"模拟类型目录不存在: {sim_type_dir}")
            return
        
        # 遍历该类型下的所有模拟目录
        for sim_dir in sim_type_dir.glob("*"):
            if not sim_dir.is_dir():
                continue
                
            sim_id = sim_dir.name
            
            # 检查是否为新的模拟
            if sim_id in existing_sim_ids:
                # 更新现有模拟的元数据
                self._update_existing_simulation(sim_id, sim_type, sim_dir)
            else:
                # 添加新的模拟
                self._add_new_simulation(sim_id, sim_type, sim_dir)
    
    def _update_existing_simulation(self, sim_id: str, sim_type: str, sim_dir: Path):
        """
        更新现有模拟的元数据
        
        Args:
            sim_id: 模拟ID
            sim_type: 模拟类型
            sim_dir: 模拟目录路径
        """
        # 查找现有模拟的索引
        for i, sim in enumerate(self.index.get('simulations', [])):
            if sim['id'] == sim_id:
                # 如果有元数据文件，使用它更新
                metadata_path = sim_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        # 合并元数据，保留原有字段
                        self.index['simulations'][i].update(metadata)
                        
                        # 确保类型正确
                        self.index['simulations'][i]['type'] = sim_type
                        
                        logger.info(f"更新了现有模拟的元数据: {sim_id}")
                    except Exception as e:
                        logger.error(f"读取模拟元数据失败 {sim_id}: {str(e)}")
                break
    
    def _add_new_simulation(self, sim_id: str, sim_type: str, sim_dir: Path):
        """
        添加新的模拟到索引
        
        Args:
            sim_id: 模拟ID
            sim_type: 模拟类型
            sim_dir: 模拟目录路径
        """
        # 首先检查是否有元数据文件
        metadata_path = sim_dir / "metadata.json"
        
        if metadata_path.exists():
            try:
                # 读取元数据
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # 确保包含必要的字段
                metadata['id'] = sim_id
                metadata['type'] = sim_type
                
                if 'name' not in metadata:
                    metadata['name'] = f"{sim_type.upper()} 模拟 {sim_id}"
                
                if 'date' not in metadata:
                    metadata['date'] = datetime.now().strftime("%Y-%m-%d")
                
                self.index.setdefault('simulations', []).append(metadata)
                logger.info(f"添加了新的模拟 (来自元数据): {sim_id}")
            except Exception as e:
                logger.error(f"读取模拟元数据失败 {sim_id}: {str(e)}")
                # 如果元数据读取失败，创建基本条目
                self._create_basic_simulation_entry(sim_id, sim_type, sim_dir)
        else:
            # 没有元数据文件，创建基本条目
            self._create_basic_simulation_entry(sim_id, sim_type, sim_dir)
    
    def _create_basic_simulation_entry(self, sim_id: str, sim_type: str, sim_dir: Path):
        """
        创建基本的模拟条目
        
        Args:
            sim_id: 模拟ID
            sim_type: 模拟类型
            sim_dir: 模拟目录路径
        """
        # 获取瓦片目录中的时间戳
        timestamps = []
        tiles_dir = sim_dir / "tiles"
        
        if tiles_dir.exists():
            timestamps = [d.name for d in tiles_dir.glob("*") if d.is_dir()]
        
        # 基本条目
        new_entry = {
            "id": sim_id,
            "type": sim_type,
            "name": f"{sim_type.upper()} 模拟 {sim_id}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"自动添加的{sim_type}模拟数据",
            "tile_timestamps": sorted(timestamps)
        }
        
        # 为不同类型添加特定属性
        if sim_type == "3di":
            new_entry["source"] = "3di_default"
        elif sim_type == "ai_model":
            new_entry["ai_model"] = "default_model"
            new_entry["confidence_score"] = 0.5  # 默认值
        
        # 保存元数据到模拟目录
        try:
            with open(sim_dir / "metadata.json", 'w', encoding='utf-8') as f:
                json.dump(new_entry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存模拟元数据失败 {sim_id}: {str(e)}")
        
        # 添加到索引
        self.index.setdefault('simulations', []).append(new_entry)
        logger.info(f"添加了新的模拟 (基本条目): {sim_id}")
    
    def _update_rainfall_events(self, existing_rainfall_ids: List[str]):
        """
        更新降雨事件索引
        
        Args:
            existing_rainfall_ids: 现有降雨事件ID列表
        """
        rainfall_dir = Config.DATA_DIR / "rainfall"
        
        if not rainfall_dir.exists():
            logger.warning(f"降雨数据目录不存在: {rainfall_dir}")
            return
        
        # 遍历所有降雨事件目录
        for event_dir in rainfall_dir.glob("*"):
            if not event_dir.is_dir():
                continue
                
            event_id = event_dir.name
            
            # 检查是否为新的降雨事件
            if event_id not in existing_rainfall_ids:
                # 添加新的降雨事件
                metadata_path = event_dir / "metadata.json"
                
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        # 确保包含必要的字段
                        metadata['id'] = event_id
                        
                        if 'name' not in metadata:
                            metadata['name'] = f"降雨事件 {event_id}"
                        
                        if 'date' not in metadata:
                            metadata['date'] = datetime.now().strftime("%Y-%m-%d")
                        
                        if 'file_path' not in metadata:
                            metadata['file_path'] = f"rainfall/{event_id}"
                        
                        self.index.setdefault('rainfall_events', []).append(metadata)
                        logger.info(f"添加了新的降雨事件 (来自元数据): {event_id}")
                    except Exception as e:
                        logger.error(f"读取降雨事件元数据失败 {event_id}: {str(e)}")
                        self._create_basic_rainfall_entry(event_id, event_dir)
                else:
                    # 没有元数据文件，创建基本条目
                    self._create_basic_rainfall_entry(event_id, event_dir)
    
    def _create_basic_rainfall_entry(self, event_id: str, event_dir: Path):
        """
        创建基本的降雨事件条目
        
        Args:
            event_id: 降雨事件ID
            event_dir: 降雨事件目录路径
        """
        new_entry = {
            "id": event_id,
            "name": f"降雨事件 {event_id}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "自动添加的降雨数据",
            "file_path": f"rainfall/{event_id}"
        }
        
        # 保存元数据到降雨事件目录
        try:
            with open(event_dir / "metadata.json", 'w', encoding='utf-8') as f:
                json.dump(new_entry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存降雨事件元数据失败 {event_id}: {str(e)}")
        
        # 添加到索引
        self.index.setdefault('rainfall_events', []).append(new_entry)
        logger.info(f"添加了新的降雨事件 (基本条目): {event_id}")
    
    def get_all_simulations(self) -> List[Dict[str, Any]]:
        """
        获取所有模拟列表
        
        Returns:
            模拟列表
        """
        return self.index.get('simulations', [])
    
    def get_simulations_by_type(self, sim_type: str) -> List[Dict[str, Any]]:
        """
        获取特定类型的模拟列表
        
        Args:
            sim_type: 模拟类型 (3di 或 ai_model)
            
        Returns:
            模拟列表
        """
        return [sim for sim in self.index.get('simulations', []) if sim.get('type') == sim_type]
    
    def get_simulation_by_id(self, sim_id: str) -> Optional[Dict[str, Any]]:
        """
        获取特定ID的模拟
        
        Args:
            sim_id: 模拟ID
            
        Returns:
            模拟数据，如果不存在则返回None
        """
        for sim in self.index.get('simulations', []):
            if sim.get('id') == sim_id:
                return sim
        return None
    
    def get_all_rainfall_events(self) -> List[Dict[str, Any]]:
        """
        获取所有降雨事件列表
        
        Returns:
            降雨事件列表
        """
        return self.index.get('rainfall_events', [])
    
    def get_rainfall_by_id(self, rainfall_id: str) -> Optional[Dict[str, Any]]:
        """
        获取特定ID的降雨事件
        
        Args:
            rainfall_id: 降雨事件ID
            
        Returns:
            降雨事件数据，如果不存在则返回None
        """
        for rain in self.index.get('rainfall_events', []):
            if rain.get('id') == rainfall_id:
                return rain
        return None
    
    def add_simulation(self, simulation_data: Dict[str, Any]) -> bool:
        """
        添加新的模拟
        
        Args:
            simulation_data: 模拟数据
            
        Returns:
            是否添加成功
        """
        if 'id' not in simulation_data:
            logger.error("添加模拟失败: 缺少ID字段")
            return False
        
        sim_id = simulation_data['id']
        
        # 检查ID是否已存在
        if any(sim['id'] == sim_id for sim in self.index.get('simulations', [])):
            logger.error(f"添加模拟失败: ID已存在 - {sim_id}")
            return False
        
        # 确保类型字段存在
        if 'type' not in simulation_data:
            simulation_data['type'] = '3di'  # 默认为3di类型
        
        # 添加到索引
        self.index.setdefault('simulations', []).append(simulation_data)
        
        # 保存索引
        if self.save_index():
            logger.info(f"成功添加新的模拟: {sim_id}")
            return True
        else:
            logger.error(f"保存索引失败，模拟添加失败: {sim_id}")
            return False
    
    def update_simulation(self, sim_id: str, simulation_data: Dict[str, Any]) -> bool:
        """
        更新模拟数据
        
        Args:
            sim_id: 模拟ID
            simulation_data: 更新的模拟数据
            
        Returns:
            是否更新成功
        """
        # 查找要更新的模拟
        for i, sim in enumerate(self.index.get('simulations', [])):
            if sim.get('id') == sim_id:
                # 保留原始ID
                simulation_data['id'] = sim_id
                
                # 更新数据
                self.index['simulations'][i].update(simulation_data)
                
                # 保存索引
                if self.save_index():
                    logger.info(f"成功更新模拟: {sim_id}")
                    return True
                else:
                    logger.error(f"保存索引失败，模拟更新失败: {sim_id}")
                    return False
        
        logger.error(f"更新模拟失败: 未找到ID - {sim_id}")
        return False


# 可执行命令行脚本
if __name__ == "__main__":
    import argparse
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='数据索引管理工具')
    parser.add_argument('--update', action='store_true', help='更新索引')
    parser.add_argument('--list', action='store_true', help='列出所有模拟和降雨事件')
    parser.add_argument('--list-simulations', action='store_true', help='列出所有模拟')
    parser.add_argument('--list-rainfall', action='store_true', help='列出所有降雨事件')
    parser.add_argument('--type', choices=['3di', 'ai_model'], help='按类型筛选模拟')
    
    args = parser.parse_args()
    
    # 创建索引管理器实例
    manager = DataIndexManager()
    
    # 处理命令
    if args.update:
        print("正在更新索引...")
        if manager.update_index():
            print("索引更新成功")
        else:
            print("索引更新失败")
    
    if args.list or args.list_simulations:
        print("\n模拟列表:")
        simulations = manager.get_simulations_by_type(args.type) if args.type else manager.get_all_simulations()
        
        if not simulations:
            print("  (无模拟数据)")
        else:
            for sim in simulations:
                print(f"  {sim['id']} [{sim.get('type', 'unknown')}] - {sim.get('name', 'No Name')}")
                print(f"    描述: {sim.get('description', 'No description')}")
                if 'time_range' in sim:
                    print(f"    时间范围: {sim['time_range'][0]} 到 {sim['time_range'][1]}")
                print(f"    类型: {sim.get('type', 'unknown')}")
                print("")
    
    if args.list or args.list_rainfall:
        print("\n降雨事件列表:")
        rainfall_events = manager.get_all_rainfall_events()
        
        if not rainfall_events:
            print("  (无降雨数据)")
        else:
            for rain in rainfall_events:
                print(f"  {rain['id']} - {rain.get('name', 'No Name')}")
                print(f"    描述: {rain.get('description', 'No description')}")
                print(f"    日期: {rain.get('date', 'Unknown date')}")
                print("") 