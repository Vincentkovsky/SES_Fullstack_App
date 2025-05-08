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
import sys
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from dataclasses import dataclass
from typing import Optional
from multiprocessing import Manager, Lock
from collections import OrderedDict
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.openweatherUtils import get_historical_archive_openmeteo, decode_historical_archive_openmeteo
from pyproj import CRS, Transformer
import numpy.typing as npt

# 创建rich console实例
console = Console()

@dataclass
class RainfallCache:
    """降雨数据缓存类"""
    latitude: float
    longitude: float
    start_date: str
    end_date: str
    rainfall_data: List[float]

class SharedCache:
    """进程间共享的缓存类"""
    def __init__(self, max_size: int = 1000):
        manager = Manager()
        self.cache = manager.dict()  # 共享字典
        self.cache_lock = manager.Lock()  # 使用 manager.Lock() 而不是 Lock()
        self.hits = manager.Value('i', 0)  # 共享计数器
        self.misses = manager.Value('i', 0)  # 共享计数器
        self.max_size = max_size
        self._keys_queue = manager.list()  # 用于LRU缓存

    def get(self, key: str) -> Optional[List[float]]:
        with self.cache_lock:
            if key in self.cache:
                self.hits.value += 1
                # 更新访问顺序
                self._keys_queue.remove(key)
                self._keys_queue.append(key)
                return self.cache[key]
            self.misses.value += 1
            return None

    def put(self, key: str, value: List[float]):
        with self.cache_lock:
            # 如果缓存已满，移除最早的项
            if len(self.cache) >= self.max_size:
                oldest_key = self._keys_queue.pop(0)
                del self.cache[oldest_key]
            
            self.cache[key] = value
            self._keys_queue.append(key)

    @property
    def stats(self):
        return {
            'hits': self.hits.value,
            'misses': self.misses.value,
            'size': len(self.cache)
        }

class threediCellRainfallGenerator:
    def __init__(self, 
                 threedi_nc_path: str,
                 utm_bounds: Tuple[float, float, float, float] = (520700.0, 6104100.0, 560000.0, 6121550.0),
                 utm_zone: int = 55,
                 hemisphere: str = 'south',
                 cache_distance_threshold: float = 0.03,  # 约1km的经纬度差距
                 max_cache_size: int = 1000):  # 最大缓存条目数
        
        self.cache_distance_threshold = cache_distance_threshold
        self._shared_cache = SharedCache(max_size=max_cache_size)

        console.print("\n[bold blue]初始化threediCellRainfallGenerator...[/bold blue]")

        if hemisphere not in ['north', 'south']:
            console.print("[bold red]错误: hemisphere必须是'north'或'south'[/bold red]")
            raise ValueError("hemisphere必须是'north'或'south'")
        
        if not (1 <= utm_zone <= 60):
            console.print("[bold red]错误: UTM区域号必须在1到60之间[/bold red]")
            raise ValueError("UTM区域号必须在1到60之间")
            
        with console.status("[bold green]正在读取NetCDF文件...[/bold green]") as status:
            self.nc = xr.open_dataset(threedi_nc_path)
            self.cellCnt = self.nc.sizes['nMesh2D_nodes']
            self.cellX = self.nc['Mesh2DFace_xcc']
            self.cellY = self.nc['Mesh2DFace_ycc']
            self.Mesh2DContour_x = self.nc['Mesh2DContour_x']
            self.nc.close()
            
        console.print(f"[green]✓[/green] 成功读取网格数据，共 [bold]{self.cellCnt}[/bold] 个网格点")

        self.bounds = utm_bounds
        self.utm_zone = utm_zone
        self.hemisphere = hemisphere

        with console.status("[bold green]设置坐标转换器...[/bold green]"):
            self.utm_proj = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
            self.wgs84_proj = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
            self.transformer = pyproj.Transformer.from_crs(self.utm_proj, self.wgs84_proj)

        with console.status("[bold green]转换网格坐标...[/bold green]"):
            self.cell_lons, self.cell_lats = self.transformer.transform(self.cellX, self.cellY)

        console.print("[bold green]计算网格面积...[/bold green]")
        # 使用NumPy向量化操作计算面积
        contour_x_array = np.array(self.Mesh2DContour_x)
        edge_lengths = np.max(contour_x_array, axis=1) - np.min(contour_x_array, axis=1)
        self.area = edge_lengths * edge_lengths
        console.print("[bold green]✓ 网格面积计算完成[/bold green]")
        
        console.print("[bold green]✓ 初始化完成！[/bold green]\n")

    def _convert_rain_to_m3s(self, rain_data: List[float]) -> List[float]:
        """将降雨数据从mm/hr转换为m3/s"""
        return [rain * self.area[i] / 3600000 for i, rain in enumerate(rain_data)]

    def _get_cache_key(self, lat: float, lon: float, start_date: str, end_date: str) -> str:
        """生成缓存键"""
        # 将经纬度按照阈值进行离散化，以增加缓存命中率
        lat_grid = round(lat / self.cache_distance_threshold) * self.cache_distance_threshold
        lon_grid = round(lon / self.cache_distance_threshold) * self.cache_distance_threshold
        return f"{lat_grid}:{lon_grid}:{start_date}:{end_date}"

    def _get_rainfall_for_point(self, args) -> Tuple[int, List[float], bool]:
        """获取单个点的降雨数据（用于并行处理）"""
        i, lat, lon, start_date, end_date = args
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 生成缓存键
                cache_key = self._get_cache_key(lat, lon, start_date, end_date)
                
                # 检查缓存
                cached_data = self._shared_cache.get(cache_key)
                if cached_data is not None:
                    return i, cached_data, True  # True表示缓存命中

                data = get_historical_archive_openmeteo(
                    latitude=lat,
                    longitude=lon,
                    start_date=start_date,
                    end_date=end_date,
                    hourly_params=["rain"]
                )
                if data:
                    decoded_data = decode_historical_archive_openmeteo(data)
                    rainfall_data = decoded_data.get('rain', [])
                    # 添加到缓存
                    self._shared_cache.put(cache_key, rainfall_data)
                    return i, rainfall_data, False  # False表示API获取
                return i, [], False
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    console.print(f"[bold red]Error getting rainfall data for point ({lat}, {lon}) after {max_retries} retries: {e}[/bold red]")
                    return i, [], False
                # 等待短暂时间后重试
                import time
                time.sleep(1)  # 1秒后重试

    def generate_threedi_cell_rainfall_netcdf(self,
                                        start_date: str,
                                        end_date: str,
                                        output_dir: str,
                                        max_workers: int = 2,  # 减少并发请求数
                                        timeout: int = 5) -> Dict[str, str]:
        
        # 显示任务信息面板
        info_text = Text()
        info_text.append("降雨NetCDF文件生成任务\n", style="bold blue")
        info_text.append(f"时间范围: {start_date} 到 {end_date}\n", style="green")
        info_text.append(f"输出目录: {output_dir}\n", style="green")
        info_text.append(f"并行进程数: {max_workers}\n", style="green")
        info_text.append(f"缓存距离阈值: {self.cache_distance_threshold}度\n", style="green")
        info_text.append(f"最大缓存条目数: {self._shared_cache.max_size}", style="green")
        console.print(Panel(info_text, title="任务信息"))
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 准备并行处理参数
        args_list = [
            (i, self.cell_lats[i], self.cell_lons[i], start_date, end_date)
            for i in range(self.cellCnt)
        ]
        
        total_points = self.cellCnt



        with console.status("[bold green]处理时间戳信息...[/bold green]") as status:
            sample_data = get_historical_archive_openmeteo(
                latitude=self.cell_lats[0],
                longitude=self.cell_lons[0],
                start_date=start_date,
                end_date=end_date,
                hourly_params=["rain"]
            )
            timestamps = decode_historical_archive_openmeteo(sample_data)['timestamps']
        
        console.print("[bold blue]生成时间戳序列...[/bold blue]")
        half_hour_timestamps = []
        hourly_timestamps = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task2 = progress.add_task("处理时间戳", total=len(timestamps)-1)
            for i in range(len(timestamps)-1):
                current_time = datetime.fromisoformat(timestamps[i])
                next_time = datetime.fromisoformat(timestamps[i+1])
                half_time = current_time + (next_time - current_time) / 2
                
                half_hour_timestamps.append(current_time.strftime("%Y-%m-%dT%H:%M"))
                half_hour_timestamps.append(half_time.strftime("%Y-%m-%dT%H:%M"))
                hourly_timestamps.append(current_time)
                progress.update(task2, advance=1)
        
        half_hour_timestamps.append(timestamps[-1])
        hourly_timestamps.append(datetime.fromisoformat(timestamps[-1]))


        console.print(f"\n[bold blue]开始获取降雨数据[/bold blue] (共 {total_points} 个网格点)")

        # Initialize empty array for rainfall data
        rainfall_data = {}
        failed_points = []  # 记录失败的点
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            main_task = progress.add_task(
                "获取降雨数据",
                total=total_points
            )
            
            with mp.Pool(max_workers) as pool:
                try:
                    # 使用imap_unordered和超时机制
                    for result in pool.imap_unordered(self._get_rainfall_for_point, args_list, chunksize=10):
                        try:
                            i, rain_values, is_cached = result
                            if not rain_values:  # 如果获取失败
                                failed_points.append(i)
                            rainfall_data[i] = self._convert_rain_to_m3s(rain_values) if rain_values else [0.0] * len(half_hour_timestamps)  # 使用默认值
                            
                            # 更新进度条和描述
                            progress.update(main_task, advance=1)
                            stats = self._shared_cache.stats
                            progress.update(
                                main_task,
                                description=f"获取降雨数据 [已完成: {len(rainfall_data)}, 缓存命中: {stats['hits']}, API请求: {stats['misses']}, 失败: {len(failed_points)}]"
                            )
                        except Exception as e:
                            console.print(f"[bold red]Error processing result: {e}[/bold red]")
                            continue
                except KeyboardInterrupt:
                    pool.terminate()
                    pool.join()
                    console.print("[bold red]任务被用户中断[/bold red]")
                    raise
                except Exception as e:
                    pool.terminate()
                    pool.join()
                    console.print(f"[bold red]发生错误: {e}[/bold red]")
                    raise

        # 如果有失败的点，显示统计信息
        if failed_points:
            console.print(f"\n[bold yellow]警告: {len(failed_points)} 个点的数据获取失败[/bold yellow]")
            console.print("这些点将使用默认值(0)填充")


        console.print("[bold blue]构建降雨数组...[/bold blue]")
        halfhourly_rainfall_array = np.zeros((len(half_hour_timestamps), self.cellCnt), dtype=np.float32)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task3 = progress.add_task("处理降雨数据", total=len(half_hour_timestamps))
            for t in range(len(half_hour_timestamps)):
                if t % 2 == 0:
                    hour_index = t // 2
                    for i in range(self.cellCnt):
                        halfhourly_rainfall_array[t, i] = rainfall_data.get(i)[hour_index]
                else:
                    hour_index = t // 2
                    for i in range(self.cellCnt):
                        halfhourly_rainfall_array[t, i] = rainfall_data.get(i)[hour_index]
                        if hour_index + 1 < len(rainfall_data.get(i)):
                            halfhourly_rainfall_array[t, i] = rainfall_data.get(i)[hour_index + 1]
                progress.update(task3, advance=1)

        with console.status("[bold green]准备NetCDF数据...[/bold green]"):
            unix_epoch = np.datetime64('1970-01-01T00:00:00', 'us')
            hourly_time_steps = np.array(hourly_timestamps, dtype='datetime64[s]')
            hourly_time_steps_seconds = ((hourly_time_steps - unix_epoch) / np.timedelta64(1, 's'))

            console.print("[bold blue]创建NetCDF数据集...[/bold blue]")
            # 创建半小时时间戳的秒数
            half_hour_time_steps = np.array([datetime.fromisoformat(ts) for ts in half_hour_timestamps], dtype='datetime64[s]')
            half_hour_time_steps_seconds = ((half_hour_time_steps - unix_epoch) / np.timedelta64(1, 's'))

            ds = xr.Dataset(
                coords={
                    'time': ('time', half_hour_time_steps_seconds, {  # 使用半小时时间戳
                        'standard_name': 'time',
                        'long_name': 'Time',
                        'units': 'seconds since 1970-01-01 00:00:00.0 +0000',
                        'calendar': 'standard',
                        'axis': 'T'
                    }),
                    'Mesh2DFace_xcc': ('nMesh2D_nodes', self.cellX.data, {
                        'long_name': 'x-coordinate of cell center',
                        'units': 'm'
                    }),
                    'Mesh2DFace_ycc': ('nMesh2D_nodes', self.cellY.data, {
                        'long_name': 'y-coordinate of cell center',
                        'units': 'm'
                    })
                }
            )
            
            # 添加降雨数据
            ds['Mesh2D_rain'] = xr.DataArray(
                halfhourly_rainfall_array,
                dims=('time', 'nMesh2D_nodes'),
                attrs={
                    'long_name': 'rain',
                    'grid_mapping': 'crs',
                    '_FillValue': 0,
                    'missing_value': 0,
                    'units': 'm3/s'
                }
            )
            
            # 添加全局属性
            ds.attrs = {
                'OFFSET': 0,
                'Conventions': 'CF-1.6',
                'title': 'Half-hourly Rainfall data',
                'institution': 'Generated by threediCellRainfallGenerator',
                'source': 'Open-Meteo API',
                'references': 'https://open-meteo.com/'
            }
            
            # 保存NetCDF文件
            nc_filename = f"rainfall_{hourly_timestamps[0].strftime('%Y%m%d%H%M')}_{hourly_timestamps[-1].strftime('%Y%m%d%H%M')}.nc"
            nc_filepath = str(Path(output_dir) / nc_filename)
            
            console.print(f"[bold green]保存NetCDF文件到: {nc_filepath}[/bold green]")
            ds.to_netcdf(nc_filepath, format='NETCDF4')
            console.print("[bold green]✓ NetCDF文件生成完成！[/bold green]")

        # 在完成后显示缓存统计信息
        stats = self._shared_cache.stats
        total_requests = stats['hits'] + stats['misses']
        if total_requests > 0:
            hit_rate = (stats['hits'] / total_requests) * 100
            console.print(f"\n[bold blue]缓存统计:[/bold blue]")
            console.print(f"总请求数: {total_requests}")
            console.print(f"缓存命中: {stats['hits']}")
            console.print(f"缓存未命中: {stats['misses']}")
            console.print(f"缓存命中率: {hit_rate:.2f}%")
            console.print(f"当前缓存大小: {stats['size']}")

        return {
            'netcdf': nc_filepath
        }