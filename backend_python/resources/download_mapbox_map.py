#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mapbox地图下载脚本

此脚本用于下载指定EPSG:32755坐标系下的Mapbox地图图片，
使用Mapbox的静态地图API获取地图图像。
"""

import os
import math
import json
import logging
import requests
from PIL import Image
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import numpy as np
from pathlib import Path
from pyproj import Transformer, CRS
import argparse
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 默认Mapbox令牌
DEFAULT_MAPBOX_TOKEN = "pk.eyJ1IjoidmluY2VudDEyOCIsImEiOiJjbHo4ZHhtcWswMXh0MnBvbW5vM2o0d2djIn0.Qj9VErbIh7yNL-DjTnAUFA"


class MapboxDownloader:
    """Mapbox地图下载器类"""
    
    def __init__(self, 
                 mapbox_token: str = None, 
                 style: str = "mapbox/streets-v12",
                 output_dir: str = "./output"):
        """
        初始化Mapbox下载器
        
        Args:
            mapbox_token: Mapbox访问令牌，如不提供将从环境变量MAPBOX_ACCESS_TOKEN获取或使用默认令牌
            style: Mapbox地图样式，格式为"username/style-id"
            output_dir: 输出目录
        """
        # 获取令牌，优先级：参数 > 环境变量 > 默认令牌
        self.mapbox_token = mapbox_token or os.getenv("MAPBOX_ACCESS_TOKEN") or DEFAULT_MAPBOX_TOKEN
            
        # 处理样式URL
        if "mapbox://" in style:
            # 从URL中提取样式ID
            style = style.split('/')[-1]
            if "mapbox" not in style:
                style = f"mapbox/{style}"
        
        self.style = style
        self.output_dir = output_dir
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建坐标转换器
        self.utm_to_wgs84 = Transformer.from_crs("EPSG:32755", "EPSG:4326", always_xy=True)
    
    def transform_coords(self, x: float, y: float) -> Tuple[float, float]:
        """
        将UTM坐标(EPSG:32755)转换为WGS84经纬度坐标
        
        Args:
            x: UTM东坐标
            y: UTM北坐标
            
        Returns:
            Tuple[float, float]: (经度, 纬度)
        """
        lon, lat = self.utm_to_wgs84.transform(x, y)
        return lon, lat
    
    def download_static_map(self, extent: List[float], width: int = 1280, height: int = 1280, filename: str = "map.png") -> str:
        """
        使用静态地图API下载地图图像
        
        Args:
            extent: [minX, minY, maxX, maxY] UTM坐标范围
            width: 图像宽度（像素）
            height: 图像高度（像素）
            filename: 输出文件名
            
        Returns:
            str: 保存的文件路径
        """
        # 转换UTM坐标到WGS84
        min_lon, min_lat = self.transform_coords(extent[0], extent[1])
        max_lon, max_lat = self.transform_coords(extent[2], extent[3])
        
        logger.info(f"坐标范围(WGS84): 左下角[{min_lon}, {min_lat}], 右上角[{max_lon}, {max_lat}]")
        
        # 构建静态地图API URL
        # 格式为：https://api.mapbox.com/styles/v1/{username}/{style_id}/static/[{lon},{lat},{zoom}|{bbox}]/{width}x{height}[@2x]
        
        # 使用bbox参数指定地图范围
        bbox = f"[{min_lon},{min_lat},{max_lon},{max_lat}]"
        
        url = f"https://api.mapbox.com/styles/v1/{self.style}/static/{bbox}/{width}x{height}?access_token={self.mapbox_token}"
        
        logger.info(f"请求URL: {url}")
        
        # 下载地图图像
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # 保存图像
                output_path = os.path.join(self.output_dir, filename)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"地图已保存至: {output_path}")
                
                # 保存元数据
                metadata = {
                    "extent_utm": extent,
                    "extent_wgs84": [min_lon, min_lat, max_lon, max_lat],
                    "image_size": [width, height],
                    "style": self.style,
                    "coord_system": "EPSG:32755",
                    "api_url": url
                }
                
                metadata_path = os.path.join(self.output_dir, f"{os.path.splitext(filename)[0]}_metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                logger.info(f"元数据已保存至: {metadata_path}")
                
                return output_path
            else:
                error_msg = f"下载地图失败: HTTP {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg += f" - {json.dumps(error_details)}"
                except:
                    error_msg += f" - {response.text}"
                
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"下载地图异常: {str(e)}")
            raise

    def download_map(self, extent_str: str, width: int = 1280, height: int = 720, filename: str = "map.png") -> str:
        """
        下载指定范围的地图
        
        Args:
            extent_str: 格式为"minX,minY : maxX,maxY"的范围字符串 (UTM坐标)
            width: 图像宽度（像素）
            height: 图像高度（像素）
            filename: 输出文件名
            
        Returns:
            str: 保存的文件路径
        """
        # 解析范围字符串
        parts = extent_str.split(":")
        if len(parts) != 2:
            raise ValueError("范围格式错误，应为'minX,minY : maxX,maxY'")
            
        min_coords = parts[0].strip().split(",")
        max_coords = parts[1].strip().split(",")
        
        if len(min_coords) != 2 or len(max_coords) != 2:
            raise ValueError("坐标格式错误，应为'X,Y'")
            
        extent = [
            float(min_coords[0]),
            float(min_coords[1]),
            float(max_coords[0]),
            float(max_coords[1])
        ]
        
        logger.info(f"下载范围(UTM): {extent}")
        
        # 使用静态地图API下载地图
        return self.download_static_map(extent, width, height, filename)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="下载Mapbox地图图片")
    parser.add_argument("--extent", type=str, required=True, 
                        help="格式为'minX,minY : maxX,maxY'的范围字符串 (UTM坐标)")
    parser.add_argument("--width", type=int, default=1280,
                        help="图像宽度（像素），默认为1280")
    parser.add_argument("--height", type=int, default=720,
                        help="图像高度（像素），默认为720")
    parser.add_argument("--style", type=str, default="mapbox/streets-v12",
                        help="Mapbox地图样式，格式为'username/style-id'")
    parser.add_argument("--token", type=str, default=None,
                        help="Mapbox访问令牌，若不提供将从环境变量获取或使用默认令牌")
    parser.add_argument("--output", type=str, default="wagga_wagga_map.png",
                        help="输出文件名")
    parser.add_argument("--output-dir", type=str, default="./output",
                        help="输出目录")
    
    args = parser.parse_args()
    
    downloader = MapboxDownloader(
        mapbox_token=args.token,
        style=args.style,
        output_dir=args.output_dir
    )
    
    try:
        output_path = downloader.download_map(
            extent_str=args.extent,
            width=args.width,
            height=args.height,
            filename=args.output
        )
        logger.info(f"地图下载成功: {output_path}")
        return 0
    except Exception as e:
        logger.error(f"地图下载失败: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main()) 