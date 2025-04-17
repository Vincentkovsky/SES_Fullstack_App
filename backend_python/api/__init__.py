"""
API模块

包含各种API蓝图。
"""

from .water_depth_api import water_depth_bp
from .tile_api import tile_bp
from .inference_api import inference_bp
from .gauging_api import gauging_bp
from .cache_api import cache_bp
from .health_api import health_bp
from .raster_api import raster_bp

__all__ = [
    'water_depth_bp',
    'tile_bp',
    'inference_bp',
    'gauging_bp',
    'cache_bp',
    'health_bp',
    'raster_bp'
] 