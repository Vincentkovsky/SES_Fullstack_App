#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
推理运行脚本（带环境激活）

用于直接运行模型推理，包括激活必要的conda环境
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='运行洪水预测模型推理（带环境激活）')
    
    parser.add_argument('--model_path', type=str, default='best.pt',
                        help='模型文件路径 (默认: best.pt)')
    
    parser.add_argument('--data_dir', type=str, default='rainfall_20221024',
                        help='输入数据目录 (默认: rainfall_20221024)')
    
    parser.add_argument('--device', type=str, default='cuda:0',
                        help='计算设备 (默认: cuda:0)')
    
    parser.add_argument('--output_dir', type=str, default=None,
                        help='输出目录 (默认: DATA_DIR/inference_results/TIMESTAMP)')
    
    parser.add_argument('--timestamp', type=str, default=None,
                        help='时间戳 (默认: 自动生成)')
    
    parser.add_argument('--conda_env', type=str, default='flood_new',
                        help='Conda环境名称 (默认: flood_new)')
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 构建命令行参数
    cmd_args = []
    
    # 添加传递的参数
    if args.model_path:
        cmd_args.extend(['--model_path', args.model_path])
    
    if args.data_dir:
        cmd_args.extend(['--data_dir', args.data_dir])
    
    if args.device:
        cmd_args.extend(['--device', args.device])
    
    if args.output_dir:
        cmd_args.extend(['--output_dir', args.output_dir])
    
    if args.timestamp:
        cmd_args.extend(['--timestamp', args.timestamp])
    
    # 构建conda环境激活命令
    activate_cmd = f"source /projects/TCCTVS/.bashrc && conda activate {args.conda_env}"
    
    # 构建运行脚本命令
    inference_script = Path(__file__).parent / "run_inference.py"
    python_cmd = f"python {inference_script}"
    
    # 完整命令
    full_cmd = f"{activate_cmd} && {python_cmd} {' '.join(cmd_args)}"
    
    print(f"运行命令: {full_cmd}")
    
    # 执行命令
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    
    # 打印输出
    if result.stdout:
        print(result.stdout)
    
    if result.stderr:
        print(f"错误输出: {result.stderr}", file=sys.stderr)
    
    # 返回脚本执行状态
    return result.returncode

if __name__ == "__main__":
    sys.exit(main()) 