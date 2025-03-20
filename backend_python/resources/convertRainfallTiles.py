from pathlib import Path
import logging
from typing import List, Tuple
import re
from datetime import datetime
import shutil
import sys
from os.path import dirname, abspath

# Add the parent directory to sys.path to enable imports
parent_dir = dirname(dirname(abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from utils.tileGeneratorUtils import TileGeneratorUtils, TileGeneratorConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rainfall_tiles_conversion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_date_from_path(path: str) -> Tuple[str, str]:
    """
    从路径中提取开始和结束日期
    例如: '.../20221008_000000_20221013_000000/...' -> ('20221008_000000', '20221013_000000')
    """
    pattern = r'(\d{8}_\d{6})_(\d{8}_\d{6})'
    match = re.search(pattern, str(path))
    if not match:
        raise ValueError(f"无法从路径中提取日期: {path}")
    return match.groups()

def get_geotiff_files(input_dir: Path) -> List[Path]:
    """获取目录下所有的GeoTIFF文件"""
    return sorted([f for f in input_dir.glob("*.tif")])

def setup_output_dir(rainfall_dir: Path) -> Path:
    """设置输出目录在降雨数据目录下的tiles子目录中"""
    output_dir = rainfall_dir / "tiles"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def convert_tiffs_to_tiles(
    input_dir: Path,
    rainfall_dir: Path,
    color_table: Path,
    tile_generator: TileGeneratorUtils
) -> bool:
    """
    将指定目录下的所有GeoTIFF文件转换为瓦片
    
    Args:
        input_dir: GeoTIFF文件所在目录
        rainfall_dir: 降雨数据主目录
        color_table: 颜色表文件路径
        tile_generator: TileGeneratorUtils实例
    
    Returns:
        bool: 是否全部转换成功
    """
    try:
        # 设置输出目录在降雨数据目录下
        output_dir = setup_output_dir(rainfall_dir)
        logger.info(f"Processing directory: {input_dir}")
        logger.info(f"Output directory: {output_dir}")
        
        # 获取所有GeoTIFF文件
        tiff_files = get_geotiff_files(input_dir)
        if not tiff_files:
            logger.warning(f"No GeoTIFF files found in {input_dir}")
            return False
            
        success_count = 0
        total_files = len(tiff_files)
        
        # 处理每个文件
        for i, tiff_file in enumerate(tiff_files, 1):
            timestamp = tiff_file.stem  # 获取文件名（不含扩展名）作为时间戳
            tile_output_dir = output_dir / timestamp
            
            logger.info(f"Converting file {i}/{total_files}: {tiff_file.name}")
            
            # 生成瓦片
            if tile_generator.generate_tiles(
                input_file=tiff_file,
                color_table=color_table,
                output_folder=tile_output_dir,
                cleanup_temp=True
            ):
                success_count += 1
                logger.info(f"Successfully generated tiles for {tiff_file.name}")
            else:
                logger.error(f"Failed to generate tiles for {tiff_file.name}")
        
        # 报告处理结果
        logger.info(f"Processed {total_files} files, {success_count} successful")
        return success_count == total_files
        
    except Exception as e:
        logger.error(f"Error processing directory {input_dir}: {str(e)}")
        return False

def main():
    try:
        # 设置路径
        current_dir = Path(__file__).parent.resolve()
        data_dir = current_dir.parent / "data"
        rainfall_data_dir = data_dir / "rainfall_data"
        color_table = current_dir / "rainfallColor.txt"

        # 验证颜色表
        if not TileGeneratorUtils.validate_color_table(color_table):
            logger.error("Invalid color table")
            return

        # 配置瓦片生成器
        config = TileGeneratorConfig(
            zoom_levels="0-14",
            processes=8,
            xyz_format=True
        )
        tile_generator = TileGeneratorUtils(config)

        # 获取所有降雨数据目录
        rainfall_dirs = [d for d in rainfall_data_dir.glob("*_*") if d.is_dir()]
        
        if not rainfall_dirs:
            logger.warning("No rainfall data directories found")
            return

        # 处理每个目录
        for rainfall_dir in rainfall_dirs:
            geotiff_dir = rainfall_dir / "geotiff"
            if not geotiff_dir.exists():
                logger.warning(f"No geotiff directory found in {rainfall_dir}")
                continue

            logger.info(f"\nProcessing rainfall data in: {rainfall_dir}")
            success = convert_tiffs_to_tiles(
                input_dir=geotiff_dir,
                rainfall_dir=rainfall_dir,
                color_table=color_table,
                tile_generator=tile_generator
            )
            
            if success:
                logger.info(f"Successfully processed all files in {rainfall_dir}")
            else:
                logger.warning(f"Some files in {rainfall_dir} failed to process")

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main() 