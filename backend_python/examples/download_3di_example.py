#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Example script demonstrating how to use the 3Di downloader

This script shows how to import and use the SimulationDownloader class
to download 3Di simulation results.

Usage:
    python download_3di_example.py [options]

Examples:
    # List available simulations
    python download_3di_example.py --list-only

    # Download a specific simulation
    python download_3di_example.py --simulation-id 12345

    # Download latest finished simulation
    python download_3di_example.py

    # Download latest simulation with specific file types
    python download_3di_example.py --file-types nc,h5

    # Use a custom configuration file (instead of .env)
    python download_3di_example.py --config-file custom_config.json
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add the parent directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the utils.threedi.downloader package
from utils.threedi.downloader.download_3di_results import (
    SimulationDownloader, 
    load_config_from_file,
    find_and_load_dotenv
)


def main():
    """Main function demonstrating the use of the SimulationDownloader."""
    parser = argparse.ArgumentParser(description="3Di Downloader Example Script")
    
    # API Configuration
    parser.add_argument("--config-file", help="Path to configuration file (optional, will use .env if available)")
    parser.add_argument("--api-host", help="3Di API host URL (default: from .env or https://api.3di.live)")
    parser.add_argument("--api-token", help="3Di API personal token (default: from .env)")
    
    # Simulation filters
    parser.add_argument("--username", help="Filter simulations by username (default: current user)")
    parser.add_argument("--organisation", help="Filter simulations by organisation name")
    parser.add_argument("--tags", help="Filter simulations by tags (comma-separated)")
    parser.add_argument("--status", default="finished", help="Post-filter simulations by status (default: finished)")
    parser.add_argument("--current-user-only", action="store_true", default=True, 
                        help="Only show simulations for the current user (default: True)")
    
    # Simulation selection
    parser.add_argument("--simulation-id", type=int, help="Specific simulation ID to download")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of simulations to list (default: 10)")
    
    # Download options
    parser.add_argument("--output-dir", help="Directory to store downloaded files")
    parser.add_argument("--file-types", help="Only download files with these extensions (comma-separated, e.g., nc,h5,csv)")
    parser.add_argument("--no-gridadmin", action="store_true", help="Skip downloading gridadmin.h5 file")
    
    # Mode selection
    parser.add_argument("--list-only", action="store_true", help="Only list simulations without downloading")
    
    args = parser.parse_args()
    
    try:
        # Load .env file first (if available)
        find_and_load_dotenv()
        
        # Prepare configuration
        config = {
            "THREEDI_API_HOST": os.getenv("THREEDI_API_HOST", "https://api.3di.live"),
            "THREEDI_API_PERSONAL_API_TOKEN": os.getenv("THREEDI_API_PERSONAL_API_TOKEN"),
        }
        
        # Load configuration from file if specified
        if args.config_file:
            file_config = load_config_from_file(args.config_file)
            print(f"Loaded configuration from {args.config_file}")
            config.update(file_config)
        
        # Command line arguments override config
        if args.api_host:
            config["THREEDI_API_HOST"] = args.api_host
        if args.api_token:
            config["THREEDI_API_PERSONAL_API_TOKEN"] = args.api_token
            
        # Check if we have a token
        if not config.get("THREEDI_API_PERSONAL_API_TOKEN"):
            print("Error: No API token provided. Please set THREEDI_API_PERSONAL_API_TOKEN in .env file or use --api-token option.")
            return 1
        
        # Set up output directory
        output_dir = args.output_dir
        
        # Initialize downloader
        downloader = SimulationDownloader(config, output_dir=output_dir)
        print(f"Initialized downloader with output directory: {downloader.output_dir}")
        print(f"Connected to 3Di API at: {config.get('THREEDI_API_HOST')}")
        
        # Get current user information if needed
        current_username = None
        if args.current_user_only and not args.username:
            try:
                user_info = downloader.api_client.auth_profile_list()
                current_username = user_info.username
                print(f"Logged in as: {current_username}")
            except Exception as e:
                print(f"Warning: Could not get current user information: {str(e)}")
                print("Continuing without user filter...")

        # Use current username if available and not overridden by command line
        if current_username and not args.username:
            args.username = current_username
            print(f"Filtering for current user: {args.username}")

        # Set up tags
        tags = None
        if args.tags:
            tags = [tag.strip() for tag in args.tags.split(",")]
            
        # Set up file types
        file_types = None
        if args.file_types:
            file_types = [ft.strip() for ft in args.file_types.split(",")]
        
        # List available simulations
        if args.list_only:
            print(f"\nListing up to {args.limit} simulations...")
            
            # Apply filters
            filter_message = []
            if args.username:
                filter_message.append(f"username='{args.username}'")
            if args.organisation:
                filter_message.append(f"organisation='{args.organisation}'")
            if tags:
                filter_message.append(f"tags=[{', '.join(tags)}]")
                
            if filter_message:
                print(f"Filters: {', '.join(filter_message)}")
            if args.status:
                print(f"Post-filter: status='{args.status}' (applied after API query)")
            
            # Call the API - with robust error handling
            try:
                simulations = downloader.list_simulations(
                    username=args.username,
                    organisation_name=args.organisation,
                    tags=tags,
                    limit=args.limit
                )
                
                # Post-filter by status if needed
                if args.status and args.status.lower() != 'any':
                    status = args.status.lower()
                    filtered_sims = []
                    
                    for sim in simulations:
                        # For 'finished' status, check if 'finished' field exists
                        if status == 'finished' and sim.get('finished'):
                            filtered_sims.append(sim)
                            continue
                            
                        # Check other status fields
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
                
                # Apply additional filters that might be important
                if args.username and not args.list_only:
                    username_filtered_sims = [sim for sim in simulations if 'user' in sim and sim.get('user', {}).get('username') == args.username]
                    if username_filtered_sims:
                        print(f"Further filtered to {len(username_filtered_sims)} simulations for user '{args.username}'")
                        simulations = username_filtered_sims
                
                print("\n===== Available Simulations =====")
                if not simulations:
                    print("No simulations found matching the criteria.")
                else:
                    for i, sim in enumerate(simulations, 1):
                        print(f"{i}. ID: {sim['id']}, Name: {sim['name']}")
                        print(f"   Organisation: {sim.get('organisation') or 'N/A'}")
                        print(f"   Created: {sim.get('created') or 'N/A'}")
                        if sim.get('started'):
                            print(f"   Started: {sim.get('started')}")
                        if sim.get('finished'):
                            print(f"   Finished: {sim.get('finished')}")
                        print("")
                    
                    print(f"Total: {len(simulations)} simulations")
            
            except Exception as e:
                print(f"API Error: {str(e)}")
                import traceback
                traceback.print_exc()
                print("\nThe API query failed. Please check your credentials and connection.")
                return 1
            
            return 0
        
        # Begin download process
        print("\n===== Download Process =====")
        start_time = datetime.now()
        
        # Download simulation
        if args.simulation_id:
            print(f"Downloading simulation with ID: {args.simulation_id}")
            try:
                downloaded = downloader.download_result_files(
                    simulation_id=args.simulation_id,
                    file_types=file_types,
                    include_gridadmin=not args.no_gridadmin
                )
            except Exception as e:
                print(f"Error downloading simulation: {str(e)}")
                return 1
        else:
            print("Downloading latest simulation matching filters:")
            # Show filters
            if args.username:
                print(f"  - Username: {args.username}")
            if args.organisation:
                print(f"  - Organisation: {args.organisation}")
            if tags:
                print(f"  - Tags: {', '.join(tags)}")
            print(f"  - Status: {args.status} (applied as post-filter)")
            
            try:
                downloaded = downloader.select_and_download_latest(
                    username=args.username,
                    organisation_name=args.organisation,
                    tags=tags,
                    status=args.status,
                    file_types=file_types,
                    include_gridadmin=not args.no_gridadmin
                )
            except Exception as e:
                print(f"Error downloading latest simulation: {str(e)}")
                import traceback
                traceback.print_exc()
                return 1
        
        # Calculate elapsed time
        elapsed_time = datetime.now() - start_time
        
        # Print summary
        print("\n===== Download Summary =====")
        print(f"Result files downloaded: {len(downloaded['result_files'])}")
        
        if downloaded['result_files']:
            # Group files by type
            file_types_dict = {}
            for path in downloaded['result_files']:
                suffix = path.suffix.lower()
                if suffix not in file_types_dict:
                    file_types_dict[suffix] = []
                file_types_dict[suffix].append(path)
            
            # Display summary by file type
            for suffix, files in file_types_dict.items():
                print(f"\n{suffix} files ({len(files)}):")
                for path in files[:5]:  # Show up to 5 files per type
                    print(f"  - {path.name}")
                if len(files) > 5:
                    print(f"  - ... and {len(files) - 5} more")
        else:
            print("No result files were downloaded.")
        
        if downloaded['gridadmin']:
            print(f"\nGridadmin file: {downloaded['gridadmin'][0].name}")
        elif not args.no_gridadmin:
            print("\nGridadmin file: Not downloaded (possibly unavailable)")
        else:
            print("\nGridadmin file: Skipped per user request")
        
        print(f"\nAll files saved to: {downloader.output_dir}")
        print(f"Total time: {elapsed_time}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 