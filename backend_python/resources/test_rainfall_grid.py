import unittest
from pathlib import Path
import os
import shutil
import rasterio
import numpy as np
from datetime import datetime, timedelta

from .rainfall_grid import RainfallGridGenerator, get_bounds_from_3di_results

class TestRainfallGridGenerator(unittest.TestCase):
    def setUp(self):
        # 设置测试数据
        self.test_bounds = (500000, 6000000, 501000, 6001000)  # 1km x 1km 区域
        self.test_resolution = 500  # 500m分辨率
        self.test_output_dir = "test_output"
        self.test_grid_points_dir = "test_grid_points"
        
        # 确保测试输出目录存在
        os.makedirs(self.test_output_dir, exist_ok=True)
        os.makedirs(self.test_grid_points_dir, exist_ok=True)
    
    def test_rainfall_from_3di_results(self):
        """从3Di结果文件生成降雨数据"""
        # 读取3Di结果文件
        nc_file = "results_3di.nc"
        bounds = get_bounds_from_3di_results(nc_file)
        
        # 设置输出目录
        output_dir = "rainfall_from_3di"
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建降雨网格生成器
        generator = RainfallGridGenerator(
            utm_bounds=bounds,
            resolution_meters=10000,  # 10km分辨率
            utm_zone=55,
            hemisphere='south'
        )
        
        # 生成24小时的降雨数据
        start_date = datetime(2024, 3, 12)  # 使用固定的日期以便复现
        end_date = start_date + timedelta(days=1)
        
        output_files = generator.generate_rainfall_rasters(
            start_date=start_date.strftime("%Y%m%d_%H%M%S"),
            end_date=end_date.strftime("%Y%m%d_%H%M%S"),
            output_dir=output_dir,
            max_workers=4
        )
        
        # 验证生成的文件
        self.assertTrue(len(output_files) > 0)
        
        # 检查第一个文件的属性
        with rasterio.open(output_files[0]) as src:
            # 打印网格信息
            print("\nGrid information from 3Di results:")
            print(f"UTM bounds: {bounds}")
            print(f"Grid shape: {src.shape}")
            print(f"Resolution: 10km")
            print(f"CRS: {src.crs.to_string()}")
            
            # 验证数据类型
            self.assertEqual(str(src.dtypes[0]), 'float64')
            
            # 读取数据
            data = src.read(1)
            print(f"Data shape: {data.shape}")
            print(f"Non-zero rainfall values: {np.count_nonzero(data)}")
            
            # 如果有降雨值，打印一些统计信息
            if np.any(data > 0):
                print(f"Rainfall statistics:")
                print(f"  Min: {np.min(data[data > 0]):.2f} mm")
                print(f"  Max: {np.max(data):.2f} mm")
                print(f"  Mean: {np.mean(data[data > 0]):.2f} mm")
    
    # ... existing test methods ... 