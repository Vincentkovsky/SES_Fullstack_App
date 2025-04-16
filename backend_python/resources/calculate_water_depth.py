#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
水深度计算脚本

此脚本用于从3di模型的NetCDF输出文件中读取水位数据，并计算水深度。
水深度 = 水位 - 地面高程
"""

import os
import glob
import numpy as np
import logging
import json
import csv
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from netCDF4 import Dataset
import rasterio
from pathlib import Path
from pyproj import Transformer
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

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
    
    def get_variables(self) -> List[str]:
        """获取所有变量名称"""
        return list(self.nc.variables.keys())
    
    def get_dimensions(self) -> Dict[str, int]:
        """获取所有维度信息"""
        return {dim: len(self.nc.dimensions[dim]) for dim in self.nc.dimensions}
    
    def get_variable_data(self, var_name: str) -> np.ndarray:
        """
        获取变量数据
        
        Args:
            var_name (str): 变量名称
            
        Returns:
            np.ndarray: 变量数据
        """
        if var_name not in self.nc.variables:
            raise ValueError(f"Variable '{var_name}' not found")
            
        var = self.nc.variables[var_name]
        return var[:]
    
    def get_time_variable(self, time_var_name: str = 'time') -> List[np.datetime64]:
        """
        获取时间变量并转换为 datetime 对象列表
        
        Args:
            time_var_name (str): 时间变量名称
            
        Returns:
            List[np.datetime64]: 时间列表
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


def get_closest_node_level(file_path: str, gauge_lat: float, gauge_lon: float) -> Tuple[List[np.datetime64], np.ndarray]:
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
        
        # 四舍五入到2位小数，并确保输出时只有2位小数
        water_depth_rounded = [round(float(d), 2) for d in water_depth]
        
        # 构建结果 - 只包含水深度数据
        result = {
            "times": time_strings,
            "water_depths": water_depth_rounded
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


def plot_water_depth(data: Dict[str, Any], output_file: str, river_level_data: Optional[pd.DataFrame] = None):
    """
    将水深度数据绘制为折线图，并可选择性地添加实测河流水位数据进行比较
    
    Args:
        data: 水深度数据
        output_file: 输出图表文件路径
        river_level_data: 实测河流水位数据（可选）
    """
    try:
        # 解析时间字符串为datetime对象
        times = [np.datetime64(t).astype(datetime) for t in data["times"]]
        water_depths = data["water_depths"]
        
        # 创建图表
        plt.figure(figsize=(14, 8))
        
        # 绘制模拟水深度 - 更改为红色(原为蓝色)
        plt.plot(times, water_depths, 'r-', linewidth=2, label='Simulated Water Depth')
        
        # 如果提供了河流水位数据，在同一坐标系上绘制
        if river_level_data is not None:
            # 筛选时间范围内的河流水位数据
            min_time = min(times)
            max_time = max(times)
            
            mask = (river_level_data['date'] >= min_time) & (river_level_data['date'] <= max_time)
            filtered_data = river_level_data[mask]
            
            if not filtered_data.empty:
                # 绘制实测河流水位 - 更改为蓝色(原为红色)
                plt.plot(filtered_data['date'], filtered_data['level'], 'b-', linewidth=2, label='Observed River Level')
                
                # 计算统计信息
                mean_sim = np.mean(water_depths)
                mean_obs = np.mean(filtered_data['level'])
                
                # 在图表上添加统计信息
                info_text = f"Mean Simulated: {mean_sim:.2f}m\nMean Observed: {mean_obs:.2f}m"
                plt.annotate(info_text, xy=(0.02, 0.96), xycoords='axes fraction', 
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
                            fontsize=10, ha='left', va='top')
            else:
                logger.warning("No overlapping river level data found for the simulation period")
        
        # 添加标题和标签
        plt.title('Water Depth and River Level Comparison', fontsize=16)
        plt.xlabel('Time', fontsize=12)
        plt.ylabel('Water Level (m)', fontsize=12)
        plt.legend(loc='upper left')
        
        # 设置时间轴格式
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.gcf().autofmt_xdate()  # 自动旋转日期标签
        
        # 添加网格
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # 保存图表
        plt.tight_layout()
        plt.savefig(output_file, dpi=300)
        plt.close()
        
        logger.info(f"Comparison plot saved to {output_file}")
    except Exception as e:
        logger.error(f"Error plotting water depth comparison: {str(e)}")
        raise


def load_river_level_data(csv_file: str) -> pd.DataFrame:
    """
    从CSV文件加载河流水位数据
    
    Args:
        csv_file: CSV文件路径
        
    Returns:
        pd.DataFrame: 包含日期和河流水位的数据框
    """
    try:
        # 读取CSV文件，添加参数以处理引号
        df = pd.read_csv(csv_file, quotechar='"', encoding='utf-8')
        
        # 确保列名正确，移除引号
        df.columns = [col.strip('"') for col in df.columns]
        
        # 转换日期列 - 处理可能已经是字符串或已经有引号的情况
        if isinstance(df['Date'].iloc[0], str):
            # 如果是字符串，清理引号并解析
            df['Date'] = pd.to_datetime(df['Date'].str.strip('"'), format='%Y-%m-%d %H:%M')
        else:
            # 否则直接解析
            df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d %H:%M')
        
        # 转换水位列为浮点数 - 处理可能是字符串或已经是数值的情况
        if isinstance(df['River Level'].iloc[0], str):
            # 如果是字符串，清理引号并转换为浮点数
            df['River Level'] = df['River Level'].str.strip('"').astype(float)
        else:
            # 否则直接转换为浮点数
            df['River Level'] = df['River Level'].astype(float)
        
        # 创建结果数据框
        result_df = pd.DataFrame({
            'date': df['Date'],
            'level': df['River Level']
        })
        
        logger.info(f"Loaded {len(result_df)} river level records from {csv_file}")
        return result_df
    except Exception as e:
        logger.error(f"Error loading river level data: {str(e)}")
        # 尝试使用更简单的加载方法作为备选
        try:
            logger.info("Attempting alternative loading method...")
            # 尝试更直接的加载方法
            df = pd.read_csv(csv_file)
            
            # 直接使用字段名而不尝试清理
            date_col = [col for col in df.columns if 'Date' in col][0]
            level_col = [col for col in df.columns if 'Level' in col or 'level' in col][0]
            
            # 转换日期(无论格式如何)
            df[date_col] = pd.to_datetime(df[date_col])
            
            # 确保水位是浮点数
            df[level_col] = pd.to_numeric(df[level_col], errors='coerce')
            
            # 创建结果数据框
            result_df = pd.DataFrame({
                'date': df[date_col],
                'level': df[level_col]
            })
            
            # 删除任何存在NaN的行
            result_df = result_df.dropna()
            
            logger.info(f"Successfully loaded {len(result_df)} records with alternative method")
            return result_df
        except Exception as fallback_error:
            logger.error(f"Alternative loading method also failed: {str(fallback_error)}")
            raise


def process_netcdf_files(netcdf_dir: str, dem_file: str, output_dir: str, 
                        gauge_lat: float = -35.10077, 
                        gauge_lon: float = 147.36836,
                        river_level_file: Optional[str] = None):
    """
    处理NetCDF文件夹中的所有文件
    
    Args:
        netcdf_dir: NetCDF文件夹路径
        dem_file: DEM文件路径
        output_dir: 输出文件夹路径
        gauge_lat: 测量站纬度(默认:Wagga Wagga站)
        gauge_lon: 测量站经度(默认:Wagga Wagga站)
        river_level_file: 实测河流水位数据文件路径（可选）
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建图表目录
        plots_dir = os.path.join(output_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)
        
        # 加载河流水位数据（如果提供）
        river_level_data = None
        if river_level_file and os.path.exists(river_level_file):
            river_level_data = load_river_level_data(river_level_file)
        
        # 获取所有NetCDF文件
        nc_files = glob.glob(f"{netcdf_dir}/*.nc")
        if not nc_files:
            logger.warning(f"No NetCDF files found in {netcdf_dir}")
            return
            
        logger.info(f"Found {len(nc_files)} NetCDF files to process")
        
        # 处理每个文件
        for nc_file in nc_files:
            file_name = os.path.basename(nc_file)
            base_name = os.path.splitext(file_name)[0]
            output_json = os.path.join(output_dir, f"{base_name}_water_depth.json")
            output_plot = os.path.join(plots_dir, f"{base_name}_water_depth_comparison.png")
            
            logger.info(f"Processing {file_name}...")
            
            # 计算水深度
            water_depth_data = calculate_water_depth(nc_file, dem_file, gauge_lat, gauge_lon)
            
            # 保存结果到JSON
            save_water_depth_data(water_depth_data, output_json)
            
            # 绘制水深度与实测河流水位对比图
            # 不再生成单独的水深度图，只生成一张对比图
            plot_water_depth(water_depth_data, output_plot, river_level_data)
            if river_level_data is not None:
                logger.info(f"Created comparison plot with river level data")
            else:
                logger.info(f"Created water depth plot without river level data")
            
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
    output_dir = base_dir / "resources/water_depth_results"
    river_level_file = base_dir / "resources/water_depth_results/410001_river_level.csv"
    
    # 测量站坐标 (Wagga Wagga站)
    gauge_lat = -35.10077
    gauge_lon = 147.36836
    
    # 处理文件
    process_netcdf_files(
        str(netcdf_dir), 
        str(dem_file), 
        str(output_dir), 
        gauge_lat, 
        gauge_lon,
        str(river_level_file)
    )


if __name__ == "__main__":
    main() 