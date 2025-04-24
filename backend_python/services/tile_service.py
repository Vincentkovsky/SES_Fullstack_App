import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from backend_python.core.config import Config
from backend_python.services.inference_service import get_latest_inference_dir

logger = logging.getLogger(__name__)

class TileService:
    """瓦片服务类"""
    
    @staticmethod
    def get_tiles_list(is_steed_mode: bool = False, simulation: Optional[str] = None) -> Tuple[List[str], int, str]:
        """
        获取瓦片时间戳列表
        
        Args:
            is_steed_mode: 是否处于STEED模式
            simulation: 模拟ID (仅在非STEED模式下使用)
            
        Returns:
            Tuple[List[str], int, str]: 时间戳列表、HTTP状态码、错误消息
        """
        timestamps = []
        status_code = 200
        error_message = ""
        
        if is_steed_mode:
            # STEED模式: 使用推理输出目录
            latest_inference_dir = get_latest_inference_dir()
            
            if not latest_inference_dir:
                return [], 404, "STEED模式下没有可用的瓦片"

            # 获取最新的推理目录名称
            latest_inference = latest_inference_dir.name
            tiles_path = latest_inference_dir / f"timeseries_tiles_{latest_inference}"
            
            if not tiles_path.exists():
                return [], 404, "STEED模式下瓦片尚未生成"
                
            # 列出瓦片目录中的所有时间戳
            timestamps = sorted(
                name for name in os.listdir(tiles_path)
                if (tiles_path / name).is_dir()
            )
        else:
            # 处理特殊的字符串值
            if simulation in ["null", "undefined", ""] or simulation is None:
                return [], 400, "本地模式下必须指定simulation参数"
                
            # 使用指定的历史模拟目录
            tiles_path = Path(Config.DATA_DIR) / "3di_res/tiles" / simulation
            if not tiles_path.exists():
                return [], 404, f"未找到指定的历史模拟: {simulation}"
                
            timestamps = sorted(
                name for name in os.listdir(tiles_path)
                if (tiles_path / name).is_dir()
            )
        
        return timestamps, status_code, error_message

    @staticmethod
    def get_tile_path(timestamp: str, z: str, x: str, y: str, is_steed_mode: bool = False, simulation: Optional[str] = None) -> Tuple[Optional[Path], int, str]:
        """
        获取瓦片文件路径
        
        Args:
            timestamp: 时间戳
            z: 缩放级别
            x: X坐标
            y: Y坐标
            is_steed_mode: 是否处于STEED模式
            simulation: 模拟ID (仅在非STEED模式下使用)
            
        Returns:
            Tuple[Optional[Path], int, str]: 瓦片路径、HTTP状态码、错误消息
        """
        if is_steed_mode:
            # STEED模式: 使用推理输出目录
            latest_inference_dir = get_latest_inference_dir()
            
            if latest_inference_dir:
                latest_inference = latest_inference_dir.name
                tile_path = (
                    latest_inference_dir
                    / f"timeseries_tiles_{latest_inference}"
                    / timestamp
                    / z
                    / x
                    / f"{y}.png"
                )

                if tile_path.exists():
                    return tile_path, 200, ""
            
            return None, 404, "STEED模式下未找到瓦片"
        else:
            # 处理特殊的字符串值
            if simulation in ["null", "undefined", ""] or simulation is None:
                return None, 400, "本地模式下必须指定simulation参数"
            
            # 使用指定的历史模拟目录
            tile_path = (
                Path(Config.DATA_DIR) / "3di_res/tiles"
                / simulation
                / timestamp
                / z
                / x
                / f"{y}.png"
            )
            
            logger.info(f"瓦片路径 (simulation={simulation}): {tile_path}")
            
            if tile_path.exists():
                return tile_path, 200, ""
                
            return None, 404, f"未找到瓦片 (simulation={simulation})"

    @staticmethod
    def get_historical_simulations() -> List[str]:
        """
        获取历史模拟列表
        
        Returns:
            List[str]: 历史模拟ID列表
        """
        tiles_path = Path(Config.DATA_DIR) / "3di_res/tiles"
        if not tiles_path.exists():
            return []
            
        # 列出历史模拟目录中的所有文件夹
        simulations = sorted(
            name for name in os.listdir(tiles_path)
            if (tiles_path / name).is_dir()
        )
        
        return simulations 