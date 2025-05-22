#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
推理运行脚本

用于直接运行模型推理，代替bash脚本版本
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import json
from datetime import datetime

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent
base_dir = current_dir
sys.path.append(str(base_dir))

# 导入推理服务
from services.inference_service import run_inference
from core.config import Config
from utils.helpers import get_timestamp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='运行洪水预测模型推理')
    
    parser.add_argument('--model_path', type=str, default='best.pt',
                        help='模型文件路径 (默认: best.pt)')
    
    parser.add_argument('--data_dir', type=str, default='rainfall_20221024',
                        help='输入数据目录 (默认: rainfall_20221024)')
    
    parser.add_argument('--device', type=str, default='cuda:0' if 'CUDA_VISIBLE_DEVICES' in os.environ else 'cpu',
                        help='计算设备 (默认: cuda:0 如果CUDA可用，否则为cpu)')
    
    parser.add_argument('--output_dir', type=str, default=None,
                        help='输出目录 (默认: DATA_DIR/inference_results/TIMESTAMP)')
    
    parser.add_argument('--timestamp', type=str, default=None,
                        help='时间戳 (默认: 自动生成)')
    
    return parser.parse_args()

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 生成时间戳
    timestamp = args.timestamp or get_timestamp()
    
    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(Config.DATA_DIR) / "inference_results" / timestamp
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"开始运行推理，模型: {args.model_path}, 数据: {args.data_dir}")
    logger.info(f"输出目录: {output_dir}")
    
    # 构建参数字典
    params = {
        'model_path': args.model_path,
        'data_dir': args.data_dir,
        'device': args.device,
        'start_tmp': timestamp
    }
    
    # 保存参数到JSON
    with open(output_dir / "parameters.json", 'w') as f:
        json.dump(params, f, indent=2)
    
    # 开始时间
    start_time = datetime.now()
    
    try:
        # 运行推理
        result = run_inference(params, output_dir)
        
        # 结束时间
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # 保存结果状态
        status_info = {
            "status": "completed" if result.get("success", False) else "failed",
            "start_time": start_time.timestamp(),
            "end_time": end_time.timestamp(),
            "elapsed_time": elapsed_time,
            "parameters": params,
            "results": result.get("results", {})
        }
        
        with open(output_dir / "status.json", 'w') as f:
            json.dump(status_info, f, indent=2)
        
        # 输出结果
        if result.get("success", False):
            logger.info(f"推理成功完成，耗时: {elapsed_time:.2f}秒")
            logger.info(f"结果文件: {result.get('results', {}).get('nc_file')}")
            logger.info(f"生成了 {result.get('results', {}).get('tif_count', 0)} 个TIF文件")
        else:
            logger.error(f"推理失败: {result.get('message', '未知错误')}")
            return 1
        
        return 0
    
    except Exception as e:
        logger.exception(f"推理过程中发生错误: {str(e)}")
        
        # 保存错误信息
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        error_info = {
            "status": "failed",
            "start_time": start_time.timestamp(),
            "end_time": end_time.timestamp(),
            "elapsed_time": elapsed_time,
            "error": str(e),
            "parameters": params
        }
        
        with open(output_dir / "status.json", 'w') as f:
            json.dump(error_info, f, indent=2)
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 