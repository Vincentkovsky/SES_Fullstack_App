#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NetCDF to Tiles API

This module provides HTTP endpoints for converting 3Di NetCDF results
to GeoTIFF files and generating map tiles.

Endpoints:
- POST /api/nc-to-tiles: Convert a specific NetCDF file to tiles
- GET /api/nc-to-tiles/status: Get the status of ongoing or completed conversions
"""

import os
import threading
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify
from http import HTTPStatus
import logging
from datetime import datetime
import time

# 导入工具模块
from utils.ncToTilesUtils import process_nc_to_tiles
from core.config import Config

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
nc_tiles_bp = Blueprint('nc_tiles', __name__)

# 存储转换任务的状态
conversion_tasks = {}


@nc_tiles_bp.route('/api/nc-to-tiles', methods=['POST'])
def convert_nc_to_tiles():
    """
    触发NetCDF到Tiles的转换过程
    
    请求体:
    {
        "results_file": "results_3di.nc",  // NetCDF结果文件名，位于data/3di_res/netcdf/目录下
        "gridadmin_file": "gridadmin.h5",  // gridadmin文件名，位于data/3di_res/目录下
        "dem_file": "5m_dem.tif",          // DEM文件名，位于data/3di_res/目录下
        "color_table": "color.txt",        // 颜色表文件名，位于resources/目录下
        "force_recalculate": false,        // 是否强制重新计算
        "zoom_levels": "0-14",             // 瓦片缩放级别
        "processes": 8                     // 并行进程数
    }
    
    返回:
    {
        "task_id": "uuid",                 // 任务ID
        "status": "running",               // 任务状态: running, completed, failed
        "message": "转换进程已启动"
    }
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        
        results_file = data.get('results_file', 'results_3di.nc')
        gridadmin_file = data.get('gridadmin_file', 'gridadmin.h5')
        dem_file = data.get('dem_file', '5m_dem.tif')
        color_table = data.get('color_table', 'color.txt')
        force_recalculate = data.get('force_recalculate', False)
        zoom_levels = data.get('zoom_levels', '0-14')
        processes = data.get('processes', 8)
        
        # 构建完整文件路径
        base_dir = Path(__file__).parent.parent
        results_path = str(base_dir / "data/3di_res/netcdf" / results_file)
        gridadmin_path = str(base_dir / "data/3di_res" / gridadmin_file)
        dem_path = str(base_dir / "data/3di_res" / dem_file)
        color_table_path = str(base_dir / "resources" / color_table)
        
        # 验证文件是否存在
        missing_files = []
        for file_path, file_name in [
            (results_path, "结果文件"),
            (gridadmin_path, "Gridadmin文件"),
            (dem_path, "DEM文件"),
            (color_table_path, "颜色表文件")
        ]:
            if not os.path.exists(file_path):
                missing_files.append(f"{file_name}: {file_path}")
        
        if missing_files:
            return jsonify({
                "error": "缺少必要的输入文件",
                "missing_files": missing_files
            }), HTTPStatus.BAD_REQUEST
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        waterdepth_folder = str(base_dir / f"data/3di_res/waterdepth_{timestamp}")
        tiles_root_folder = str(base_dir / f"data/3di_res/timeseries_tiles_{timestamp}")
        
        # 创建任务ID
        task_id = str(uuid.uuid4())
        
        # 更新任务状态
        conversion_tasks[task_id] = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "input": {
                "results_file": results_file,
                "gridadmin_file": gridadmin_file,
                "dem_file": dem_file,
                "color_table": color_table,
                "force_recalculate": force_recalculate,
                "zoom_levels": zoom_levels,
                "processes": processes
            },
            "output": {
                "waterdepth_folder": waterdepth_folder,
                "tiles_root_folder": tiles_root_folder
            },
            "progress": 0,
            "message": "任务已启动",
            "error": None,
            "completion_time": None
        }
        
        # 在后台线程中启动转换过程
        thread = threading.Thread(
            target=run_conversion,
            args=(
                task_id,
                gridadmin_path,
                results_path,
                dem_path,
                color_table_path,
                waterdepth_folder,
                tiles_root_folder,
                force_recalculate,
                zoom_levels,
                processes
            )
        )
        thread.daemon = True
        thread.start()
        
        # 返回任务ID和状态
        return jsonify({
            "task_id": task_id,
            "status": "running",
            "message": "转换进程已启动",
            "output": {
                "waterdepth_folder": waterdepth_folder,
                "tiles_root_folder": tiles_root_folder
            }
        }), HTTPStatus.ACCEPTED
        
    except Exception as e:
        logger.error(f"启动转换过程时出错: {str(e)}")
        return jsonify({
            "error": "启动转换过程时出错",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR


@nc_tiles_bp.route('/api/nc-to-tiles/status', methods=['GET'])
def get_conversion_status():
    """
    获取转换任务的状态
    
    查询参数:
        task_id (str, optional): 任务ID，如不指定则返回所有任务
        
    返回:
        JSON: 任务状态信息
    """
    try:
        task_id = request.args.get('task_id')
        
        if task_id:
            # 返回特定任务的状态
            task = conversion_tasks.get(task_id)
            if not task:
                return jsonify({
                    "error": f"未找到任务ID: {task_id}"
                }), HTTPStatus.NOT_FOUND
                
            return jsonify({
                "task_id": task_id,
                "status": task
            }), HTTPStatus.OK
        else:
            # 返回所有任务的概要
            task_summaries = {}
            for tid, task in conversion_tasks.items():
                task_summaries[tid] = {
                    "status": task["status"],
                    "start_time": task["start_time"],
                    "message": task["message"],
                    "progress": task["progress"],
                    "completion_time": task["completion_time"]
                }
            
            return jsonify({
                "tasks": task_summaries,
                "count": len(task_summaries)
            }), HTTPStatus.OK
            
    except Exception as e:
        logger.error(f"获取任务状态时出错: {str(e)}")
        return jsonify({
            "error": "获取任务状态时出错",
            "details": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR


def run_conversion(
    task_id, 
    gridadmin_path, 
    results_path, 
    dem_path, 
    color_table_path,
    waterdepth_folder,
    tiles_root_folder,
    force_recalculate,
    zoom_levels,
    processes
):
    """
    在后台运行转换过程
    
    Args:
        task_id: 任务ID
        gridadmin_path: Gridadmin文件路径
        results_path: 结果文件路径
        dem_path: DEM文件路径
        color_table_path: 颜色表文件路径
        waterdepth_folder: 水深度文件输出目录
        tiles_root_folder: 瓦片输出根目录
        force_recalculate: 是否强制重新计算
        zoom_levels: 瓦片缩放级别
        processes: 并行进程数
    """
    try:
        # 更新任务状态
        conversion_tasks[task_id]["message"] = "开始计算水深度"
        conversion_tasks[task_id]["progress"] = 10
        
        # 运行转换过程
        result = process_nc_to_tiles(
            gridadmin_path=gridadmin_path,
            results_path=results_path,
            dem_path=dem_path,
            color_table=color_table_path,
            waterdepth_folder=waterdepth_folder,
            tiles_root_folder=tiles_root_folder,
            force_recalculate=force_recalculate,
            zoom_levels=zoom_levels,
            processes=processes
        )
        
        # 转换成功，更新任务状态
        conversion_tasks[task_id].update({
            "status": "completed",
            "message": "转换成功完成",
            "progress": 100,
            "result": {
                "water_depth_count": len(result["water_depth_files"]),
                "processed_count": len(result["processed_files"]),
                "tile_folders_count": len(result["tile_folders"]),
                "sample_tile_folders": result["tile_folders"][:5] if result["tile_folders"] else []
            },
            "completion_time": datetime.now().isoformat()
        })
        
        logger.info(f"任务 {task_id} 成功完成")
        
    except Exception as e:
        # 转换失败，更新任务状态
        error_message = str(e)
        logger.error(f"任务 {task_id} 失败: {error_message}")
        
        conversion_tasks[task_id].update({
            "status": "failed",
            "message": "转换过程失败",
            "error": error_message,
            "completion_time": datetime.now().isoformat()
        }) 