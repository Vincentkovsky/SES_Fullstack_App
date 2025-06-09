import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .config import Config

# 创建简单的内存缓存
_cache = {}
_cache_expiry = {}  # 用于存储缓存过期时间

def get_cache_key(params: Dict[str, Any]) -> str:
    """生成基于请求参数的缓存键"""
    param_str = json.dumps(sorted(params.items()), sort_keys=True)
    return hashlib.md5(param_str.encode()).hexdigest()

def get_cache(key: str) -> Optional[Any]:
    """从缓存获取数据"""
    # 检查缓存是否过期
    if key in _cache and datetime.now() < _cache_expiry.get(key, datetime.min):
        return _cache[key]
    
    # 缓存已过期或不存在
    if key in _cache:
        del _cache[key]
    if key in _cache_expiry:
        del _cache_expiry[key]
    
    return None

def set_cache(key: str, data: Any, expiry_seconds: Optional[int] = None) -> None:
    """设置缓存数据"""
    _cache[key] = data
    expiry = datetime.now() + timedelta(seconds=expiry_seconds or Config.CACHE_EXPIRY_SECONDS)
    _cache_expiry[key] = expiry

def clear_cache() -> int:
    """清除所有缓存"""
    global _cache, _cache_expiry
    cache_size = len(_cache)
    _cache = {}
    _cache_expiry = {}
    return cache_size

def prune_expired_cache() -> int:
    """清除过期缓存"""
    now = datetime.now()
    
    # 收集过期的键
    expired_keys = [key for key, expiry in _cache_expiry.items() if now >= expiry]
    
    # 删除过期的缓存项
    for key in expired_keys:
        if key in _cache:
            del _cache[key]
        if key in _cache_expiry:
            del _cache_expiry[key]
    
    return len(expired_keys)

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    now = datetime.now()
    stats = {
        "total_entries": len(_cache),
        "memory_usage_estimate_kb": sum(len(json.dumps(data)) for data in _cache.values()) // 1024 if _cache else 0,
        "entries": [
            {
                "cache_key": key[:8] + "...",  # 只显示键的前8个字符
                "expires_at": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "ttl_seconds": max(0, int((expiry - now).total_seconds()))
            }
            for key, expiry in _cache_expiry.items()
        ]
    }
    return stats 