import numpy as np
import pyproj
import rasterio
from rasterio.transform import from_origin
import multiprocessing as mp
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Union
from pathlib import Path
import os
import xarray as xr
from tqdm import tqdm
from openweatherUtils import get_historical_archive_openmeteo, decode_historical_archive_openmeteo
from pyproj import CRS, Transformer
import numpy.typing as npt

def get_bounds_from_3di_results(nc_path: str) -> Tuple[float, float, float, float]:
    """
    从3Di结果文件中获取网格边界坐标
    
    Args:
        nc_path: netCDF文件路径
        
    Returns:
        Tuple[float, float, float, float]: (minx, miny, maxx, maxy)
    """
    ds = xr.open_dataset(nc_path)
    minx = float(ds['Mesh2DFace_xcc'].min())
    miny = float(ds['Mesh2DFace_ycc'].min())
    maxx = float(ds['Mesh2DFace_xcc'].max())
    maxy = float(ds['Mesh2DFace_ycc'].max())
    ds.close()
    return minx, miny, maxx, maxy

class RainfallGridGenerator:
    def __init__(self, 
                 utm_bounds: Tuple[float, float, float, float] = (520700.0, 6104100.0, 560000.0, 6121550.0),
                 resolution_meters: float = 5,  # 默认5米分辨率
                 utm_zone: int = 55,  # 根据实际位置调整
                 hemisphere: str = 'south'):  # 'north' 或 'south'
        """
        初始化降雨网格生成器
        
        Args:
            utm_bounds: (minx, miny, maxx, maxy) UTM坐标边界
                默认值: (520700.0, 6104100.0, 560000.0, 6121550.0)
            resolution_meters: 网格分辨率（米），默认5米
            utm_zone: UTM区域号
            hemisphere: 半球 ('north' 或 'south')
            
        Raises:
            ValueError: 当输入参数无效时抛出
        """
        # 验证输入参数
        if resolution_meters <= 0:
            raise ValueError("分辨率必须为正数")
        
        if utm_bounds[2] <= utm_bounds[0]:
            raise ValueError("无效的X轴边界：maxx必须大于minx")
        
        if utm_bounds[3] <= utm_bounds[1]:
            raise ValueError("无效的Y轴边界：maxy必须大于miny")
        
        if hemisphere not in ['north', 'south']:
            raise ValueError("hemisphere必须是'north'或'south'")
        
        if not (1 <= utm_zone <= 60):
            raise ValueError("UTM区域号必须在1到60之间")
        
        self.bounds = utm_bounds
        self.resolution = resolution_meters
        self.utm_zone = utm_zone
        self.hemisphere = hemisphere
        
        # 设置坐标转换器
        self.utm_proj = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
        self.wgs84_proj = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
        self.transformer = pyproj.Transformer.from_crs(self.utm_proj, self.wgs84_proj)
        
        # 计算网格尺寸
        self.grid_width = int(np.ceil((self.bounds[2] - self.bounds[0]) / self.resolution)) + 1
        self.grid_height = int(np.ceil((self.bounds[3] - self.bounds[1]) / self.resolution)) + 1

        print(f"网格范围: ({self.bounds[0]}, {self.bounds[1]}) - ({self.bounds[2]}, {self.bounds[3]})")
        print(f"分辨率: {self.resolution}m")
        print(f"网格尺寸: {self.grid_width} x {self.grid_height}")
        
        # 创建网格点
        self._create_grid_points()

    def _create_grid_points(self):
        """创建UTM网格点并转换为经纬度"""
        # 使用linspace确保精确的边界值
        x = np.linspace(self.bounds[0], self.bounds[2], self.grid_width)
        y = np.linspace(self.bounds[1], self.bounds[3], self.grid_height)
        self.xx, self.yy = np.meshgrid(x, y)
        
        # 转换为经纬度
        lat_lon_points = [self.transformer.transform(x, y) 
                         for x, y in zip(self.xx.flatten(), self.yy.flatten())]
        self.lons, self.lats = zip(*lat_lon_points)
        self.lons = np.array(self.lons).reshape(self.xx.shape)
        self.lats = np.array(self.lats).reshape(self.yy.shape)
        
        # 保存网格点坐标到文件
        # self.save_grid_points()

    def save_grid_points(self, output_dir: str = "grid_points"):
        """
        保存网格点坐标到文件
        
        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存UTM坐标
        np.savetxt(
            os.path.join(output_dir, "utm_x.csv"),
            self.xx,
            delimiter=",",
            header=f"UTM X coordinates (meters) - Resolution: {self.resolution}m"
        )
        np.savetxt(
            os.path.join(output_dir, "utm_y.csv"),
            self.yy,
            delimiter=",",
            header=f"UTM Y coordinates (meters) - Resolution: {self.resolution}m"
        )
        
        # 保存经纬度坐标
        np.savetxt(
            os.path.join(output_dir, "longitude.csv"),
            self.lons,
            delimiter=",",
            header=f"Longitude coordinates (degrees) - Resolution: {self.resolution}m"
        )
        np.savetxt(
            os.path.join(output_dir, "latitude.csv"),
            self.lats,
            delimiter=",",
            header=f"Latitude coordinates (degrees) - Resolution: {self.resolution}m"
        )
        
        # 保存坐标对照表
        with open(os.path.join(output_dir, "grid_points.csv"), "w") as f:
            f.write("i,j,utm_x,utm_y,longitude,latitude\n")
            for i in range(self.grid_height):
                for j in range(self.grid_width):
                    f.write(f"{i},{j},{self.xx[i,j]},{self.yy[i,j]},{self.lons[i,j]},{self.lats[i,j]}\n")

    def _get_rainfall_for_point(self, args) -> Tuple[int, int, List[float]]:
        """获取单个点的降雨数据（用于并行处理）"""
        i, j, lat, lon, start_date, end_date = args
        try:
            data = get_historical_archive_openmeteo(
                latitude=lat,
                longitude=lon,
                start_date=start_date,
                end_date=end_date,
                hourly_params=["rain"]
            )
            if data:
                decoded_data = decode_historical_archive_openmeteo(data)
                return i, j, decoded_data.get('rain', [])
            return i, j, []
        except Exception as e:
            print(f"Error getting rainfall data for point ({lat}, {lon}): {e}")
            return i, j, []

    def generate_rainfall_rasters(self, 
                                start_date: str,
                                end_date: str,
                                output_dir: str,
                                max_workers: int = 4) -> Dict[str, List[str]]:
        """
        生成降雨栅格文件，同时输出GeoTIFF和NetCDF格式
        
        Args:
            start_date: 开始日期 (YYYYMMDD_HHMMSS)
            end_date: 结束日期 (YYYYMMDD_HHMMSS)
            output_dir: 输出目录
            max_workers: 最大并行进程数
            
        Returns:
            Dict包含生成的文件路径列表:
            {
                'geotiff': [...],
                'netcdf': [...]
            }
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'geotiff'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'netcdf'), exist_ok=True)
        
        # 准备并行处理参数
        args_list = [
            (i, j, self.lats[i, j], self.lons[i, j], start_date, end_date)
            for i in range(self.grid_height)
            for j in range(self.grid_width)
        ]
        
        total_points = len(args_list)
        print(f"\n开始获取降雨数据 (共 {total_points} 个网格点)...")
        
        # 并行获取降雨数据
        rainfall_data = {}
        with mp.Pool(max_workers) as pool:
            results = list(tqdm(
                pool.imap(self._get_rainfall_for_point, args_list),
                total=total_points,
                desc="获取降雨数据",
                unit="点"
            ))
            for i, j, rain_values in results:
                rainfall_data[(i, j)] = rain_values
        
        # 获取时间戳列表
        print("\n获取时间戳信息...")
        sample_data = get_historical_archive_openmeteo(
            latitude=self.lats[0, 0],
            longitude=self.lons[0, 0],
            start_date=start_date,
            end_date=end_date,
            hourly_params=["rain"]
        )
        timestamps = decode_historical_archive_openmeteo(sample_data)['timestamps']
        
        # 创建半小时时间戳
        half_hour_timestamps = []
        hourly_timestamps = []  # 新增：仅整点时间戳
        for i in range(len(timestamps)-1):
            current_time = datetime.fromisoformat(timestamps[i])
            next_time = datetime.fromisoformat(timestamps[i+1])
            half_time = current_time + (next_time - current_time) / 2
            
            half_hour_timestamps.append(current_time.strftime("%Y-%m-%dT%H:%M"))
            half_hour_timestamps.append(half_time.strftime("%Y-%m-%dT%H:%M"))
  
            hourly_timestamps.append(current_time)  # 新增：仅添加整点时间
        
        half_hour_timestamps.append(timestamps[-1])
        hourly_timestamps.append(datetime.fromisoformat(timestamps[-1]))  # 新增：添加最后一个整点
        
        # 创建GeoTIFF文件
        geotiff_files = []
        transform = rasterio.transform.from_bounds(
            self.bounds[0],      # left
            self.bounds[1],      # bottom
            self.bounds[2],      # right
            self.bounds[3],      # top
            self.grid_width - 1,    # width
            self.grid_height - 1    # height
        )
        
        # 准备NetCDF数据 - 修改为仅使用整点时间
        unix_epoch = np.datetime64('1970-01-01T00:00:00', 'us')
        hourly_time_steps = np.array(hourly_timestamps, dtype='datetime64[s]')
        hourly_time_steps_seconds = ((hourly_time_steps - unix_epoch) / np.timedelta64(1, 's'))
        
        # 创建降雨数据数组 - 修改为仅使用整点数据
        hourly_rainfall_array = np.zeros((len(hourly_timestamps), self.grid_height, self.grid_width), dtype=np.float32)
        
        print(f"\n开始生成降雨文件 (共 {len(half_hour_timestamps)} 个时间步)...")
        for t, timestamp in enumerate(tqdm(half_hour_timestamps, desc="生成文件", unit="文件")):
            # 创建当前时间步的降雨强度矩阵
            rainfall_matrix = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)
            
            # 如果是整点，直接使用数据
            if t % 2 == 0:
                hour_index = t // 2
                for i in range(self.grid_height):
                    for j in range(self.grid_width):
                        rain_values = rainfall_data.get((i, j), [])
                        if hour_index < len(rain_values):
                            rainfall_matrix[i, j] = np.float32(rain_values[hour_index] / 2)
                # 保存整点数据到hourly_rainfall_array
                hourly_rainfall_array[hour_index] = rainfall_matrix * 2  # 乘以2转换回小时降雨量
            # 如果是半点，插值计算
            else:
                hour_index = t // 2
                for i in range(self.grid_height):
                    for j in range(self.grid_width):
                        rain_values = rainfall_data.get((i, j), [])
                        if hour_index + 1 < len(rain_values):
                            rainfall_matrix[i, j] = np.float32(rain_values[hour_index + 1] / 2)
            
            # 生成GeoTIFF文件
            dt = datetime.fromisoformat(timestamp)
            filename = f"rainfall_{dt.strftime('%Y%m%d%H%M%S')}.tif"
            filepath = str(Path(output_dir) / 'geotiff' / filename)
            
            with rasterio.open(
                filepath,
                'w',
                driver='GTiff',
                height=self.grid_height,
                width=self.grid_width,
                count=1,
                dtype='float32',
                crs=rasterio.crs.CRS.from_string(self.utm_proj),
                transform=transform
            ) as dst:
                dst.write(rainfall_matrix, 1)
            
            geotiff_files.append(filepath)
        
        # 创建NetCDF文件
        netcdf_files = []
        ds = xr.Dataset()
        
        # 添加时间维度 - 使用整点时间
        ds['time'] = xr.DataArray(
            hourly_time_steps_seconds,
            dims='time',
            attrs={
                'standard_name': 'time',
                'long_name': 'Time',
                'units': 'seconds since 1970-01-01 00:00:00.0 +0000',
                'calendar': 'standard',
                'axis': 'T'
            }
        )
        
        # 添加空间维度
        target_crs = CRS.from_string(self.utm_proj)
        x_attrs, y_attrs = target_crs.cs_to_cf()
        
        ds['x'] = xr.DataArray(
            np.linspace(self.bounds[0], self.bounds[2], self.grid_width),
            dims='x',
            attrs=x_attrs
        )
        
        ds['y'] = xr.DataArray(
            np.linspace(self.bounds[1], self.bounds[3], self.grid_height),
            dims='y',
            attrs=y_attrs
        )
        
        # 添加降雨数据 - 使用整点数据
        ds['values'] = xr.DataArray(
            hourly_rainfall_array,  # 使用整点降雨数据
            dims=('time', 'y', 'x'),
            attrs={
                'long_name': 'rain',
                'grid_mapping': 'crs',
                '_FillValue': 0,
                'missing_value': 0,
                'units': 'mm/hr'  # 单位保持为mm/hr
            }
        )
        
        # 添加投影信息
        ds['crs'] = 1
        ds['crs'].attrs = target_crs.to_cf()
        ds['crs'].attrs['spatial_ref'] = f"EPSG:{target_crs.to_epsg()}"
        ds['crs'].attrs['GeoTransform'] = f"{self.bounds[0]} {self.resolution} 0 {self.bounds[3]} 0 -{self.resolution}"
        
        # 添加全局属性
        ds.attrs = {
            'OFFSET': 0,
            'Conventions': 'CF-1.6',
            'title': 'Hourly Rainfall data',  # 更新标题以反映整点数据
            'institution': 'Generated by RainfallGridGenerator',
            'source': 'Open-Meteo API',
            'references': 'https://open-meteo.com/'
        }
        
        # 保存NetCDF文件 - 使用整点时间戳
        nc_filename = f"rainfall_{hourly_timestamps[0].strftime('%Y%m%d%H%M')}_{hourly_timestamps[-1].strftime('%Y%m%d%H%M')}.nc"
        nc_filepath = str(Path(output_dir) / 'netcdf' / nc_filename)
        ds.to_netcdf(nc_filepath, format='NETCDF4')
        netcdf_files.append(nc_filepath)
        
        return {
            'geotiff': geotiff_files,
            'netcdf': netcdf_files
        }

def generate_rainfall_rasters_for_3di(grid_bounds,
                                    start_date: str,
                                    end_date: str,
                                    output_dir: str,
                                    resolution_meters: float = 100):
    """
    为3Di模型的网格范围生成降雨栅格文件
    
    Args:
        grid_bounds: GridBounds对象
        start_date: 开始日期 (YYYYMMDD_HHMMSS)
        end_date: 结束日期 (YYYYMMDD_HHMMSS)
        output_dir: 输出目录
        resolution_meters: 网格分辨率（米）
    
    Returns:
        生成的GeoTIFF文件路径列表
    """
    # 获取UTM边界
    utm_bounds = (
        grid_bounds.minx,
        grid_bounds.miny,
        grid_bounds.maxx,
        grid_bounds.maxy
    )
    
    # 创建降雨网格生成器
    generator = RainfallGridGenerator(
        utm_bounds=utm_bounds,
        resolution_meters=resolution_meters
    )
    
    # 生成降雨栅格文件
    return generator.generate_rainfall_rasters(
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir
    ) 