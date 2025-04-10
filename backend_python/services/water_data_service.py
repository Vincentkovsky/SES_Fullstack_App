import requests
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from core.config import Config
from core.cache import get_cache_key, get_cache, set_cache
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

def fetch_surface_water_data(site_id: str = "410001", 
                            start_date: str = "2024-03-24 00:00",
                            end_date: str = "2024-03-24 01:00",
                            frequency: str = "Instantaneous",
                            page_number: int = 1,
                            variable: str = "StreamWaterLevel",
                            use_cache: bool = True) -> Dict[str, Any]:
    """
    从WaterNSW API获取地表水数据
    
    Args:
        site_id: 站点ID (默认: 410001)
        start_date: 开始日期，格式为dd-MMM-yyyy HH:mm (例如: "24-Mar-2024 00:00")
        end_date: 结束日期，格式为dd-MMM-yyyy HH:mm (例如: "24-Mar-2024 01:00")
        frequency: 数据频率 (Instantaneous或Latest)
        page_number: 分页的页码
        variable: 变量类型 (StreamWaterLevel或FlowRate)
        use_cache: 是否使用缓存 (默认: True)
    
    Returns:
        Dict[str, Any]: 包含数据和缓存状态的字典
    """
    # 构建参数字典以便生成缓存键
    params = {
        'siteId': site_id,
        'frequency': frequency,
        'dataType': 'AutoQC',
        'pageNumber': page_number,
        'startDate': start_date,
        'endDate': end_date,
        'variable': variable
    }
    
    # 生成缓存键
    cache_key = get_cache_key(params)
    
    # 检查缓存
    if use_cache:
        cached_data = get_cache(cache_key)
        if cached_data:
            return {
                'data': cached_data,
                'from_cache': True,
                'cache_key': cache_key
            }
    
    # 如果缓存中没有或已过期，则从API获取数据
    url = urljoin(Config.WATERNSW_BASE_URL, Config.WATERNSW_SURFACE_WATER_ENDPOINT)
    
    headers = {
        'Ocp-Apim-Subscription-Key': Config.API_KEY,
        'Accept': 'application/json'
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=10)
    
    if response.status_code == 401:
        logger.error("WaterNSW API认证失败，请检查API密钥")
        raise Exception("WaterNSW API认证失败，请检查API密钥配置")
        
    response.raise_for_status()
    
    data = response.json()
    
    # 如果成功获取数据，更新缓存
    if use_cache:
        set_cache(cache_key, data)
    
    return {
        'data': data,
        'from_cache': False,
        'cache_key': cache_key
    }

def process_water_data(waternsw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理从WaterNSW获取的水数据，转换为时间序列格式
    
    Args:
        waternsw_data: 从WaterNSW API获取的原始数据
        
    Returns:
        Dict[str, Any]: 转换后的时间序列数据
    """
    timeseries_data = {}
    
    for record in waternsw_data.get('records', []):
        try:
            timestamp = record.get('timeStamp')
            if not timestamp:
                continue

            # 如果时间戳条目不存在则初始化
            if timestamp not in timeseries_data:
                timeseries_data[timestamp] = {
                    'timestamp': timestamp,
                    'waterLevel': None,
                    'flowRate': None
                }
            
            # 根据variableName更新适当的测量值
            variable_name = record.get('variableName')
            value = record.get('value')
            
            if variable_name == 'StreamWaterLevel':
                timeseries_data[timestamp]['waterLevel'] = value
            elif variable_name == 'FlowRate':
                timeseries_data[timestamp]['flowRate'] = value

        except (ValueError, TypeError) as e:
            logger.warning(f"解析记录时出错: {e}")
            continue
    
    # 将字典转换为排序列表
    sorted_timeseries = sorted(
        timeseries_data.values(),
        key=lambda x: x['timestamp']
    )
    
    # 构建响应数据
    site_id = waternsw_data.get('records', [{}])[0].get('siteId', '410001')
    response_data = {
        'site_id': site_id,
        'timeseries': sorted_timeseries,
        'total_records': len(sorted_timeseries)
    }
    
    return response_data 