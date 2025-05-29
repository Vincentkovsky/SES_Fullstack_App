#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据结构迁移工具

用于将旧的数据结构迁移到新的目录结构
支持3Di模拟数据和AI模型生成的模拟数据
"""

import os
import shutil
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 配置日志
logging.basicConfig(level=logging.INFO, 
                     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入的路径需要根据执行环境动态调整
import sys
sys.path.append(str(Path(__file__).parent.parent))
from core.config import Config
from utils.data_index_manager import DataIndexManager

class DataMigrator:
    """数据迁移类"""
    
    def __init__(self, old_data_dir: Optional[Path] = None, dry_run: bool = False):
        """
        初始化数据迁移器
        
        Args:
            old_data_dir: 旧数据目录路径，如果不提供则使用默认路径
            dry_run: 是否只打印操作而不实际执行
        """
        self.old_data_dir = old_data_dir or (Path(__file__).parent.parent / "data/3di_res")
        self.new_data_dir = Config.DATA_DIR
        self.dry_run = dry_run
        self.data_index_manager = DataIndexManager()
        
        # 记录迁移的文件和目录
        self.migrated_simulations = []
        self.migrated_files = []
        self.errors = []
    
    def migrate(self) -> bool:
        """
        执行数据迁移
        
        Returns:
            是否迁移成功
        """
        logger.info(f"开始数据迁移，{'[DRY RUN]' if self.dry_run else ''}")
        logger.info(f"源数据目录: {self.old_data_dir}")
        logger.info(f"目标数据目录: {self.new_data_dir}")
        
        try:
            # 1. 创建新的目录结构
            self._create_new_directory_structure()
            
            # 2. 迁移模拟数据
            self._migrate_simulations()
            
            # 3. 迁移参考数据
            self._migrate_reference_data()
            
            # 4. 更新索引
            if not self.dry_run:
                self.data_index_manager.update_index()
            
            # 5. 记录迁移日志
            self._write_migration_log()
            
            logger.info(f"数据迁移完成: 迁移了 {len(self.migrated_simulations)} 个模拟，{len(self.migrated_files)} 个文件，{len(self.errors)} 个错误")
            return True
        except Exception as e:
            logger.error(f"数据迁移失败: {str(e)}")
            return False
    
    def _create_new_directory_structure(self):
        """创建新的目录结构"""
        dirs_to_create = [
            self.new_data_dir / "3di",
            self.new_data_dir / "ai_model",
            self.new_data_dir / "reference",
            self.new_data_dir / "rainfall"
        ]
        
        for dir_path in dirs_to_create:
            if not dir_path.exists():
                logger.info(f"创建目录: {dir_path}")
                if not self.dry_run:
                    dir_path.mkdir(parents=True, exist_ok=True)
    
    def _migrate_simulations(self):
        """迁移模拟数据"""
        # 检查旧的tiles目录
        old_tiles_dir = self.old_data_dir / "tiles"
        if not old_tiles_dir.exists():
            logger.warning(f"旧的tiles目录不存在: {old_tiles_dir}")
            return
        
        # 默认将所有旧的模拟视为3Di模拟
        sim_type = "3di"
        
        # 遍历旧的tiles目录中的所有模拟
        for sim_dir in old_tiles_dir.glob("*"):
            if not sim_dir.is_dir():
                continue
                
            sim_id = sim_dir.name
            logger.info(f"开始迁移模拟: {sim_id} (类型: {sim_type})")
            
            # 创建新的模拟目录结构
            new_sim_dir = self.new_data_dir / sim_type / sim_id
            new_tiles_dir = new_sim_dir / "tiles"
            new_geotiff_dir = new_sim_dir / "geotiff"
            new_netcdf_dir = new_sim_dir / "netcdf"
            
            if not self.dry_run:
                new_sim_dir.mkdir(parents=True, exist_ok=True)
                new_tiles_dir.mkdir(exist_ok=True)
                new_geotiff_dir.mkdir(exist_ok=True)
                new_netcdf_dir.mkdir(exist_ok=True)
            
            # 复制瓦片数据
            logger.info(f"复制瓦片数据: {sim_dir} -> {new_tiles_dir}")
            
            if not self.dry_run:
                # 复制所有文件和子目录
                for item in sim_dir.glob("*"):
                    if item.is_dir():
                        dst_dir = new_tiles_dir / item.name
                        if not dst_dir.exists():
                            shutil.copytree(item, dst_dir)
                    else:
                        dst_file = new_tiles_dir / item.name
                        if not dst_file.exists():
                            shutil.copy2(item, dst_file)
            
            # 检查是否有对应的GeoTIFF文件
            old_geotiff_dir = self.old_data_dir / "geotiff" / sim_id
            if old_geotiff_dir.exists():
                logger.info(f"复制GeoTIFF数据: {old_geotiff_dir} -> {new_geotiff_dir}")
                
                if not self.dry_run:
                    for item in old_geotiff_dir.glob("*"):
                        dst_file = new_geotiff_dir / item.name
                        if not dst_file.exists():
                            if item.is_file():
                                shutil.copy2(item, dst_file)
                            else:
                                shutil.copytree(item, dst_file)
            
            # 检查是否有对应的NetCDF文件
            old_netcdf_dir = self.old_data_dir / "netcdf"
            if old_netcdf_dir.exists():
                # 查找可能匹配的NetCDF文件
                for nc_file in old_netcdf_dir.glob("*.nc"):
                    if sim_id in nc_file.name:
                        logger.info(f"复制NetCDF文件: {nc_file} -> {new_netcdf_dir}")
                        
                        if not self.dry_run:
                            dst_file = new_netcdf_dir / nc_file.name
                            if not dst_file.exists():
                                shutil.copy2(nc_file, dst_file)
            
            # 生成元数据文件
            metadata = {
                "id": sim_id,
                "type": sim_type,
                "name": f"3Di模拟 {sim_id}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "description": f"从旧数据结构迁移的{sim_type}模拟",
                "source": "3di_model",
                "migrated": True,
                "migrated_at": datetime.now().isoformat()
            }
            
            # 获取瓦片目录中的时间戳
            if new_tiles_dir.exists():
                timestamps = [d.name for d in new_tiles_dir.glob("*") if d.is_dir()]
                metadata["tile_timestamps"] = sorted(timestamps)
            
            # 保存元数据
            metadata_path = new_sim_dir / "metadata.json"
            logger.info(f"创建元数据文件: {metadata_path}")
            
            if not self.dry_run:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 记录迁移的模拟
            self.migrated_simulations.append({
                "id": sim_id,
                "type": sim_type,
                "source": str(sim_dir),
                "destination": str(new_sim_dir)
            })
    
    def _migrate_reference_data(self):
        """迁移参考数据"""
        reference_files = [
            "color.txt",
            "5m_dem.tif",
            "10m_dem.tif",
            "20m_dem.tif",
            "gridadmin.h5"
        ]
        
        for file_name in reference_files:
            src_file = self.old_data_dir / file_name
            if src_file.exists():
                dst_file = Config.REFERENCE_DATA_DIR / file_name
                logger.info(f"复制参考数据: {src_file} -> {dst_file}")
                
                if not self.dry_run and not dst_file.exists():
                    shutil.copy2(src_file, dst_file)
                
                # 记录迁移的文件
                self.migrated_files.append({
                    "name": file_name,
                    "source": str(src_file),
                    "destination": str(dst_file)
                })
                
                # 同时复制辅助文件
                aux_file = src_file.with_suffix(src_file.suffix + ".aux.xml")
                if aux_file.exists():
                    dst_aux = dst_file.with_suffix(dst_file.suffix + ".aux.xml")
                    logger.info(f"复制辅助文件: {aux_file} -> {dst_aux}")
                    
                    if not self.dry_run and not dst_aux.exists():
                        shutil.copy2(aux_file, dst_aux)
                    
                    self.migrated_files.append({
                        "name": aux_file.name,
                        "source": str(aux_file),
                        "destination": str(dst_aux)
                    })
    
    def _write_migration_log(self):
        """记录迁移日志"""
        log_data = {
            "migration_date": datetime.now().isoformat(),
            "old_data_dir": str(self.old_data_dir),
            "new_data_dir": str(self.new_data_dir),
            "simulations": self.migrated_simulations,
            "reference_files": self.migrated_files,
            "errors": self.errors
        }
        
        log_path = self.new_data_dir / "migration_log.json"
        logger.info(f"保存迁移日志: {log_path}")
        
        if not self.dry_run:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='数据结构迁移工具')
    parser.add_argument('--old-data-dir', type=str, help='旧数据目录路径')
    parser.add_argument('--dry-run', action='store_true', help='只打印操作而不实际执行')
    
    args = parser.parse_args()
    
    # 创建迁移器实例
    old_data_dir = Path(args.old_data_dir) if args.old_data_dir else None
    migrator = DataMigrator(old_data_dir, args.dry_run)
    
    # 执行迁移
    success = migrator.migrate()
    
    # 退出码
    sys.exit(0 if success else 1) 