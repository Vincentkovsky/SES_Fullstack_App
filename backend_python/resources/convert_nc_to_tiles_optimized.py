#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optimized script for converting NetCDF files to GeoTIFF and map tiles
"""

import os
import sys
import glob
import argparse
import subprocess
import logging
from datetime import datetime
import multiprocessing

# Add parent directory to path to make local imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our optimized module instead of the original
from threedidepth_optimized.calculate_optimized import calculate_waterdepth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='nc_conversion_optimized.log'
)
logger = logging.getLogger(__name__)


def get_base_name(file_path):
    """从文件路径中提取基本名称"""
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)
    return name


def create_output_dirs(base_dir, name):
    """创建输出目录结构"""
    geotiff_dir = os.path.join(base_dir, "waterdepth_folder")
    tiles_dir = os.path.join(base_dir, "timeseries_tiles")
    
    # 确保目录存在
    os.makedirs(geotiff_dir, exist_ok=True)
    os.makedirs(tiles_dir, exist_ok=True)
    
    return geotiff_dir, tiles_dir


def generate_tiles(input_file, color_table, output_folder, zoom_levels="0-14", processes=8):
    """
    为GeoTIFF文件生成地图瓦片
    
    Args:
        input_file: 输入GeoTIFF文件路径
        color_table: 颜色表文件路径
        output_folder: 输出瓦片目录
        zoom_levels: 瓦片缩放级别范围
        processes: 并行处理的进程数
        
    Returns:
        生成的瓦片目录路径
    """
    logger.info(f"开始为 {input_file} 生成瓦片")
    
    # 确保输出目录存在
    os.makedirs(output_folder, exist_ok=True)
    
    # 提取时间戳作为瓦片子目录名
    base_name = os.path.basename(input_file)
    name_without_ext = os.path.splitext(base_name)[0]
    tile_dir = os.path.join(output_folder, name_without_ext)
    
    # 确保瓦片子目录存在
    os.makedirs(tile_dir, exist_ok=True)
    
    # 临时文件路径
    temp_file = os.path.join(output_folder, f"temp_{name_without_ext}.vrt")
    color_mapped_file = os.path.join(output_folder, f"colored_{name_without_ext}.tif")
    transparent_file = os.path.join(output_folder, f"transparent_{name_without_ext}.tif")
    
    try:
        # 1. 转换为VRT格式（快速）
        cmd_translate = f"gdal_translate -q -of VRT {input_file} {temp_file}"
        logger.debug(f"执行命令: {cmd_translate}")
        subprocess.run(cmd_translate, shell=True, check=True)
        
        # 2. 应用颜色映射
        cmd_color = f"gdaldem color-relief -q {temp_file} {color_table} {color_mapped_file}"
        logger.debug(f"执行命令: {cmd_color}")
        subprocess.run(cmd_color, shell=True, check=True)
        
        # 3. 添加透明度
        cmd_warp = f"gdalwarp -q -dstnodata 255 {color_mapped_file} {transparent_file}"
        logger.debug(f"执行命令: {cmd_warp}")
        subprocess.run(cmd_warp, shell=True, check=True)
        
        # 4. 生成瓦片，使用更高效的设置
        cmd_tiles = (
            f"gdal2tiles.py -q -p mercator -z {zoom_levels} "
            f"--processes={processes} {transparent_file} {tile_dir}"
        )
        logger.debug(f"执行命令: {cmd_tiles}")
        subprocess.run(cmd_tiles, shell=True, check=True)
        
        # 5. 删除临时文件
        for tmp_file in [temp_file, color_mapped_file, transparent_file]:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        
        logger.info(f"瓦片生成完成: {tile_dir}")
        return tile_dir
        
    except subprocess.CalledProcessError as e:
        logger.error(f"生成瓦片时出错: {str(e)}")
        return None


def process_nc_to_tiles(
    gridadmin_path, 
    results_path, 
    dem_path, 
    color_table,
    waterdepth_folder, 
    tiles_root_folder, 
    force_recalculate=False,
    zoom_levels="0-14", 
    processes=8
):
    """
    处理单个NetCDF文件并生成水深度TIFF和瓦片
    
    Args:
        gridadmin_path: gridadmin.h5文件路径
        results_path: NetCDF结果文件路径
        dem_path: DEM文件路径
        color_table: 颜色表文件路径
        waterdepth_folder: 水深度GeoTIFF输出目录
        tiles_root_folder: 瓦片输出根目录
        force_recalculate: 是否强制重新计算
        zoom_levels: 瓦片缩放级别
        processes: 并行处理的进程数
        
    Returns:
        处理结果信息字典
    """
    logger.info(f"处理NetCDF文件: {results_path}")
    
    # 获取文件基本名称
    base_name = get_base_name(results_path)
    
    # 确保输出目录存在
    os.makedirs(waterdepth_folder, exist_ok=True)
    os.makedirs(tiles_root_folder, exist_ok=True)
    
    # 存储已处理的水深度文件和瓦片目录
    water_depth_files = []
    tile_folders = []
    
    try:
        # 优化: 使用更多进程和优化的calculate_waterdepth函数
        # 确定处理器数量，保留至少一个核心给系统
        num_cpu = max(1, multiprocessing.cpu_count() - 1)
        
        # 水深度计算
        for i in range(24):  # 假设最多24个时间步
            waterdepth_file = os.path.join(
                waterdepth_folder, f"waterdepth_{base_name}_{i:06d}.tif"
            )
            
            # 如果文件已存在且不强制重新计算，则跳过
            if os.path.exists(waterdepth_file) and not force_recalculate:
                logger.info(f"文件已存在，跳过计算: {waterdepth_file}")
                water_depth_files.append(waterdepth_file)
                continue
                
            # 计算水深度
            try:
                logger.info(f"计算水深度 (步骤 {i}): {waterdepth_file}")
                calculate_waterdepth(
                    gridadmin_path=gridadmin_path,
                    results_3di_path=results_path,
                    dem_path=dem_path,
                    waterdepth_path=waterdepth_file,
                    calculation_steps=[i],
                    mode="lizard",
                    num_workers=num_cpu  # 使用我们优化版本的额外参数
                )
                logger.info(f"水深度计算完成: {waterdepth_file}")
                water_depth_files.append(waterdepth_file)
            except Exception as e:
                if "Maximum calculation step" in str(e):
                    # 如果超出最大计算步骤，结束循环
                    logger.info(f"已处理所有时间步（共 {i} 步）")
                    break
                else:
                    # 其他错误
                    logger.error(f"计算水深度时出错: {str(e)}")
                    raise
                    
        # 为每个水深度文件生成瓦片
        for water_depth_file in water_depth_files:
            tile_folder = generate_tiles(
                input_file=water_depth_file,
                color_table=color_table,
                output_folder=tiles_root_folder,
                zoom_levels=zoom_levels,
                processes=processes
            )
            if tile_folder:
                tile_folders.append(tile_folder)
                
        return {
            "water_depth_files": water_depth_files,
            "tile_folders": tile_folders
        }
        
    except Exception as e:
        logger.error(f"处理NetCDF文件时出错: {str(e)}")
        raise


def process_nc_file(
    nc_file_path, 
    gridadmin_path, 
    dem_path, 
    color_table, 
    base_dir,
    force_recalculate=False,
    zoom_levels="0-14", 
    processes=8
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
    
    # 优化: 推荐的进程数，考虑系统性能
    if args.processes > multiprocessing.cpu_count():
        recommended_processes = max(1, multiprocessing.cpu_count() - 1)
        print(f"\n警告: 指定的进程数 ({args.processes}) 超过了系统CPU核心数。")
        print(f"推荐使用 {recommended_processes} 个进程以获得最佳性能。")
    
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


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="批量处理NetCDF文件，转换为GeoTIFF和Tiles (优化版)")
    
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
    parser.add_argument("--processes", type=int, default=8,
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