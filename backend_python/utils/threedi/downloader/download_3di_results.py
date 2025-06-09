#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
3Di Simulation Results Downloader

This script downloads simulation results and related metadata from the 3Di API.
It provides functionality to:
1. Connect to the 3Di API using authentication
2. List available simulations with filtering options
3. Download simulation results and metadata files
4. Handle errors and display progress

Dependencies:
- threedi_api_client
- tqdm (for progress tracking)
- pathlib
- argparse (for command line arguments)
- python-dotenv (for loading environment variables)
"""

import os
import sys
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

# Import dotenv for loading environment variables from .env file
try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: python-dotenv package not found. Will not load .env file.")

    def load_dotenv():
        return False

# Import 3Di API client
try:
    from threedi_api_client.api import ThreediApi
    from threedi_api_client.openapi.api.v3_api import V3Api
    from threedi_api_client.files import download_file
except ImportError:
    print("Error: Required packages not found. Please install:")
    print("pip install threedi-api-client tqdm python-dotenv")
    sys.exit(1)

# Import tqdm for progress tracking
try:
    from tqdm import tqdm
except ImportError:
    # Define a simple fallback if tqdm is not available
    def tqdm(iterable, **kwargs):
        return iterable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("3di_download.log")
    ]
)
logger = logging.getLogger(__name__)


def find_and_load_dotenv():
    """
    Find and load the .env file at different possible locations.
    First checks in current directory, then up to 3 levels up,
    and finally in the backend_python directory.
    """
    # Start with current directory
    current_path = Path.cwd()
    
    # Try up to 3 levels up
    for _ in range(4):
        env_path = current_path / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded .env from {env_path}")
            return True
        # Go one level up
        current_path = current_path.parent
    
    # Try backend_python directory specifically
    script_dir = Path(__file__).resolve().parent
    backend_path = script_dir
    # Navigate up until we find backend_python or reach root
    while backend_path.name != 'backend_python' and backend_path != backend_path.parent:
        backend_path = backend_path.parent
    
    if backend_path.name == 'backend_python':
        env_path = backend_path / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded .env from {env_path}")
            return True
    
    logger.warning("No .env file found")
    return False


class SimulationDownloader:
    """Class for downloading 3Di simulation results and metadata."""
    
    def __init__(self, config: Dict[str, str], output_dir: str = None):
        """
        Initialize the downloader with authentication details.
        
        Args:
            config: Dictionary containing API configuration 
                   (THREEDI_API_HOST and THREEDI_API_PERSONAL_API_TOKEN)
            output_dir: Base directory for downloaded files
        """
        self.config = config
        self.api_client = None
        
        # Default output directory is '../data/3di' relative to script location
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            # Get the script's directory and navigate to backend_python/data/3di
            script_dir = Path(__file__).resolve().parent
            # Find the backend_python directory from the current script location
            backend_path = script_dir
            while backend_path.name != 'backend_python' and backend_path != backend_path.parent:
                backend_path = backend_path.parent
            
            # Set output directory to backend_python/data/3di
            if backend_path.name == 'backend_python':
                self.output_dir = backend_path / "data" / "3di"
            else:
                # Fallback to script's parent directory if backend_python not found
                self.output_dir = script_dir.parent / "data" / "3di"
        
        # Connect to API
        self._connect_to_api()
        
    def _connect_to_api(self):
        """Establish connection with 3Di API."""
        try:
            logger.info(f"Connecting to 3Di API at {self.config.get('THREEDI_API_HOST', 'unknown host')}")
            self.api_client: V3Api = ThreediApi(config=self.config)
            logger.info("Connection to 3Di API established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to 3Di API: {str(e)}")
            raise
    
    def get_current_user(self) -> Optional[str]:
        """
        Get the username of the currently logged in user.
        
        Returns:
            Optional[str]: Username of the currently logged in user, or None if not available
        """
        try:
            user_info = self.api_client.auth_profile_list()
            if hasattr(user_info, 'username'):
                logger.info(f"Currently logged in as: {user_info.username}")
                return user_info.username
            return None
        except Exception as e:
            logger.warning(f"Could not retrieve current user information: {str(e)}")
            return None
    
    def list_simulations(self, 
                        username: str = None, 
                        limit: int = 10, 
                        organisation_name: str = None,
                        name: str = None,
                        tags: List[str] = None,
                        status: str = None) -> List[Dict[str, Any]]:
        """
        List available simulations with optional filters.
        
        Args:
            username: Filter by username
            limit: Maximum number of simulations to list
            organisation_name: Filter by organisation name
            name: Filter by simulation name
            tags: Filter by tags
            status: Filter by status (e.g., 'finished', 'postprocessing', etc.)
                   Note: This may not be supported by the API and will be ignored.
            
        Returns:
            List of simulation objects
        """
        try:
            # Build filter parameters
            params = {}
            if username:
                params['user__username'] = username
            if organisation_name:
                params['organisation__name'] = organisation_name
            if name:
                params['name__icontains'] = name
            if tags:
                params['tags__icontains'] = ','.join(tags)
            
            # Note: status parameter is not supported by the API, removed
            
            params['limit'] = limit
            
            # Get simulations
            logger.info(f"Retrieving simulations with filters: {params}")
            simulation_results = self.api_client.simulations_list(**params)
            
            if simulation_results.count == 0:
                logger.warning("No simulations found with the specified filters")
                return []
            
            logger.info(f"Found {simulation_results.count} simulations")
            
            # Convert to a more usable format
            simulations = []
            for sim in simulation_results.results:
                try:
                    # More robust handling of simulation data
                    sim_dict = {
                        "id": getattr(sim, 'id', None),
                        "name": getattr(sim, 'name', 'Unknown Simulation'),
                        "threedimodel_id": getattr(sim, 'threedimodel_id', None),
                    }
                    
                    # Handle user information if available
                    if hasattr(sim, 'user'):
                        user = getattr(sim, 'user')
                        if user:
                            if isinstance(user, dict):
                                sim_dict["user"] = user
                            elif hasattr(user, 'username'):
                                sim_dict["user"] = {"username": user.username}
                            elif isinstance(user, str):
                                sim_dict["user"] = {"username": user}
                    
                    # Handle organisation which might be an object or string or missing
                    if hasattr(sim, 'organisation'):
                        org = getattr(sim, 'organisation')
                        if isinstance(org, dict):
                            sim_dict["organisation"] = org.get('name')
                        elif hasattr(org, 'name'):
                            sim_dict["organisation"] = org.name
                        elif isinstance(org, str):
                            sim_dict["organisation"] = org
                        else:
                            sim_dict["organisation"] = None
                    else:
                        sim_dict["organisation"] = None
                        
                    # Handle datetime conversions properly
                    for dt_field in ['created', 'started', 'finished']:
                        if hasattr(sim, dt_field):
                            dt_value = getattr(sim, dt_field)
                            if dt_value:
                                if hasattr(dt_value, 'isoformat'):
                                    sim_dict[dt_field] = dt_value.isoformat()
                                else:
                                    sim_dict[dt_field] = str(dt_value)
                            else:
                                sim_dict[dt_field] = None
                        else:
                            sim_dict[dt_field] = None
                            
                    simulations.append(sim_dict)
                except Exception as e:
                    logger.warning(f"Error parsing simulation data: {str(e)}")
                    # Create minimal dict with available data to avoid losing this entry
                    try:
                        min_dict = {
                            "id": getattr(sim, 'id', 'Unknown ID'),
                            "name": getattr(sim, 'name', 'Unknown Simulation'),
                            "error": f"Error parsing full data: {str(e)}"
                        }
                        simulations.append(min_dict)
                    except:
                        pass  # Skip this entry if we can't even get minimal data
                
            return simulations
            
        except Exception as e:
            logger.error(f"Error listing simulations: {str(e)}")
            raise
    
    def get_simulation_status(self, simulation_id: int) -> Dict[str, Any]:
        """
        Get the status of a simulation.
        
        Args:
            simulation_id: ID of the simulation
            
        Returns:
            Dictionary with status information
        """
        try:
            status = self.api_client.simulations_status_list(simulation_id)
            return {"name": status.name, "time": status.time}
        except Exception as e:
            logger.error(f"Error getting simulation status for ID {simulation_id}: {str(e)}")
            raise
    
    def list_result_files(self, simulation_id: int) -> List[Dict[str, Any]]:
        """
        List available result files for a simulation.
        
        Args:
            simulation_id: ID of the simulation
            
        Returns:
            List of result file objects
        """
        try:
            result_files = self.api_client.simulations_results_files_list(simulation_id)
            
            files = []
            for file in result_files.results:
                file_dict = {
                    "id": file.id,
                    "filename": file.filename,
                    "created": file.created.isoformat() if hasattr(file, 'created') else None,
                    "size": getattr(file, 'size', 'unknown size')
                }
                files.append(file_dict)
                
            return files
        except Exception as e:
            logger.error(f"Error listing result files for simulation ID {simulation_id}: {str(e)}")
            raise
    
    def download_result_files(self, 
                             simulation_id: int, 
                             simulation_name: str = None,
                             file_types: List[str] = None,
                             include_gridadmin: bool = True) -> Dict[str, List[Path]]:
        """
        Download result files for a simulation.
        
        Args:
            simulation_id: ID of the simulation
            simulation_name: Name to use for the output folder (uses sim ID if None)
            file_types: List of file extensions to download (e.g., ['.nc', '.csv'])
                        If None, download all files
            include_gridadmin: Whether to also download the gridadmin.h5 file
            
        Returns:
            Dictionary with paths to downloaded files
        """
        try:
            # Get simulation details to determine creation date
            simulation = self.api_client.simulations_read(simulation_id)
            
            # Handle different date formats (string, datetime, or missing)
            created_date = datetime.now().strftime("%Y%m%d")  # Default fallback
            
            if hasattr(simulation, 'created'):
                created = getattr(simulation, 'created')
                if created:
                    if hasattr(created, 'strftime'):
                        # It's a datetime object
                        created_date = created.strftime("%Y%m%d")
                    elif isinstance(created, str):
                        # Parse string date
                        try:
                            # Try ISO format
                            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            created_date = dt.strftime("%Y%m%d")
                        except:
                            try:
                                # Try timestamp format
                                import dateutil.parser
                                dt = dateutil.parser.parse(created)
                                created_date = dt.strftime("%Y%m%d")
                            except:
                                # Keep default
                                logger.warning(f"Could not parse created date: {created}, using current date")
            
            # Create sim_YYYYMMDD folder name format
            folder_name = f"sim_{created_date}"
            if simulation_name:
                # Add simulation name as a subfolder if provided
                # Sanitize simulation_name for filesystem
                safe_name = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in str(simulation_name))
                folder_name = f"{folder_name}_{safe_name}"
                
            # Set up main simulation folder and subfolders
            download_folder = self.output_dir / folder_name
            download_folder.mkdir(parents=True, exist_ok=True)
            
            # Create subfolders for different file types
            netcdf_folder = download_folder / "netcdf"
            netcdf_folder.mkdir(exist_ok=True)
            
            geotiff_folder = download_folder / "geotiff"
            geotiff_folder.mkdir(exist_ok=True)
            
            other_folder = download_folder / "other"
            other_folder.mkdir(exist_ok=True)
            
            # Get list of result files
            logger.info(f"Getting list of result files for simulation ID {simulation_id}")
            result_files = self.api_client.simulations_results_files_list(simulation_id)
            
            # Filter files by type if specified
            files_to_download = result_files.results
            if file_types:
                file_types = [t.lower() if t.startswith('.') else '.' + t.lower() for t in file_types]
                files_to_download = [
                    f for f in files_to_download 
                    if Path(f.filename).suffix.lower() in file_types
                ]
                logger.info(f"Filtered to {len(files_to_download)} files with extensions: {file_types}")
            
            # Download files with progress bar
            downloaded_files = []
            total_size = sum(getattr(f, 'size', 0) for f in files_to_download)
            logger.info(f"Downloading {len(files_to_download)} files (approx. {total_size/1024/1024:.2f} MB)")
            
            for file in tqdm(files_to_download, desc="Downloading result files"):
                try:
                    download = self.api_client.simulations_results_files_download(
                        id=file.id, simulation_pk=simulation_id
                    )
                    
                    # Determine appropriate subfolder based on file extension
                    file_path = Path(file.filename)
                    suffix = file_path.suffix.lower()
                    
                    if suffix == '.nc':
                        target_folder = netcdf_folder
                    elif suffix in ['.tif', '.tiff', '.geotiff']:
                        target_folder = geotiff_folder
                    else:
                        target_folder = other_folder
                    
                    file_path = target_folder / file_path.name
                    download_file(download.get_url, file_path)
                    downloaded_files.append(file_path)
                    logger.info(f"Downloaded {file.filename}")
                except Exception as e:
                    logger.error(f"Error downloading {file.filename}: {str(e)}")
            
            # Download gridadmin.h5 if requested
            gridadmin_path = None
            if include_gridadmin:
                try:
                    logger.info("Retrieving threedimodel_id for gridadmin.h5")
                    threedi_model_id = getattr(simulation, 'threedimodel_id', None)
                    
                    if threedi_model_id:
                        logger.info(f"Downloading gridadmin.h5 for model ID {threedi_model_id}")
                        download_url = self.api_client.threedimodels_gridadmin_download(threedi_model_id)
                        
                        file_path = netcdf_folder / "gridadmin.h5"
                        download_file(download_url.get_url, file_path)
                        gridadmin_path = file_path
                        logger.info("Downloaded gridadmin.h5")
                    else:
                        logger.warning("Could not find threedimodel_id, skipping gridadmin.h5")
                except Exception as e:
                    logger.error(f"Error downloading gridadmin.h5: {str(e)}")
            
            # Create a metadata file with information about the download
            metadata = {
                "simulation_id": simulation_id,
                "simulation_name": simulation_name,
                "download_time": datetime.now().isoformat(),
                "files_downloaded": [str(f.relative_to(download_folder)) for f in downloaded_files],
                "gridadmin_downloaded": bool(gridadmin_path)
            }
            
            metadata_path = download_folder / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                "result_files": downloaded_files,
                "gridadmin": [gridadmin_path] if gridadmin_path else []
            }
            
        except Exception as e:
            logger.error(f"Error downloading result files for simulation ID {simulation_id}: {str(e)}")
            raise

    def select_and_download_latest(self, 
                                   username: str = None, 
                                   organisation_name: str = None,
                                   tags: List[str] = None,
                                   status: str = "finished",
                                   include_gridadmin: bool = True,
                                   file_types: List[str] = None) -> Dict[str, List[Path]]:
        """
        Select the latest simulation based on filters and download its results.
        
        Args:
            username: Filter by username
            organisation_name: Filter by organisation name
            tags: Filter by tags
            status: Filter by status (default: 'finished'), applied as post-filter
            include_gridadmin: Whether to download gridadmin.h5
            file_types: List of file extensions to download
            
        Returns:
            Dictionary with paths to downloaded files
        """
        try:
            # 如果没有指定用户名，尝试获取当前登录用户
            if not username:
                current_username = self.get_current_user()
                if current_username:
                    username = current_username
                    logger.info(f"Using current user for filtering: {username}")
                    
            # Get a larger list of simulations to post-filter by status
            # The API doesn't support filtering by status directly
            simulations = self.list_simulations(
                username=username,
                organisation_name=organisation_name,
                tags=tags,
                limit=50  # Get more to allow for filtering
            )
            
            if not simulations:
                logger.warning("No simulations found matching the criteria")
                return {"result_files": [], "gridadmin": []}
            
            # Post-filter by status if requested
            if status and status.lower() != 'any':
                # Try different attribute names that might contain status info
                status_fields = ['status', 'state', 'finished']
                status_simulations = []
                
                for sim in simulations:
                    # For 'finished' status, check if 'finished' attribute exists and is not None
                    if status.lower() == 'finished' and sim.get('finished'):
                        status_simulations.append(sim)
                        continue
                        
                    # Check if any status field matches
                    for field in status_fields:
                        sim_status = sim.get(field)
                        if sim_status and str(sim_status).lower() == status.lower():
                            status_simulations.append(sim)
                            break
                
                if status_simulations:
                    logger.info(f"Filtered {len(status_simulations)} simulations with status '{status}'")
                    simulations = status_simulations
                else:
                    logger.warning(f"No simulations found with status '{status}', using all simulations")
            
            if not simulations:
                logger.warning("No simulations found after filtering")
                return {"result_files": [], "gridadmin": []}
            
            # Sort by created date (if available) to get the most recent
            simulations.sort(key=lambda s: s.get('created', ''), reverse=True)
            
            simulation = simulations[0]
            simulation_id = simulation["id"]
            simulation_name = simulation["name"]
            
            logger.info(f"Selected simulation: {simulation_name} (ID: {simulation_id})")
            
            # Download the files
            return self.download_result_files(
                simulation_id=simulation_id,
                simulation_name=simulation_name,
                file_types=file_types,
                include_gridadmin=include_gridadmin
            )
        
        except Exception as e:
            logger.error(f"Error in select_and_download_latest: {str(e)}")
            raise


def load_config_from_file(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_path: Path to the JSON configuration file
    
    Returns:
        Dictionary with configuration values
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration from {config_path}: {str(e)}")
        raise


def main():
    """Main function to handle command line arguments and execute the downloader."""
    parser = argparse.ArgumentParser(description="Download 3Di simulation results and metadata")
    
    # API Configuration
    parser.add_argument("--api-host", default=None,
                       help="3Di API host URL (default: from .env or https://api.3di.live)")
    parser.add_argument("--api-token", 
                       help="3Di API personal token (if not provided, will try to load from .env or environment)")
    parser.add_argument("--config-file",
                       help="Path to JSON configuration file containing API credentials and defaults")
    
    # Simulation selection
    parser.add_argument("--username", help="Filter simulations by username")
    parser.add_argument("--organisation", help="Filter simulations by organisation name")
    parser.add_argument("--tags", help="Filter simulations by tags (comma-separated)")
    parser.add_argument("--status", default="finished", 
                       help="Filter simulations by status (default: finished)")
    parser.add_argument("--simulation-id", type=int,
                       help="Download results for a specific simulation ID")
    parser.add_argument("--current-user-only", action="store_true", default=True,
                       help="Only show/download simulations for the current logged in user (default: True)")
    parser.add_argument("--all-users", action="store_true", default=False,
                       help="Show/download simulations for all users (overrides --current-user-only)")
    
    # Download options
    parser.add_argument("--output-dir", 
                       help="Directory to store downloaded files (default: ../data/3di)")
    parser.add_argument("--file-types", 
                       help="Only download files with these extensions (comma-separated, e.g., nc,h5,csv)")
    parser.add_argument("--no-gridadmin", action="store_true",
                       help="Skip downloading gridadmin.h5 file")
    
    # List only mode
    parser.add_argument("--list-only", action="store_true",
                       help="Only list simulations without downloading files")
    parser.add_argument("--limit", type=int, default=10,
                       help="Maximum number of simulations to list (default: 10)")
    
    args = parser.parse_args()
    
    # 处理互斥的用户过滤选项
    if args.all_users:
        args.current_user_only = False
    
    # Try to load .env file
    find_and_load_dotenv()
    
    # Default configuration
    config = {
        "THREEDI_API_HOST": os.getenv("THREEDI_API_HOST", "https://api.3di.live"),
        "THREEDI_API_PERSONAL_API_TOKEN": os.getenv("THREEDI_API_PERSONAL_API_TOKEN"),
        "DEFAULT_OUTPUT_DIR": None  # Will use the default in the SimulationDownloader class
    }
    
    # Load configuration from file if specified
    file_config = {}
    if args.config_file:
        try:
            file_config = load_config_from_file(args.config_file)
            # Update config with values from file
            config.update({k: v for k, v in file_config.items() if k not in ['DEFAULT_OPTIONS']})
        except Exception as e:
            print(f"Warning: Couldn't load configuration file: {str(e)}")
    
    # Command line arguments override config file and .env
    if args.api_host:
        config["THREEDI_API_HOST"] = args.api_host
    
    if args.api_token:
        config["THREEDI_API_PERSONAL_API_TOKEN"] = args.api_token
    
    # Try to get API token from environment if not in config, .env or args
    if not config["THREEDI_API_PERSONAL_API_TOKEN"]:
        config["THREEDI_API_PERSONAL_API_TOKEN"] = os.environ.get("THREEDI_API_PERSONAL_API_TOKEN")
        
    # Check if we have an API token
    if not config["THREEDI_API_PERSONAL_API_TOKEN"]:
        parser.error("No API token provided. Use --api-token, set THREEDI_API_PERSONAL_API_TOKEN in .env file, or set environment variable.")
    
    # Set output directory
    output_dir = args.output_dir or file_config.get("DEFAULT_OUTPUT_DIR")
    
    # Set up file types
    file_types = None
    if args.file_types:
        file_types = [ft.strip() for ft in args.file_types.split(",")]
    elif "DEFAULT_OPTIONS" in file_config and "file_types" in file_config["DEFAULT_OPTIONS"]:
        file_types = file_config["DEFAULT_OPTIONS"]["file_types"]
    
    # Set up tags
    tags = None
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(",")]
    
    try:
        # Initialize downloader
        downloader = SimulationDownloader(config, output_dir=output_dir)
        
        # 如果启用了当前用户过滤且没有明确指定用户名，则获取当前登录用户
        if args.current_user_only and not args.username:
            current_username = downloader.get_current_user()
            if current_username:
                args.username = current_username
                print(f"Filtering for current user: {args.username}")
                
        # List simulations mode
        if args.list_only:
            simulations = downloader.list_simulations(
                username=args.username,
                organisation_name=args.organisation,
                tags=tags,
                status=args.status,
                limit=args.limit
            )
            
            # 如果指定了状态过滤条件，执行后处理过滤
            if args.status and args.status.lower() != 'any':
                status = args.status.lower()
                filtered_sims = []
                
                for sim in simulations:
                    # 对于'finished'状态，检查'finished'字段是否存在且不为空
                    if status == 'finished' and sim.get('finished'):
                        filtered_sims.append(sim)
                        continue
                        
                    # 检查其他可能包含状态信息的字段
                    for field in ['status', 'state', 'finished']:
                        sim_status = sim.get(field)
                        if sim_status and str(sim_status).lower() == status:
                            filtered_sims.append(sim)
                            break
                
                if filtered_sims:
                    print(f"Filtered from {len(simulations)} to {len(filtered_sims)} simulations with status '{args.status}'")
                    simulations = filtered_sims
                else:
                    print(f"No simulations found with status '{args.status}', showing all")
            
            print("\n===== Available Simulations =====")
            if not simulations:
                print("No simulations found matching the criteria.")
            else:
                for i, sim in enumerate(simulations, 1):
                    print(f"{i}. ID: {sim['id']}, Name: {sim['name']}")
                    # 显示用户名（如果可用）
                    if 'user' in sim and 'username' in sim['user']:
                        print(f"   User: {sim['user']['username']}")
                    print(f"   Created: {sim['created']}")
                    print(f"   Organisation: {sim['organisation']}")
                    if sim.get('finished'):
                        print(f"   Finished: {sim['finished']}")
                    print("")
                
                print(f"Total: {len(simulations)} simulations")
            
            return
        
        # Determine whether to include gridadmin
        include_gridadmin = not args.no_gridadmin
        if args.no_gridadmin is False and "DEFAULT_OPTIONS" in file_config:
            include_gridadmin = file_config["DEFAULT_OPTIONS"].get("include_gridadmin", True)
        
        # Download specific simulation
        if args.simulation_id:
            # 如果指定了模拟ID，先获取模拟信息，检查状态和用户是否符合条件
            try:
                # 获取模拟详情
                simulation = downloader.api_client.simulations_read(args.simulation_id)
                simulation_status = downloader.api_client.simulations_status_list(args.simulation_id)
                
                # 检查状态是否符合条件（如果指定了状态过滤）
                status_match = True
                if args.status and args.status.lower() != 'any':
                    status_match = False
                    # 对于'finished'状态，检查是否完成
                    if args.status.lower() == 'finished' and hasattr(simulation, 'finished') and simulation.finished:
                        status_match = True
                    # 检查状态名称
                    elif hasattr(simulation_status, 'name') and simulation_status.name.lower() == args.status.lower():
                        status_match = True
                
                # 检查用户是否符合条件（如果开启了当前用户过滤）
                user_match = True
                if args.current_user_only and args.username:
                    user_match = False
                    if hasattr(simulation, 'user') and hasattr(simulation.user, 'username'):
                        if simulation.user.username == args.username:
                            user_match = True
                
                # 如果状态和用户条件都满足，则下载
                if status_match and user_match:
                    print(f"Downloading simulation with ID: {args.simulation_id}")
                    downloaded = downloader.download_result_files(
                        simulation_id=args.simulation_id,
                        include_gridadmin=include_gridadmin,
                        file_types=file_types
                    )
                else:
                    if not status_match:
                        print(f"Simulation with ID {args.simulation_id} does not have status '{args.status}'. Download skipped.")
                    if not user_match:
                        print(f"Simulation with ID {args.simulation_id} does not belong to user '{args.username}'. Download skipped.")
                    return 1
                    
            except Exception as e:
                print(f"Error accessing simulation: {str(e)}")
                return 1
        else:
            # Download latest simulation based on filters
            downloaded = downloader.select_and_download_latest(
                username=args.username,
                organisation_name=args.organisation,
                tags=tags,
                status=args.status,
                include_gridadmin=include_gridadmin,
                file_types=file_types
            )
        
        # Print summary
        print("\n===== Download Summary =====")
        print(f"Result files downloaded: {len(downloaded['result_files'])}")
        for path in downloaded['result_files']:
            print(f"- {path}")
        
        if downloaded['gridadmin']:
            print(f"\nGridadmin file: {downloaded['gridadmin'][0]}")
        elif include_gridadmin:
            print("\nGridadmin file: Failed to download")
        
        print(f"\nAll files saved to: {downloader.output_dir}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 