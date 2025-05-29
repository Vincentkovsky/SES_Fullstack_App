"""
3Di Downloader Module

This module provides functionality for downloading and processing 3Di simulation results.
"""

from .download_3di_results import (
    SimulationDownloader,
    load_config_from_file
)

__all__ = [
    'SimulationDownloader',
    'load_config_from_file'
] 