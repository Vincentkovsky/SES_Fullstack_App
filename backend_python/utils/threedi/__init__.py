"""
3Di Utilities Package

This package contains various modules for working with 3Di flood models.
"""

# Import commonly used modules for easier access
try:
    from .downloader import SimulationDownloader, load_config_from_file
except ImportError:
    pass 