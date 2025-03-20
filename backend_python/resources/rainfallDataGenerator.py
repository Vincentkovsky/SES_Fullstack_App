from pathlib import Path
import sys
from dataclasses import dataclass
from datetime import datetime
import multiprocessing as mp
import json
import time
from typing import Dict, List, Tuple, Union

from ..utils.rainfallGridUtils import RainfallGridGenerator, get_bounds_from_3di_results

# Get the current file's directory
CURRENT_DIR = Path(__file__).parent.resolve()
PROGRESS_FILE = CURRENT_DIR / 'rainfall_generation_progress.json'

@dataclass
class GridBounds:
    minx: float
    miny: float
    maxx: float
    maxy: float

def convert_date_format(date_str: str) -> str:
    """
    将 'YYYYMMDD_HHMMSS' 格式转换为 'YYYY-MM-DD' 格式
    """
    dt = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
    return dt.strftime("%Y-%m-%d")

def create_time_based_dir(base_dir: str, start_date: str, end_date: str) -> str:
    """
    根据时间段创建目录结构
    
    Args:
        base_dir: 基础目录
        start_date: 开始日期 (YYYYMMDD_HHMMSS格式)
        end_date: 结束日期 (YYYYMMDD_HHMMSS格式)
    
    Returns:
        str: 创建的目录路径
    """
    # 提取日期部分用于目录名
    start_dir = start_date[:8]  # YYYYMMDD
    end_dir = end_date[:8]      # YYYYMMDD
    
    # 创建目录路径
    time_dir = f"{start_dir}_to_{end_dir}"
    full_path = Path(base_dir) / time_dir
    
    # 确保目录存在
    full_path.mkdir(parents=True, exist_ok=True)
    return str(full_path)

def load_progress(progress_file: Path) -> Dict[str, Dict[str, Union[str, int]]]:
    """
    加载已处理的时间段记录
    """
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_progress(progress_file: Path, progress: Dict[str, Dict[str, Union[str, int]]]):
    """
    保存处理进度
    """
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)

def main():
    """
    主函数：生成降雨数据
    """
    # 设置输入和输出路径
    input_dir = CURRENT_DIR / "rainfall_forecast_json"
    output_base_dir = CURRENT_DIR / "rainfall_tiles"
    progress_file = PROGRESS_FILE

    # 确保输出目录存在
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # 加载进度
    progress = load_progress(progress_file) if progress_file.exists() else {}

    # 定义要生成的时间段
    time_periods = [
        ("20221008_000000", "20221013_000000"),
        ("20221101_000000", "20221106_000000"),
        ("20221024_000000", "20221030_000000")
    ]

    # 创建降雨网格生成器
    generator = RainfallGridGenerator(
        resolution_meters=1000  # 使用1000米分辨率以减少API调用次数
    )

    # 为每个时间段生成数据
    for original_start_date, original_end_date in time_periods:
        period_key = f"{original_start_date}_to_{original_end_date}"
        
        # 检查是否已经处理过这个时间段
        if period_key in progress:
            print(f"\n时间段 {original_start_date} 到 {original_end_date} 已处理，跳过...")
            continue
            
        print(f"\n生成时间段 {original_start_date} 到 {original_end_date} 的数据...")
        
        try:
            # 创建基于时间的输出目录
            time_based_dir = create_time_based_dir(output_base_dir, original_start_date, original_end_date)
            
            # 转换日期格式用于API调用
            api_start_date = convert_date_format(original_start_date)
            api_end_date = convert_date_format(original_end_date)
            
            max_workers = 4
            
            # 生成降雨数据
            result = generator.generate_rainfall_rasters(
                start_date=api_start_date,
                end_date=api_end_date,
                output_dir=time_based_dir,  # 使用基于时间的目录
                max_workers=max_workers
            )
            
            # 从结果中获取文件路径
            geotiff_files = result['geotiff']
            netcdf_files = result['netcdf']
            
            print(f"成功生成数据:")
            print(f"- 输出目录: {time_based_dir}")
            print(f"- NetCDF文件: {netcdf_files[0] if netcdf_files else 'None'}")
            print(f"- 生成了 {len(geotiff_files)} 个GeoTIFF文件")
            
            # 记录处理成功的时间段
            progress[period_key] = {
                "start_date": original_start_date,
                "end_date": original_end_date,
                "completed_at": datetime.now().isoformat(),
                "output_dir": time_based_dir,
                "netcdf_file": netcdf_files[0] if netcdf_files else None,
                "tiff_files_count": len(geotiff_files),
                "tiff_files": geotiff_files
            }
            save_progress(progress_file, progress)
            
            # 添加短暂延迟以避免API限制
            time.sleep(2)
            
        except Exception as e:
            print(f"生成数据时出错: {e}")
            continue

    print("\n所有数据生成完成！")

if __name__ == '__main__':
    try:
        # 设置多进程启动方法为'spawn'以避免fork相关问题
        mp.set_start_method('spawn')
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断。您可以稍后重新运行程序，将从上次成功的位置继续处理。") 