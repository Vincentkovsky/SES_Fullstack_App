#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Water gauge data API (FastAPI version)

Provides API endpoints for river gauge data from CSV files.
Simplified version that works with the frontend's fetchGaugingData function.
"""

from fastapi import APIRouter, Query, HTTPException, status
from typing import Dict, Any, Optional
import logging
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from starlette.concurrency import run_in_threadpool

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api")

# Base paths
BASE_DIR = Path(__file__).parent.parent
GAUGE_DATA_DIR = BASE_DIR / "data/gauge_data"

# Ensure the gauge data directory exists
GAUGE_DATA_DIR.mkdir(exist_ok=True, parents=True)

# Default station ID and CSV file
DEFAULT_STATION_ID = "410001"
DEFAULT_CSV_FILE = GAUGE_DATA_DIR / f"{DEFAULT_STATION_ID}_river_level.csv"

# Cache for gauge data
gauge_data_cache = {}

@router.get("/gauging", response_model=Dict[str, Any])
async def get_gauging_data(
    start_date: str = Query(..., description="Start date (format: DD-MMM-YYYY HH:MM)"),
    end_date: str = Query(..., description="End date (format: DD-MMM-YYYY HH:MM)"),
    frequency: str = Query("Instantaneous", description="Data frequency")
):
    """
    Get river gauge data for a specified time period.
    
    Args:
        start_date: Start date in DD-MMM-YYYY HH:MM format (e.g., 01-Jan-2022 00:00)
        end_date: End date in DD-MMM-YYYY HH:MM format
        frequency: Data frequency (defaults to "Instantaneous")
        
    Returns:
        Dictionary containing gauge data for the specified period
    """
    try:
        logger.info(f"Fetching gauge data from {start_date} to {end_date}")
        
        # Parse dates
        try:
            start_datetime = datetime.strptime(start_date, "%d-%b-%Y %H:%M")
            end_datetime = datetime.strptime(end_date, "%d-%b-%Y %H:%M")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format. Use DD-MMM-YYYY HH:MM (e.g., 01-Jan-2022 00:00). Error: {str(e)}"
            )
        
        # Check if CSV file exists
        if not DEFAULT_CSV_FILE.exists():
                raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Gauge data file not found: {DEFAULT_CSV_FILE}"
                )
            
        # Read CSV file
        def read_gauge_data():
            # Check cache first
            cache_key = f"{DEFAULT_STATION_ID}_{start_date}_{end_date}"
            if cache_key in gauge_data_cache:
                logger.info(f"Returning cached gauge data for {DEFAULT_STATION_ID}")
                return gauge_data_cache[cache_key]
            
            # Read the CSV file
            try:
                # Read with explicit quoting and column names
                df = pd.read_csv(
                    DEFAULT_CSV_FILE,
                    quotechar='"',      # Specify double quotes as quote character
                    doublequote=True,   # Double quotes within quoted fields are doubled
                    dtype={"River Level": float}  # Ensure River Level is parsed as float
                )
        
                # Rename columns to match expected names
                df = df.rename(columns={
                    "Date": "timestamp",
                    "River Level": "water_level"
                })
                
                # Check if we have the required columns
                if "timestamp" not in df.columns:
                    # Check if we need to handle column name with quotes
                    if '"Date"' in df.columns:
                        df = df.rename(columns={'"Date"': "timestamp"})
                
                if "water_level" not in df.columns:
                    # Check if we need to handle column name with quotes
                    if '"River Level"' in df.columns:
                        df = df.rename(columns={'"River Level"': "water_level"})
                
                # Ensure timestamp column exists
                if 'timestamp' not in df.columns:
                    raise ValueError("CSV file does not have a 'Date' or 'timestamp' column")
                    
                # Ensure water_level column exists
                if 'water_level' not in df.columns:
                    raise ValueError("CSV file does not have a 'River Level' or 'water_level' column")
        
                # Handle quotes in date strings if present
                if isinstance(df['timestamp'].iloc[0], str) and df['timestamp'].iloc[0].startswith('"') and df['timestamp'].iloc[0].endswith('"'):
                    df['timestamp'] = df['timestamp'].str.strip('"')
                
                # Convert timestamps to datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Convert water_level to float if it's not already
                if df['water_level'].dtype != float:
                    # Remove quotes if present
                    if isinstance(df['water_level'].iloc[0], str):
                        df['water_level'] = df['water_level'].str.strip('"')
                    df['water_level'] = pd.to_numeric(df['water_level'], errors='coerce')
                
                # Filter by date range
                mask = (df['timestamp'] >= start_datetime) & (df['timestamp'] <= end_datetime)
                filtered_df = df.loc[mask]
                
                # Check if we have data
                if filtered_df.empty:
                    logger.warning(f"No gauge data found between {start_date} and {end_date}")
                    # Return empty dataset with the expected structure
                    return {
                        "data_count": 0,
                        "data_source": {
                            "file_path": str(DEFAULT_CSV_FILE),
                            "timestamp": datetime.now().isoformat(),
                            "type": "csv"
                        },
                        "site_info": {
                            "site_id": DEFAULT_STATION_ID,
                            "site_name": "Wagga Wagga (Murrumbidgee River)",
                            "variable": "Water Level"
                },
                        "timestamps": [],
                        "values": []
                    }
                
                # Format the result
                result = {
                    "data_count": len(filtered_df),
                    "data_source": {
                        "file_path": str(DEFAULT_CSV_FILE),
                        "timestamp": datetime.now().isoformat(),
                        "type": "csv"
                    },
                    "site_info": {
                        "site_id": DEFAULT_STATION_ID,
                        "site_name": "Wagga Wagga (Murrumbidgee River)",
                        "variable": "Water Level"
                    },
                    "timestamps": filtered_df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S').tolist(),
                    "values": filtered_df['water_level'].tolist()
                }
                
                # Cache the result
                gauge_data_cache[cache_key] = result
                
                return result
            except Exception as e:
                logger.error(f"Error reading gauge data CSV: {str(e)}")
                raise
        
        # Run file reading in a thread pool
        gauge_data = await run_in_threadpool(read_gauge_data)
        
        return gauge_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching gauge data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch gauge data: {str(e)}"
        ) 