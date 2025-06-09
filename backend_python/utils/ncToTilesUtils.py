#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NetCDF to Tiles Utility Functions

This module provides functionality to process NetCDF files containing 3Di model results,
extract water depth information, and generate map tiles for visualization.

Main functionalities:
1. Convert NetCDF water levels to GeoTIFF water depth files
2. Process GeoTIFF files by replacing NoData values
3. Generate map tiles from GeoTIFF files with color mapping

Dependencies:
- threedidepth
- netCDF4
- rasterio
- numpy
- os
- datetime
- subprocess (via tileGeneratorUtils)
- tqdm (for progress tracking)
"""

import os
import threedidepth
from netCDF4 import Dataset
from datetime import datetime, timedelta
import rasterio
import numpy as np
from pathlib import Path
import logging
import matplotlib.pyplot as plt
from rasterio.plot import show
from typing import List, Dict, Optional, Union, Tuple, Any
from tqdm import tqdm

# Import tile generator utilities
from .tileGeneratorUtils import TileGeneratorUtils, TileGeneratorConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("nc_to_tiles.log")
    ]
)
logger = logging.getLogger(__name__)


def extract_timestamps_from_nc(nc_file_path: str) -> List[datetime]:
    """
    Extract timestamps from a NetCDF file.
    
    Args:
        nc_file_path: Path to the NetCDF file
        
    Returns:
        List of datetime objects representing the timestamps in the file
    """
    try:
        with Dataset(nc_file_path, mode="r") as nc:
            # Assuming time is stored in variable "time", with units as "seconds since <base_date>"
            time_var = nc.variables["time"]
            time_units = time_var.units
            time_values = time_var[:]
            
            # Parse time units (e.g., "seconds since 1970-01-01 00:00:00")
            base_time_str = time_units.split("since")[1].strip()
            base_time = datetime.strptime(base_time_str, "%Y-%m-%d %H:%M:%S")
            
            # Calculate absolute timestamps
            timestamps = [base_time + timedelta(seconds=float(t)) for t in time_values]
            
            logger.info(f"Extracted {len(timestamps)} timestamps from {nc_file_path}")
            return timestamps
    except Exception as e:
        logger.error(f"Error extracting timestamps from NetCDF file: {str(e)}")
        raise


def calculate_water_depths(
    gridadmin_path: str, 
    results_path: str, 
    dem_path: str, 
    output_folder: str,
    force_recalculate: bool = False
) -> List[str]:
    """
    Calculate water depths from 3Di model results.
    
    Args:
        gridadmin_path: Path to the gridadmin.h5 file
        results_path: Path to the results_3di.nc file
        dem_path: Path to the DEM .tif file
        output_folder: Path to the folder where water depth files will be saved
        force_recalculate: If True, recalculate even if files already exist
        
    Returns:
        List of paths to the generated water depth files
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        
        # Extract timestamps from NetCDF file
        timestamps = extract_timestamps_from_nc(results_path)
        calculation_steps_count = len(timestamps)
        
        output_files = []
        skipped_count = 0
        
        # Create a progress bar
        logger.info(f"Starting water depth calculation for {calculation_steps_count} timestamps...")
        
        # Loop through and generate files with progress bar
        for i in tqdm(range(calculation_steps_count), desc="Calculating water depths", unit="step"):
            # Current timestamp
            current_time = timestamps[i]
            time_str = current_time.strftime("%Y%m%d_%H%M%S")  # Format as YYYYMMDD_HHMMSS
            
            # Output file path
            output_path = os.path.join(output_folder, f"waterdepth_{time_str}.tif")
            output_files.append(output_path)
            
            # Check if file already exists
            if os.path.exists(output_path) and not force_recalculate:
                logger.debug(f"File already exists, skipping: {output_path}")
                skipped_count += 1
                continue
            
            # Current calculation step
            calculation_step = [i]
            
            # Execute water depth calculation
            logger.debug(f"Calculating water depth for step {i}/{calculation_steps_count-1} ({time_str})...")
            threedidepth.calculate_waterdepth(
                gridadmin_path=gridadmin_path,
                results_3di_path=results_path,
                dem_path=dem_path,
                waterdepth_path=output_path,
                calculation_steps=calculation_step
            )
            
            logger.debug(f"Calculation step {i} completed: {output_path}")
        
        logger.info(f"Water depth calculation completed. Generated: {calculation_steps_count - skipped_count} files, Skipped: {skipped_count} files")
        return output_files
    except Exception as e:
        logger.error(f"Error calculating water depths: {str(e)}")
        raise


def process_water_depth_files(folder_path: str) -> List[str]:
    """
    Process water depth GeoTIFF files to replace NoData values with 0.
    
    Args:
        folder_path: Path to the folder containing water depth .tif files
        
    Returns:
        List of processed file paths
    """
    try:
        processed_files = []
        processed_count = 0
        skipped_count = 0
        
        # Get all .tif files in the folder
        tif_files = [f for f in os.listdir(folder_path) if f.endswith(".tif")]
        
        # Process files with progress bar
        logger.info(f"Starting to process {len(tif_files)} water depth files...")
        for file_name in tqdm(tif_files, desc="Processing water depth files", unit="file"):
            file_path = os.path.join(folder_path, file_name)
            processed_files.append(file_path)
            
            # Open the GeoTIFF file in read/write mode
            with rasterio.open(file_path, "r+") as src:
                # Read the first band
                data = src.read(1)
                
                # Replace -9999 (NoData) with 0
                if -9999 in data:
                    data[data == -9999] = 0
                    
                    # Update the file
                    src.write(data, 1)
                    
                    # Update NoData value to 0 (optional)
                    src.nodata = 0
                    
                    logger.debug(f"Processed file: {file_path}")
                    processed_count += 1
                else:
                    logger.debug(f"No -9999 values found in {file_path}, skipping")
                    skipped_count += 1
        
        logger.info(f"Water depth file processing completed. Processed: {processed_count} files, No changes needed: {skipped_count} files")
        return processed_files
    except Exception as e:
        logger.error(f"Error processing water depth files: {str(e)}")
        raise


def generate_tiles_for_files(
    input_folder: str, 
    color_table: str, 
    output_root_folder: str,
    zoom_levels: str = "0-14",
    processes: int = 8
) -> List[str]:
    """
    Generate map tiles for all water depth GeoTIFF files.
    
    Args:
        input_folder: Path to the folder containing water depth .tif files
        color_table: Path to the color table file
        output_root_folder: Path to the root folder where tiles will be saved
        zoom_levels: Zoom levels for tile generation (e.g., "0-14")
        processes: Number of parallel processes for tile generation
        
    Returns:
        List of output folder paths containing the generated tiles
    """
    try:
        # Initialize tile generator with custom configuration
        config = TileGeneratorConfig(
            zoom_levels=zoom_levels,
            processes=processes,
            projection="mercator",
            xyz_format=True
        )
        tile_generator = TileGeneratorUtils(config)
        
        output_folders = []
        success_count = 0
        failed_count = 0
        
        # Get all .tif files in the folder
        tif_files = [f for f in os.listdir(input_folder) if f.endswith(".tif")]
        
        # Generate tiles with progress bar
        logger.info(f"Starting tile generation for {len(tif_files)} GeoTIFF files...")
        for file_name in tqdm(tif_files, desc="Generating map tiles", unit="file"):
            # Full input file path
            input_file = os.path.join(input_folder, file_name)
            
            # Extract time point from file name (remove file extension)
            time_point = os.path.splitext(file_name)[0]
            output_folder = os.path.join(output_root_folder, time_point)
            output_folders.append(output_folder)
            
            # Create output directory (if it doesn't exist)
            os.makedirs(output_folder, exist_ok=True)
            
            # Call generate_tiles function
            logger.debug(f"Processing file: {input_file}")
            success = tile_generator.generate_tiles(input_file, color_table, output_folder)
            
            if success:
                logger.debug(f"Tiles generated successfully in {output_folder}")
                success_count += 1
            else:
                logger.error(f"Failed to generate tiles for {input_file}")
                failed_count += 1
        
        logger.info(f"Tile generation completed. Successful: {success_count} files, Failed: {failed_count} files")
        return output_folders
    except Exception as e:
        logger.error(f"Error generating tiles: {str(e)}")
        raise


def read_tif(file_path: str) -> None:
    """
    Display a GeoTIFF file using matplotlib.
    
    Args:
        file_path: Path to the GeoTIFF file
    """
    try:
        with rasterio.open(file_path) as dataset:
            fig, ax = plt.subplots(figsize=(10, 10))
            show(dataset, ax=ax)
            plt.show()
    except Exception as e:
        logger.error(f"Error reading TIFF file: {str(e)}")


def read_tif_attributes(file_path: str) -> Dict[str, Any]:
    """
    Read attributes of a GeoTIFF file.
    
    Args:
        file_path: Path to the GeoTIFF file
        
    Returns:
        Dictionary containing file attributes
    """
    try:
        with rasterio.open(file_path) as dataset:
            attributes = {
                "width": dataset.width,
                "height": dataset.height,
                "count": dataset.count,
                "crs": dataset.crs.to_string(),
                "transform": dataset.transform,
                "bounds": dataset.bounds,
                "driver": dataset.driver,
                "dtype": dataset.dtypes[0]
            }
            return attributes
    except Exception as e:
        logger.error(f"Error reading TIFF file attributes: {str(e)}")
        return {}


def read_tif_data(file_path: str) -> Dict[str, Any]:
    """
    Read data and attributes of a GeoTIFF file.
    
    Args:
        file_path: Path to the GeoTIFF file
        
    Returns:
        Dictionary containing file data and attributes
    """
    try:
        with rasterio.open(file_path) as dataset:
            data = dataset.read()
            return {
                "data": data,
                "width": dataset.width,
                "height": dataset.height,
                "count": dataset.count,
                "crs": dataset.crs.to_string(),
                "transform": dataset.transform,
                "bounds": dataset.bounds,
                "driver": dataset.driver,
                "dtype": dataset.dtypes[0]
            }
    except Exception as e:
        logger.error(f"Error reading TIFF file data: {str(e)}")
        return {}


def process_nc_to_tiles(
    gridadmin_path: str,
    results_path: str,
    dem_path: str,
    color_table: str,
    waterdepth_folder: str = None,
    tiles_root_folder: str = None,
    force_recalculate: bool = False,
    zoom_levels: str = "0-14",
    processes: int = 8
) -> Dict[str, List[str]]:
    """
    Process NetCDF files to generate water depth GeoTIFFs and map tiles.
    Main function that combines all the steps in the workflow.
    
    Args:
        gridadmin_path: Path to the gridadmin.h5 file
        results_path: Path to the results_3di.nc file
        dem_path: Path to the DEM .tif file
        color_table: Path to the color table file
        waterdepth_folder: Path to store water depth files (default: next to results file)
        tiles_root_folder: Path to store tiles (default: next to water depth folder)
        force_recalculate: Force recalculation of existing files
        zoom_levels: Zoom levels for tile generation
        processes: Number of parallel processes for tile generation
        
    Returns:
        Dictionary with paths to generated water depth files and tile folders
    """
    try:
        # Set default folders if not provided
        if waterdepth_folder is None:
            results_dir = os.path.dirname(results_path)
            waterdepth_folder = os.path.join(results_dir, "waterdepth_folder")
            
        if tiles_root_folder is None:
            waterdepth_dir = os.path.dirname(waterdepth_folder)
            tiles_root_folder = os.path.join(waterdepth_dir, "timeseries_tiles")
        
        # Display overall progress
        print("\n======= NetCDF to Tiles Conversion Process =======")
        print(f"Input NetCDF: {results_path}")
        print(f"Output Water Depth Folder: {waterdepth_folder}")
        print(f"Output Tiles Folder: {tiles_root_folder}")
        print("=================================================\n")
        
        # Step 1: Calculate water depths
        print("Step 1/3: Calculating water depths from NetCDF file...")
        water_depth_files = calculate_water_depths(
            gridadmin_path, 
            results_path, 
            dem_path, 
            waterdepth_folder,
            force_recalculate
        )
        
        # Step 2: Process water depth files
        print("\nStep 2/3: Processing water depth files...")
        processed_files = process_water_depth_files(waterdepth_folder)
        
        # Step 3: Generate tiles
        print("\nStep 3/3: Generating tiles for water depth files...")
        tile_folders = generate_tiles_for_files(
            waterdepth_folder, 
            color_table, 
            tiles_root_folder,
            zoom_levels,
            processes
        )
        
        # Display completion message
        print("\n======= Conversion Process Completed =======")
        print(f"Total Water Depth Files: {len(water_depth_files)}")
        print(f"Total Processed Files: {len(processed_files)}")
        print(f"Total Tile Folders: {len(tile_folders)}")
        print("===========================================\n")
        
        return {
            "water_depth_files": water_depth_files,
            "processed_files": processed_files,
            "tile_folders": tile_folders
        }
    except Exception as e:
        logger.error(f"Error in NC to tiles processing: {str(e)}")
        raise


if __name__ == "__main__":
    # Example usage when run as script
    print("This module provides utilities for converting NetCDF files to map tiles.")
    print("Import and use the functions in your own scripts.") 