#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NetCDF转GeoTIFF和Tiles批处理脚本

该脚本用于批量处理3di_res/netcdf文件夹下的NetCDF文件，将其转换为GeoTIFF和地图瓦片。
输出将组织为特定的目录结构:
- GeoTIFF文件: 3di_res/geotiff/{name}/ 目录
- Tile文件: 3di_res/tiles/{name}/ 目录

其中{name}是从NetCDF文件名中提取的(格式为name.nc或startTime_endTime.nc)

使用方法:
    python convert_nc_to_tiles.py

依赖项:
    - ncToTilesUtils模块
    - tqdm用于进度显示
"""

import os
import sys
import glob
import logging
import argparse
from pathlib import Path
from datetime import datetime

# 添加父目录到路径，以便导入utils模块
sys.path.append(str(Path(__file__).parent.parent))

from utils.ncToTilesUtils import process_nc_to_tiles

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("nc_conversion.log")
    ]
)
logger = logging.getLogger(__name__)


def get_base_name(nc_file_path):
    """
    从NetCDF文件路径中提取基本名称
    
    Args:
        nc_file_path: NetCDF文件路径
        
    Returns:
        不带扩展名的基本文件名
    """
    # 获取文件名（不含路径）
    file_name = os.path.basename(nc_file_path)
    # 移除扩展名
    base_name = os.path.splitext(file_name)[0]
    return base_name


def create_output_dirs(base_dir, name):
    """
    创建输出目录结构
    
    Args:
        base_dir: 基础目录路径
        name: 从NetCDF文件名中提取的名称
        
    Returns:
        包含geotiff和tiles路径的元组
    """
    # 创建GeoTIFF输出目录
    geotiff_dir = os.path.join(base_dir, "geotiff", name)
    os.makedirs(geotiff_dir, exist_ok=True)
    
    # 创建Tiles输出目录
    tiles_dir = os.path.join(base_dir, "tiles", name)
    os.makedirs(tiles_dir, exist_ok=True)
    
    return geotiff_dir, tiles_dir


def process_nc_file(
    nc_file_path, 
    gridadmin_path, 
    dem_path, 
    color_table, 
    base_dir,
    force_recalculate=False,
    zoom_levels="0-14", 
    processes=128
):
    """
    处理单个NetCDF文件
    
    Args:
        nc_file_path: NetCDF文件路径
        gridadmin_path: gridadmin.h5文件路径
        dem_path: DEM文件路径
        color_table: 颜色表文件路径
        base_dir: 基础输出目录
        force_recalculate: 是否强制重新计算
        zoom_levels: 瓦片缩放级别
        processes: 并行处理的进程数
        
    Returns:
        处理结果信息字典
    """
    try:
        # 检查DEM文件是否存在
        if not os.path.exists(dem_path):
            raise FileNotFoundError(f"DEM文件不存在: {dem_path}")
            
        # 检查gridadmin文件是否存在
        if not os.path.exists(gridadmin_path):
            raise FileNotFoundError(f"gridadmin.h5文件不存在: {gridadmin_path}")
            
        # 从文件名中提取基本名称
        name = get_base_name(nc_file_path)
        
        # 创建输出目录
        geotiff_dir, tiles_dir = create_output_dirs(base_dir, name)
        
        # 打印开始处理信息
        print(f"\n{'='*60}")
        print(f"开始处理文件: {os.path.basename(nc_file_path)}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DEM文件: {dem_path}")
        print(f"gridadmin文件: {gridadmin_path}")
        print(f"{'='*60}")
        
        # 调用处理函数
        result = process_nc_to_tiles(
            gridadmin_path=gridadmin_path,
            results_path=nc_file_path,
            dem_path=dem_path,
            color_table=color_table,
            waterdepth_folder=geotiff_dir,
            tiles_root_folder=tiles_dir,
            force_recalculate=force_recalculate,
            zoom_levels=zoom_levels,
            processes=processes
        )
        
        # 打印完成信息
        print(f"\n{'='*60}")
        print(f"文件处理完成: {os.path.basename(nc_file_path)}")
        print(f"输出GeoTIFF目录: {geotiff_dir}")
        print(f"输出Tiles目录: {tiles_dir}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        return {
            "name": name,
            "nc_file": nc_file_path,
            "geotiff_dir": geotiff_dir,
            "tiles_dir": tiles_dir,
            "geotiff_count": len(result["water_depth_files"]),
            "tiles_count": len(result["tile_folders"])
        }
        
    except Exception as e:
        logger.error(f"处理文件 {nc_file_path} 时出错: {str(e)}")
        return {
            "name": get_base_name(nc_file_path),
            "nc_file": nc_file_path,
            "error": str(e)
        }


def process_all_nc_files(args):
    """
    处理指定目录下的所有NetCDF文件
    
    Args:
        args: 命令行参数
    """
    # 查找所有NetCDF文件
    nc_pattern = os.path.join(args.netcdf_dir, "*.nc")
    nc_files = glob.glob(nc_pattern)
    
    if not nc_files:
        logger.error(f"在目录 {args.netcdf_dir} 中未找到NetCDF文件")
        return
    
    logger.info(f"找到 {len(nc_files)} 个NetCDF文件需要处理")
    
    # 确保颜色表存在
    if not os.path.exists(args.color_table):
        logger.error(f"颜色表文件不存在: {args.color_table}")
        return
    
    # 确保DEM文件存在
    if not os.path.exists(args.dem_path):
        logger.error(f"DEM文件不存在: {args.dem_path}")
        print(f"\n错误: DEM文件不存在 - {args.dem_path}")
        print("请确保DEM文件存在或使用 --dem-path 参数指定正确的路径")
        return
        
    # 确保gridadmin文件存在
    if not os.path.exists(args.gridadmin_path):
        logger.error(f"gridadmin.h5文件不存在: {args.gridadmin_path}")
        print(f"\n错误: gridadmin.h5文件不存在 - {args.gridadmin_path}")
        print("请确保gridadmin.h5文件存在或使用 --gridadmin-path 参数指定正确的路径")
        return
    
    # 记录开始时间
    start_time = datetime.now()
    logger.info(f"批处理开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"使用DEM文件: {args.dem_path}")
    logger.info(f"使用gridadmin文件: {args.gridadmin_path}")

    # 存储处理结果
    results = []
    
    # 处理每个文件
    for i, nc_file in enumerate(nc_files, 1):
        logger.info(f"处理文件 {i}/{len(nc_files)}: {os.path.basename(nc_file)}")
        
        result = process_nc_file(
            nc_file_path=nc_file,
            gridadmin_path=args.gridadmin_path,
            dem_path=args.dem_path,
            color_table=args.color_table,
            base_dir=args.base_dir,
            force_recalculate=args.force_recalculate,
            zoom_levels=args.zoom_levels,
            processes=args.processes
        )
        
        results.append(result)
    
    # 记录结束时间
    end_time = datetime.now()
    duration = end_time - start_time
    
    # 打印汇总信息
    print(f"\n{'='*60}")
    print("批处理完成汇总")
    print(f"{'='*60}")
    print(f"处理的NetCDF文件总数: {len(nc_files)}")
    print(f"成功处理的文件数: {sum(1 for r in results if 'error' not in r)}")
    print(f"失败的文件数: {sum(1 for r in results if 'error' in r)}")
    print(f"总运行时间: {duration}")
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 打印失败的文件列表（如果有）
    failed_files = [r for r in results if 'error' in r]
    if failed_files:
        print("\n失败的文件列表:")
        for f in failed_files:
            print(f"  - {f['name']}: {f['error']}")
    
    logger.info(f"批处理结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"总运行时间: {duration}")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="批量处理NetCDF文件，转换为GeoTIFF和Tiles")
    
    # 必要参数
    parser.add_argument("--netcdf-dir", default="../data/3di_res/netcdf",
                      help="包含NetCDF文件的目录 (默认: ../data/3di_res/netcdf)")
    parser.add_argument("--base-dir", default="../data/3di_res",
                      help="基础输出目录 (默认: ../data/3di_res)")
    parser.add_argument("--gridadmin-path", default="../data/3di_res/gridadmin.h5",
                      help="gridadmin.h5文件路径 (默认: ../data/3di_res/gridadmin.h5)")
    parser.add_argument("--dem-path", default="../data/3di_res/5m_dem.tif",
                      help="DEM文件路径 (默认: ../data/3di_res/5m_dem.tif)")
    parser.add_argument("--color-table", default="color.txt",
                      help="颜色表文件路径 (默认: color.txt)")
    
    # 可选参数
    parser.add_argument("--force-recalculate", action="store_true",
                      help="强制重新计算已存在的文件")
    parser.add_argument("--zoom-levels", default="0-14",
                      help="瓦片缩放级别 (默认: 0-14)")
    parser.add_argument("--processes", type=int, default=128,
                      help="并行处理的进程数 (默认: 8)")
    
    return parser.parse_args()


if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()
    
    try:
        # 批量处理NetCDF文件
        process_all_nc_files(args)
    except KeyboardInterrupt:
        logger.info("用户中断了处理")
        print("\n处理被用户中断")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {str(e)}")
        print(f"\n处理过程中发生错误: {str(e)}") 