#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
3Di Results Processing Example

This script demonstrates how to:
1. Download 3Di simulation results using download_3di_results.py
2. Process the results to generate water depth files
3. Convert water depth files to map tiles using ncToTilesUtils.py

This can be used as a template for your own processing workflow.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("3di_processing.log")
    ]
)
logger = logging.getLogger(__name__)

# Check if required modules are available
try:
    # Import from the same package
    from .download_3di_results import SimulationDownloader, load_config_from_file
    
    # Import from utils package
    # Adjust path based on the location of ncToTilesUtils.py
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from utils.ncToTilesUtils import process_nc_to_tiles
except ImportError:
    logger.error("Required modules not found. Make sure download_3di_results.py and ncToTilesUtils.py are in the correct directories.")
    sys.exit(1)


def download_simulation_results(config_file: str, simulation_id: int = None, username: str = None) -> dict:
    """
    Download 3Di simulation results using the SimulationDownloader class.
    
    Args:
        config_file: Path to the configuration file
        simulation_id: Specific simulation ID to download (optional)
        username: Filter simulations by username (optional)
        
    Returns:
        Dictionary with paths to downloaded files
    """
    logger.info("Starting 3Di simulation results download")
    
    # Load configuration from file
    try:
        config = load_config_from_file(config_file)
        logger.info(f"Loaded configuration from {config_file}")
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        sys.exit(1)
    
    # Initialize downloader
    output_dir = config.get("DEFAULT_OUTPUT_DIR") or "../data/3di"
    downloader = SimulationDownloader(config, output_dir=output_dir)
    
    # Download specific simulation or latest one
    try:
        if simulation_id:
            logger.info(f"Downloading simulation with ID: {simulation_id}")
            downloaded = downloader.download_result_files(
                simulation_id=simulation_id,
                include_gridadmin=config.get("DEFAULT_OPTIONS", {}).get("include_gridadmin", True),
                file_types=config.get("DEFAULT_OPTIONS", {}).get("file_types")
            )
        else:
            logger.info(f"Downloading latest simulation for username: {username}")
            downloaded = downloader.select_and_download_latest(
                username=username,
                include_gridadmin=config.get("DEFAULT_OPTIONS", {}).get("include_gridadmin", True),
                file_types=config.get("DEFAULT_OPTIONS", {}).get("file_types")
            )
        
        # Print summary
        logger.info(f"Downloaded {len(downloaded['result_files'])} result files")
        for path in downloaded['result_files']:
            logger.debug(f"Downloaded: {path}")
        
        if downloaded.get('gridadmin'):
            logger.info(f"Downloaded gridadmin file: {downloaded['gridadmin'][0]}")
        
        return downloaded
        
    except Exception as e:
        logger.error(f"Error downloading simulation results: {str(e)}")
        sys.exit(1)


def find_netcdf_file(downloaded_files: list) -> Path:
    """Find the main NetCDF results file from downloaded files."""
    for file_path in downloaded_files:
        file_path = Path(file_path)
        if file_path.suffix.lower() == '.nc' and 'results_3di' in file_path.name.lower():
            return file_path
    
    # If no specific results_3di.nc file is found, return the first .nc file
    for file_path in downloaded_files:
        file_path = Path(file_path)
        if file_path.suffix.lower() == '.nc':
            return file_path
    
    return None


def find_dem_file(simulation_dir: Path, data_dir: Path = None) -> Path:
    """
    Find the DEM file in either the simulation directory or the data directory.
    
    Args:
        simulation_dir: Directory of the simulation
        data_dir: Base data directory (e.g., data/3di_res)
        
    Returns:
        Path to the DEM file or None if not found
    """
    # Default data directory if not specified
    if data_dir is None:
        # Get script directory
        script_dir = Path(__file__).resolve().parent
        data_dir = script_dir.parent / "data" / "3di_res"
    
    # Try to find DEM in the simulation directory
    dem_patterns = ["*dem*.tif", "*DEM*.tif", "*.tif"]
    for pattern in dem_patterns:
        dem_files = list(simulation_dir.glob(pattern))
        if dem_files:
            return dem_files[0]
    
    # Try to find in simulation's geotiff folder
    geotiff_dir = simulation_dir / "geotiff"
    if geotiff_dir.exists():
        for pattern in dem_patterns:
            dem_files = list(geotiff_dir.glob(pattern))
            if dem_files:
                return dem_files[0]
    
    # Look in the 3di_res directory
    if data_dir.exists():
        for pattern in dem_patterns:
            dem_files = list(data_dir.glob(pattern))
            if dem_files:
                return dem_files[0]
        
        # Check specifically for 5m_dem.tif which is commonly used
        specific_dem = data_dir / "5m_dem.tif"
        if specific_dem.exists():
            return specific_dem
    
    return None


def process_results(downloaded_files: dict, color_table: str, force_recalculate: bool = False) -> dict:
    """
    Process downloaded 3Di results to generate water depth files and map tiles.
    
    Args:
        downloaded_files: Dictionary with paths to downloaded files (from download_simulation_results)
        color_table: Path to the color table file for tile generation
        force_recalculate: Force recalculation of water depth files
        
    Returns:
        Dictionary with paths to generated files
    """
    logger.info("Starting 3Di results processing")
    
    # Find necessary files
    result_files = downloaded_files.get('result_files', [])
    gridadmin_files = downloaded_files.get('gridadmin', [])
    
    if not result_files:
        logger.error("No result files found to process")
        return {}
    
    if not gridadmin_files:
        logger.error("No gridadmin.h5 file found, required for processing")
        return {}
    
    # Find the main NetCDF results file
    results_nc = find_netcdf_file(result_files)
    if not results_nc:
        logger.error("No NetCDF results file found")
        return {}
    
    gridadmin_path = gridadmin_files[0]
    
    # Get the simulation directory from the netcdf file path
    # The structure should be data/3di/sim_YYYYMMDD/netcdf/file.nc
    simulation_dir = Path(results_nc).parent.parent
    
    # Find the DEM file
    dem_path = find_dem_file(simulation_dir)
    
    if not dem_path or not os.path.exists(dem_path):
        logger.warning(f"DEM file not found automatically. Please specify correct DEM path.")
        dem_path = input("Please enter path to DEM file: ")
        if not os.path.exists(dem_path):
            logger.error(f"DEM file not found at {dem_path}")
            return {}
    
    # Process results using ncToTilesUtils
    try:
        logger.info("Processing NetCDF to generate water depth files and tiles")
        logger.info(f"NetCDF file: {results_nc}")
        logger.info(f"Gridadmin file: {gridadmin_path}")
        logger.info(f"DEM file: {dem_path}")
        logger.info(f"Color table: {color_table}")
        
        # Set up output folders
        waterdepth_folder = simulation_dir / "waterdepth_folder"
        tiles_folder = simulation_dir / "tiles"
        
        waterdepth_folder.mkdir(exist_ok=True)
        tiles_folder.mkdir(exist_ok=True)
        
        # Call the main processing function from ncToTilesUtils
        processing_result = process_nc_to_tiles(
            gridadmin_path=str(gridadmin_path),
            results_path=str(results_nc),
            dem_path=str(dem_path),
            color_table=color_table,
            waterdepth_folder=str(waterdepth_folder),
            tiles_root_folder=str(tiles_folder),
            force_recalculate=force_recalculate,
            zoom_levels="0-14",
            processes=8
        )
        
        logger.info("Processing completed successfully")
        return processing_result
        
    except Exception as e:
        logger.error(f"Error processing results: {str(e)}")
        return {}


def main():
    """Main function to handle command line arguments and execute the workflow."""
    parser = argparse.ArgumentParser(description="Download and process 3Di simulation results")
    
    parser.add_argument("--config-file", required=True,
                       help="Path to JSON configuration file for API credentials")
    parser.add_argument("--simulation-id", type=int,
                       help="Specific simulation ID to download and process")
    parser.add_argument("--username",
                       help="Filter simulations by username (if simulation-id not provided)")
    parser.add_argument("--color-table", default="color.txt",
                       help="Path to color table file for water depth visualization (default: color.txt)")
    parser.add_argument("--force-recalculate", action="store_true",
                       help="Force recalculation of water depth files even if they exist")
    parser.add_argument("--download-only", action="store_true",
                       help="Only download files without processing")
    parser.add_argument("--dem-path",
                      help="Path to DEM file (if not found automatically)")
    
    args = parser.parse_args()
    
    # Check if color table exists
    if not os.path.exists(args.color_table) and not args.download_only:
        logger.error(f"Color table file not found: {args.color_table}")
        sys.exit(1)
    
    # Download simulation results
    downloaded = download_simulation_results(
        config_file=args.config_file,
        simulation_id=args.simulation_id,
        username=args.username
    )
    
    if args.download_only:
        logger.info("Download completed. Skipping processing as requested.")
        return
    
    # If dem_path is specified, temporarily override the find_dem_file function
    if args.dem_path and os.path.exists(args.dem_path):
        logger.info(f"Using specified DEM file: {args.dem_path}")
        # Store the specified DEM path for use in process_results
        dem_path = args.dem_path
        
        # Monkey patch the find_dem_file function to return the specified path
        original_find_dem_file = find_dem_file
        find_dem_file = lambda *args, **kwargs: Path(dem_path)
    
    # Process the downloaded results
    processing_result = process_results(
        downloaded_files=downloaded,
        color_table=args.color_table,
        force_recalculate=args.force_recalculate
    )
    
    # Restore original function if we patched it
    if args.dem_path and os.path.exists(args.dem_path):
        find_dem_file = original_find_dem_file
    
    # Print summary
    if processing_result:
        logger.info("Processing summary:")
        logger.info(f"Water depth files: {len(processing_result.get('water_depth_files', []))}")
        logger.info(f"Processed files: {len(processing_result.get('processed_files', []))}")
        logger.info(f"Tile folders: {len(processing_result.get('tile_folders', []))}")
        
        # Print sample tile URL for testing
        if processing_result.get('tile_folders'):
            sample_folder = processing_result['tile_folders'][0]
            logger.info(f"Sample tile folder: {sample_folder}")
            logger.info(f"Sample tile URL format: {sample_folder}/{{z}}/{{x}}/{{y}}.png")
    else:
        logger.warning("No processing results returned")


if __name__ == "__main__":
    main() 