"""
API模块 (FastAPI版本)

包含各种API路由器。
"""

from .health_router import router as health_router
from .water_depth_router import router as water_depth_router
from .inference_router import router as inference_router
from .raster_router import router as raster_router

# Change import order to avoid circular dependency
from .gauging_router import router as gauging_router
from .cache_router import router as cache_router
from .raster_router import router as raster_router

__all__ = [
    'health_router',
    'water_depth_router',
    'inference_router',
    'gauging_router',
    'cache_router',
    'raster_router'
] 