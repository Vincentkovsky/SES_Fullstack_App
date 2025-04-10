#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深度计算工具

此脚本用于从3di模型的NetCDF输出文件中读取水位数据，并计算水深度。
水深度 = 水位 - 地面高程
"""

import os
import glob
import numpy as np
import logging
import json
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from netCDF4 import Dataset
import rasterio
from pathlib import Path
import matplotlib.pyplot as plt
from pyproj import Transformer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NCReader:
    """NetCDF 文件读取器类"""
    
    def __init__(self, file_path: str):
        """
        初始化 NetCDF 读取器
        
        Args:
            file_path (str): NetCDF 文件路径
        """
        self.file_path = file_path
        self.nc = None
        
    def __enter__(self):
        self.nc = Dataset(self.file_path, mode='r')
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.nc is not None:
            self.nc.close()
    
    def get_global_attributes(self) -> Dict[str, Any]:
        """获取全局属性"""
        return {key: getattr(self.nc, key) for key in self.nc.ncattrs()}
    
    def get_variables(self) -> List[str]:
        """获取所有变量名称"""
        return list(self.nc.variables.keys())
    
    def get_dimensions(self) -> Dict[str, int]:
        """获取所有维度信息"""
        return {dim: len(self.nc.dimensions[dim]) for dim in self.nc.dimensions}
    
    def get_variable_info(self, var_name: str) -> Dict[str, Any]:
        """
        获取变量的详细信息
        
        Args:
            var_name (str): 变量名称
            
        Returns:
            Dict: 变量信息字典
        """
        if var_name not in self.nc.variables:
            raise ValueError(f"Variable '{var_name}' not found")
            
        var = self.nc.variables[var_name]
        return {
            'dimensions': var.dimensions,
            'shape': var.shape,
            'dtype': var.dtype,
            'attributes': {key: getattr(var, key) for key in var.ncattrs()},
            'units': getattr(var, 'units', None),
            'long_name': getattr(var, 'long_name', None)
        }
    
    def get_variable_data(self, 
                         var_name: str, 
                         start: Optional[Union[int, List[int]]] = None,
                         count: Optional[Union[int, List[int]]] = None) -> np.ndarray:
        """
        获取变量数据
        
        Args:
            var_name (str): 变量名称
            start: 起始索引
            count: 读取数量
            
        Returns:
            np.ndarray: 变量数据
        """
        if var_name not in self.nc.variables:
            raise ValueError(f"Variable '{var_name}' not found")
            
        var = self.nc.variables[var_name]
        return var[start:count] if start is not None else var[:]
    
    def get_time_variable(self, time_var_name: str = 'time') -> List[datetime]:
        """
        获取时间变量并转换为 datetime 对象列表
        
        Args:
            time_var_name (str): 时间变量名称
            
        Returns:
            List[datetime]: 时间列表
        """
        if time_var_name not in self.nc.variables:
            raise ValueError(f"Time variable '{time_var_name}' not found")
            
        time_var = self.nc.variables[time_var_name]
        units = getattr(time_var, 'units', '')
        
        # 解析时间单位
        if 'since' in units.lower():
            base_time_str = units.split('since')[1].strip()
            try:
                base_time = np.datetime64(base_time_str)
                
                # 转换时间数组
                time_values = time_var[:]
                return [base_time + np.timedelta64(int(t), 's') for t in time_values]
            except Exception as e:
                logger.error(f"Error parsing time: {str(e)}")
                # 如果上面的方法失败，尝试另一种方法
                try:
                    base_time = datetime.strptime(base_time_str, '%Y-%m-%d %H:%M:%S')
                    return [base_time + timedelta(seconds=float(t)) for t in time_var[:]]
                except Exception as e2:
                    logger.error(f"Error parsing time with alternative method: {str(e2)}")
                    raise
        else:
            raise ValueError(f"Unsupported time units: {units}")


def XYtoLonLat(x, y):
    """
    将X,Y坐标转换为经度、纬度
    
    Args:
        x: X坐标
        y: Y坐标
        
    Returns:
        tuple: (lon, lat)
    """
    transformer = Transformer.from_crs("EPSG:32755", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return lon, lat


def get_closest_node_level(file_path: str, gauge_lat: float, gauge_lon: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    获取最接近指定测量站的节点的水位时间序列
    
    Args:
        file_path: NetCDF文件路径
        gauge_lat: 测量站纬度
        gauge_lon: 测量站经度
        
    Returns:
        Tuple: (times, levels) - 时间数组和水位数组
    """
    try:
        with NCReader(file_path) as nc:
            # 获取必要的数据
            xcc = nc.get_variable_data("Mesh2DFace_xcc")  # 网格中心点X坐标
            ycc = nc.get_variable_data("Mesh2DFace_ycc")  # 网格中心点Y坐标
            level = nc.get_variable_data("Mesh2D_s1")     # 水位数据
            times = nc.get_time_variable()                # 时间序列
            
            # 将X,Y坐标转换为经纬度
            lon, lat = XYtoLonLat(xcc, ycc)
            
            # 计算每个节点到测量站的距离
            distances = np.sqrt((lat - gauge_lat)**2 + (lon - gauge_lon)**2)
            
            # 找到最近的节点
            closest_node_index = np.argmin(distances)
            
            # 获取该节点的水位时间序列
            closest_node_level = level[:, closest_node_index]
            
            return times, closest_node_level
    except Exception as e:
        logger.error(f"Error getting closest node level: {str(e)}")
        raise


def get_dem_value(file_path: str, lat: float, lon: float) -> float:
    """
    从DEM中获取指定坐标的高程值
    
    Args:
        file_path: DEM文件路径
        lat: 纬度
        lon: 经度
        
    Returns:
        float: 高程值
    """
    try:
        with rasterio.open(file_path) as dem:
            # 将经纬度转换为DEM的坐标系统
            transformer = Transformer.from_crs("EPSG:4326", dem.crs, always_xy=True)
            x, y = transformer.transform(lon, lat)
            
            # 读取DEM值
            row, col = dem.index(x, y)
            dem_value = dem.read(1)[row, col]
            
            return float(dem_value)
    except Exception as e:
        logger.error(f"Error getting DEM value: {str(e)}")
        raise


def calculate_water_depth(nc_file: str, dem_file: str, gauge_lat: float, gauge_lon: float) -> Dict[str, Any]:
    """
    计算水深度

    Args:
        nc_file: NetCDF文件路径
        dem_file: DEM文件路径
        gauge_lat: 测量站纬度
        gauge_lon: 测量站经度
        
    Returns:
        Dict: 包含时间序列和水深度的字典
    """
    try:
        # 获取DEM值
        dem_value = get_dem_value(dem_file, gauge_lat, gauge_lon)
        logger.info(f"DEM value at ({gauge_lat}, {gauge_lon}): {dem_value}m")

        # 获取水位时间序列
        times, water_levels = get_closest_node_level(nc_file, gauge_lat, gauge_lon)
        
        # 将NumPy datetime64转换为ISO格式字符串
        time_strings = [str(t) for t in times]
        
        # 计算水深度 = 水位 - 地面高程
        water_depth = water_levels - dem_value
        
        # 四舍五入到2位小数
        water_depth_rounded = np.round(water_depth, decimals=2)
        
        # 构建结果
        result = {
            "gauge_location": {
                "latitude": gauge_lat,
                "longitude": gauge_lon
            },
            "dem_elevation": float(dem_value),
            "times": time_strings,
            "water_levels": water_levels.tolist(),
            "water_depths": water_depth_rounded.tolist(),
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    except Exception as e:
        logger.error(f"Error calculating water depth: {str(e)}")
        raise


def save_water_depth_data(data: Dict[str, Any], output_file: str):
    """
    保存水深度数据到JSON文件
    
    Args:
        data: 水深度数据
        output_file: 输出文件路径
    """
    try:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Water depth data saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving water depth data: {str(e)}")
        raise


def plot_water_depth(data: Dict[str, Any], output_file: str = None):
    """
    绘制水深度图表
    
    Args:
        data: 水深度数据
        output_file: 输出图表文件路径
    """
    try:
        # 准备数据
        times = [np.datetime64(t) for t in data['times']]
        depths = data['water_depths']
        
        # 创建图表
        plt.figure(figsize=(12, 6))
        plt.plot(times, depths, label='Water Depth')
        plt.xlabel('Time')
        plt.ylabel('Water Depth (m)')
        plt.title(f"Water Depth at ({data['gauge_location']['latitude']}, {data['gauge_location']['longitude']})")
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # 保存或显示
        if output_file:
            plt.savefig(output_file)
            logger.info(f"Water depth plot saved to {output_file}")
        else:
            plt.show()
    except Exception as e:
        logger.error(f"Error plotting water depth: {str(e)}")
        raise


def process_netcdf_files(netcdf_dir: str, dem_file: str, output_dir: str, 
                        gauge_lat: float = -35.10077, 
                        gauge_lon: float = 147.36836):
    """
    处理NetCDF文件夹中的所有文件
    
    Args:
        netcdf_dir: NetCDF文件夹路径
        dem_file: DEM文件路径
        output_dir: 输出文件夹路径
        gauge_lat: 测量站纬度(默认:Wagga Wagga站)
        gauge_lon: 测量站经度(默认:Wagga Wagga站)
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取所有NetCDF文件
        nc_files = glob.glob(f"{netcdf_dir}/*.nc")
        if not nc_files:
            logger.warning(f"No NetCDF files found in {netcdf_dir}")
            return
            
        logger.info(f"Found {len(nc_files)} NetCDF files to process")
        
        # 处理每个文件
        for nc_file in nc_files:
            file_name = os.path.basename(nc_file)
            output_json = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}_water_depth.json")
            output_plot = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}_water_depth.png")
            
            logger.info(f"Processing {file_name}...")
            
            # 计算水深度
            water_depth_data = calculate_water_depth(nc_file, dem_file, gauge_lat, gauge_lon)
            
            # 保存结果
            save_water_depth_data(water_depth_data, output_json)
            
            # 绘制图表
            plot_water_depth(water_depth_data, output_plot)
            
        logger.info("All files processed successfully")
    except Exception as e:
        logger.error(f"Error processing NetCDF files: {str(e)}")
        raise


def main():
    """主函数"""
    # 配置路径
    base_dir = Path(__file__).parent.parent
    netcdf_dir = base_dir / "data/3di_res/netcdf"
    dem_file = base_dir / "data/3di_res/5m_dem.tif"
    output_dir = base_dir / "data/3di_res/water_depth"
    
    # 测量站坐标 (Wagga Wagga站)
    gauge_lat = -35.10077
    gauge_lon = 147.36836
    
    # 处理文件
    process_netcdf_files(str(netcdf_dir), str(dem_file), str(output_dir), gauge_lat, gauge_lon)


if __name__ == "__main__":
    main() 