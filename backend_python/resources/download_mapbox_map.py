#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mapbox 地图下载脚本

此脚本用于下载指定 EPSG:32755 坐标系下的 Mapbox 地图图片，
支持坐标转换和图片拼接，并添加地理参考信息。
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
import rasterio
from rasterio.transform import from_bounds

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

class MapboxDownloader:
    """Mapbox 地图下载器类"""
    
    def __init__(self, 
                 mapbox_token: str = None, 
                 style: str = "mapbox://styles/mapbox/streets-v12",
                 output_dir: str = "./output",
                 zoom: int = 14):
        """
        初始化 Mapbox 下载器
        
        Args:
            mapbox_token: Mapbox 访问令牌
            style: 地图样式 URL
            output_dir: 输出目录
            zoom: 地图缩放级别
        """
        # 使用环境变量中的令牌，或者传入的令牌
        self.token = mapbox_token or os.environ.get("MAPBOX_ACCESS_TOKEN")
        if not self.token:
            raise ValueError("Mapbox token is required. Set MAPBOX_ACCESS_TOKEN environment variable or pass it as argument.")
        
        # 解析样式 URL
        if style.startswith("mapbox://styles/"):
            style_path = style.replace("mapbox://styles/", "")
            self.style_url = f"https://api.mapbox.com/styles/v1/{style_path}/tiles"
        else:
            self.style_url = style
            
        # 初始化其他参数
        self.zoom = zoom
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # 创建坐标转换器
        self.utm_to_wgs84 = Transformer.from_crs(
            CRS.from_epsg(32755),  # UTM 区域 55S
            CRS.from_epsg(4326),   # WGS84
            always_xy=True
        )
        
        # 创建反向转换器 (WGS84 -> UTM)
        self.wgs84_to_utm = Transformer.from_crs(
            CRS.from_epsg(4326),   # WGS84
            CRS.from_epsg(32755),  # UTM 区域 55S
            always_xy=True
        )
        
        # 缓存已下载的瓦片
        self.tile_cache = {}
        
    def utm_to_latlon(self, x: float, y: float) -> Tuple[float, float]:
        """
        从 UTM 坐标转换为 WGS84 经纬度坐标
        
        Args:
            x: UTM X 坐标 (东向)
            y: UTM Y 坐标 (北向)
            
        Returns:
            (lon, lat) 经度和纬度
        """
        lon, lat = self.utm_to_wgs84.transform(x, y)
        return lon, lat
    
    def latlon_to_tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """
        从经纬度计算瓦片坐标
        
        Args:
            lat: 纬度
            lon: 经度
            zoom: 缩放级别
            
        Returns:
            (x, y) 瓦片坐标
        """
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return x, y
    
    def get_tile_url(self, x: int, y: int, zoom: int) -> str:
        """
        生成瓦片 URL
        
        Args:
            x: 瓦片 X 坐标
            y: 瓦片 Y 坐标
            zoom: 缩放级别
            
        Returns:
            瓦片 URL
        """
        return f"{self.style_url}/{zoom}/{x}/{y}@2x?access_token={self.token}"
    
    def download_tile(self, x: int, y: int, zoom: int) -> Optional[Image.Image]:
        """
        下载单个瓦片
        
        Args:
            x: 瓦片 X 坐标
            y: 瓦片 Y 坐标
            zoom: 缩放级别
            
        Returns:
            瓦片图像对象，如果下载失败则返回 None
        """
        cache_key = f"{zoom}_{x}_{y}"
        if cache_key in self.tile_cache:
            return self.tile_cache[cache_key]
        
        url = self.get_tile_url(x, y, zoom)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                self.tile_cache[cache_key] = img
                return img
            else:
                logger.error(f"Failed to download tile {x},{y} at zoom {zoom}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error downloading tile {x},{y} at zoom {zoom}: {e}")
            return None
    
    def stitch_tiles(self, tiles: List[List[Optional[Image.Image]]], width: int, height: int) -> Image.Image:
        """
        拼接瓦片图像
        
        Args:
            tiles: 二维瓦片数组
            width: 拼接图像宽度
            height: 拼接图像高度
            
        Returns:
            拼接后的图像
        """
        tile_size = 512  # Mapbox 使用 @2x 的瓦片为 512x512 像素
        result = Image.new('RGBA', (width * tile_size, height * tile_size))
        
        for y in range(height):
            for x in range(width):
                if tiles[y][x] is not None:
                    result.paste(tiles[y][x], (x * tile_size, y * tile_size))
        
        return result
    
    def save_geotiff(self, image: Image.Image, output_path: str, utm_bounds: Tuple[float, float, float, float]):
        """
        将图像保存为带有地理参考信息的 GeoTIFF
        
        Args:
            image: PIL 图像对象
            output_path: 输出文件路径
            utm_bounds: UTM 坐标边界 (minx, miny, maxx, maxy)
        """
        # 将 PIL 图像转换为 numpy 数组
        array = np.array(image)
        
        # 计算变换矩阵
        width, height = image.size
        
        # 计算像素分辨率
        x_res = (utm_bounds[2] - utm_bounds[0]) / width
        y_res = (utm_bounds[3] - utm_bounds[1]) / height
        
        # 创建地理转换矩阵（从像素坐标到UTM坐标）
        transform = from_bounds(
            utm_bounds[0], utm_bounds[1], utm_bounds[2], utm_bounds[3],
            width, height
        )
        
        logger.info(f"生成GeoTIFF，分辨率为: x={x_res:.2f}m/pixel, y={y_res:.2f}m/pixel")
        
        # 定义UTM区域55S坐标系统
        crs = CRS.from_epsg(32755)
        
        # 将RGBA图像分离为3个或4个波段
        if array.shape[2] == 4:  # 带透明通道的RGBA
            bands = [array[:, :, 0], array[:, :, 1], array[:, :, 2], array[:, :, 3]]
            count = 4
        else:  # RGB
            bands = [array[:, :, 0], array[:, :, 1], array[:, :, 2]]
            count = 3
            
        # 创建GeoTIFF文件
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=count,
            dtype=bands[0].dtype,
            crs=crs,
            transform=transform,
            photometric="RGB" if count == 3 else None
        ) as dst:
            for i, band in enumerate(bands, 1):
                dst.write(band, i)
                
        logger.info(f"已保存带有地理参考信息的GeoTIFF到: {output_path}")
        
    def download_map(self, 
                    utm_extent: str, 
                    output_file: str = "map.png") -> Tuple[Image.Image, Dict]:
        """
        下载地图区域
        
        Args:
            utm_extent: UTM 坐标范围，格式为 "minX,minY : maxX,maxY"
            output_file: 输出文件名
            
        Returns:
            (图像对象, 元数据)
        """
        # 解析UTM坐标范围
        parts = utm_extent.split(" : ")
        if len(parts) != 2:
            raise ValueError("Invalid extent format. Expected 'minX,minY : maxX,maxY'")
            
        min_corner = [float(x) for x in parts[0].split(",")]
        max_corner = [float(x) for x in parts[1].split(",")]
        
        if len(min_corner) != 2 or len(max_corner) != 2:
            raise ValueError("Invalid corner format. Expected 'X,Y'")
            
        utm_min_x, utm_min_y = min_corner
        utm_max_x, utm_max_y = max_corner
        
        # 存储UTM边界信息
        utm_bounds = (utm_min_x, utm_min_y, utm_max_x, utm_max_y)
        
        # 转换角落坐标到WGS84
        min_lon, min_lat = self.utm_to_latlon(utm_min_x, utm_min_y)
        max_lon, max_lat = self.utm_to_latlon(utm_max_x, utm_max_y)
        
        logger.info(f"UTM区域: ({utm_min_x}, {utm_min_y}) - ({utm_max_x}, {utm_max_y})")
        logger.info(f"WGS84区域: ({min_lon}, {min_lat}) - ({max_lon}, {max_lat})")
        
        # 计算瓦片范围
        min_tile_x, min_tile_y = self.latlon_to_tile(min_lat, min_lon, self.zoom)
        max_tile_x, max_tile_y = self.latlon_to_tile(max_lat, max_lon, self.zoom)
        
        # 确保正确的顺序
        if min_tile_x > max_tile_x:
            min_tile_x, max_tile_x = max_tile_x, min_tile_x
        if min_tile_y > max_tile_y:
            min_tile_y, max_tile_y = max_tile_y, min_tile_y
            
        # 计算瓦片数量
        tile_width = max_tile_x - min_tile_x + 1
        tile_height = max_tile_y - min_tile_y + 1
        
        logger.info(f"瓦片范围: ({min_tile_x}, {min_tile_y}) - ({max_tile_x}, {max_tile_y})")
        logger.info(f"需要下载的瓦片: {tile_width}x{tile_height} = {tile_width * tile_height}张")
        
        # 下载所有瓦片
        tiles = [[None for _ in range(tile_width)] for _ in range(tile_height)]
        
        for y_idx in range(tile_height):
            for x_idx in range(tile_width):
                x = min_tile_x + x_idx
                y = min_tile_y + y_idx
                logger.info(f"下载瓦片 ({x}, {y}) 缩放级别 {self.zoom}...")
                tiles[y_idx][x_idx] = self.download_tile(x, y, self.zoom)
        
        # 拼接瓦片
        logger.info("拼接瓦片...")
        stitched_image = self.stitch_tiles(tiles, tile_width, tile_height)
        
        # 构建输出路径
        output_png = self.output_dir / output_file
        output_geotiff = output_png.with_suffix('.tif')
        output_metadata = output_png.with_suffix('.json')
        
        # 保存PNG图像
        logger.info(f"保存PNG图像到: {output_png}")
        stitched_image.save(output_png)
        
        # 保存带有地理参考信息的GeoTIFF
        self.save_geotiff(stitched_image, str(output_geotiff), utm_bounds)
        
        # 构建并保存元数据
        metadata = {
            "utm_bounds": {
                "min_x": utm_min_x,
                "min_y": utm_min_y,
                "max_x": utm_max_x,
                "max_y": utm_max_y
            },
            "wgs84_bounds": {
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat
            },
            "zoom_level": self.zoom,
            "tiles": {
                "width": tile_width,
                "height": tile_height,
                "count": tile_width * tile_height
            },
            "output_files": {
                "png": str(output_png),
                "geotiff": str(output_geotiff),
                "metadata": str(output_metadata)
            }
        }
        
        # 保存元数据
        with open(output_metadata, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logger.info(f"保存元数据到: {output_metadata}")
        
        return stitched_image, metadata

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="下载指定EPSG:32755坐标系下的Mapbox地图")
    
    parser.add_argument(
        "--extent",
        required=True,
        help="UTM坐标范围，格式为'minX,minY : maxX,maxY'"
    )
    
    parser.add_argument(
        "--zoom",
        type=int,
        default=14,
        help="地图缩放级别 (默认: 14)"
    )
    
    parser.add_argument(
        "--style",
        default="mapbox://styles/mapbox/streets-v12",
        help="Mapbox地图样式 (默认: mapbox://styles/mapbox/streets-v12)"
    )
    
    parser.add_argument(
        "--token",
        help="Mapbox访问令牌 (可选，也可通过环境变量MAPBOX_ACCESS_TOKEN设置)"
    )
    
    parser.add_argument(
        "--output",
        default="wagga_wagga_map.png",
        help="输出文件名 (默认: wagga_wagga_map.png)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="输出目录 (默认: ./output)"
    )
    
    return parser.parse_args()

def main():
    """脚本主入口点"""
    args = parse_arguments()
    
    try:
        downloader = MapboxDownloader(
            mapbox_token=args.token,
            style=args.style,
            output_dir=args.output_dir,
            zoom=args.zoom
        )
        
        _, metadata = downloader.download_map(
            utm_extent=args.extent,
            output_file=args.output
        )
        
        logger.info("地图下载完成!")
        logger.info(f"PNG图像: {metadata['output_files']['png']}")
        logger.info(f"GeoTIFF: {metadata['output_files']['geotiff']}")
        logger.info(f"元数据: {metadata['output_files']['metadata']}")
        
    except Exception as e:
        logger.error(f"下载地图时出错: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main()) 