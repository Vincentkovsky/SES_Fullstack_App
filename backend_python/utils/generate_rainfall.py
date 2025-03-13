#!/usr/bin/env python3

from datetime import datetime, timedelta
from rainfall_grid import RainfallGridGenerator, get_bounds_from_3di_results
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description='从3Di结果文件生成降雨数据')
    parser.add_argument('--resolution', type=float, default=1000, help='网格分辨率（米），默认1000（1km）')
    parser.add_argument('--output-dir', default='rainfall_output', help='输出目录')
    parser.add_argument('--utm-zone', type=int, default=55, help='UTM区域号，默认55')
    parser.add_argument('--hemisphere', choices=['north', 'south'], default='south', help='半球，默认south')
    parser.add_argument('--workers', type=int, default=4, help='并行处理进程数，默认4')
    
    args = parser.parse_args()
    
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 创建降雨网格生成器
    generator = RainfallGridGenerator(
        resolution_meters=args.resolution,
        utm_zone=args.utm_zone,
        hemisphere=args.hemisphere
    )
    
    # 设置时间范围
    # 20221008_000000-20221013_000000（5天）
    start_date = datetime.strptime("20221008_000000", "%Y%m%d_%H%M%S")
    end_date = datetime.strptime("20221013_000000", "%Y%m%d_%H%M%S")
    
    print(f"\n生成降雨数据:")
    print(f"分辨率: {args.resolution}m")
    print(f"时间范围: {start_date} 到 {end_date}")
    print(f"输出目录: {args.output_dir}")
    
    # 生成降雨数据
    output_files = generator.generate_rainfall_rasters(
        start_date=start_date.strftime("%Y%m%d_%H%M%S"),
        end_date=end_date.strftime("%Y%m%d_%H%M%S"),
        output_dir=args.output_dir,
        max_workers=args.workers
    )
    
    print(f"\n生成完成:")
    print(f"生成文件数: {len(output_files)}")
    print(f"第一个文件: {output_files[0]}")
    print(f"最后一个文件: {output_files[-1]}")

if __name__ == '__main__':
    main() 