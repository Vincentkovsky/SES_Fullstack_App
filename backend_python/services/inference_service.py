import os
import subprocess
import logging
from typing import Dict, Any, Tuple, Optional
from http import HTTPStatus
from pathlib import Path
import torch
from torch.utils.data import DataLoader
import numpy as np
import netCDF4 as nc
from datetime import datetime, timedelta
import multiprocessing as mp
from tqdm import tqdm
from threedidepth.calculate import calculate_waterdepth

from core.config import Config
from utils.helpers import get_timestamp
from ai_inference.model import MODEL_DIR

logger = logging.getLogger(__name__)

# Default configuration for inference
INFERENCE_CONFIG = {
    'start_time_steps': [0,], 
    'pred_length': 48, 
    'water_level_scale': 1.0, 
}

def load_model(model_path, device, dtype):
    """
    加载模型
    
    Args:
        model_path: 模型文件路径
        device: 设备 (cuda:0, cpu等)
        dtype: 数据类型 (torch.float32, torch.bfloat16等)
    
    Returns:
        加载的模型
    """
    try:
        # 动态导入模型类，避免直接依赖
        import sys
        sys.path.append(str(MODEL_DIR))
        from model import FloodTransformer
        
        # 创建与训练相同配置的模型
        model = FloodTransformer(
            context_length=47791,
            dem_input_dim=1280,
            rain_num_steps=48,
            width=768,
            heads=12,
            layers=12,
            pred_length=48
        )
        
        # 加载检查点
        checkpoint = torch.load(model_path, map_location='cpu')
        model.load_state_dict(checkpoint['model_state_dict'])
        model = model.to(device).to(dtype)
        model.eval()
        
        logger.info(f"模型已从{model_path}加载到{device}设备上")
        return model
    except Exception as e:
        logger.error(f"加载模型失败: {str(e)}")
        raise

def write_results_to_nc(water_level, data_dir, output_dir):
    """
    将预测结果写入NetCDF文件
    
    Args:
        water_level: 水位预测结果
        data_dir: 输入数据目录
        output_dir: 输出目录
    
    Returns:
        结果文件路径
    """
    try:
        wl_array = water_level[0][0].transpose(1,0)  # (48, 47791)
        
        # 读取初始水位
        data_dir_path = MODEL_DIR / data_dir
        with nc.Dataset(f'{data_dir_path}/{data_dir}.nc', 'r') as dataset:
            wl_0 = dataset.variables['Mesh2D_s1'][0,:-12]  # 47791 初始水位
        
        # 加载预处理的数据
        dem_min = torch.load(f'{MODEL_DIR}/dem_min_tensor.pt', weights_only=True).numpy()
        water_level_min = torch.load(f'{MODEL_DIR}/water_level_min.pt', weights_only=True).numpy()
        
        # 处理初始水位
        wl_0 = np.ma.masked_where(wl_0 < dem_min, wl_0)
        wl_0 = (wl_0 - water_level_min)
        wl_0 = wl_0.filled(0)  # 初始水深
        
        # 计算水深
        water_depths = np.zeros((48, 47791))  # 形状: (timesteps, nodes)
        water_depths[0] = wl_0 + wl_array[0]  # 第一个时间步是初始值加上第一个差值
        
        for t in range(1, 48):
            water_depths[t] = water_depths[t-1] + wl_array[t]  # 将差值添加到前一个时间步
        
        # 转换为实际水位
        wl_masked = water_depths + water_level_min
        
        # 构建结果文件路径
        result_file = Path(output_dir) / 'result.nc'
        
        # 复制原始nc文件到结果目录
        import shutil
        source_file = Path(data_dir_path) / f'{data_dir}.nc'
        if not result_file.exists():
            shutil.copy(source_file, result_file)
        
        # 写入预测结果
        with nc.Dataset(result_file, 'r+') as dataset:
            # 获取原始数据
            mesh2d_s1 = dataset.variables['Mesh2D_s1'][:]
            # 替换前48个时间步的所有节点（除了最后12个）
            pred_steps = wl_masked.shape[0]
            mesh2d_s1[:pred_steps,:-12] = wl_masked
            # 写回文件
            dataset.variables['Mesh2D_s1'][:pred_steps] = mesh2d_s1[:pred_steps]
        
        logger.info(f"结果已写入到: {result_file}")
        return str(result_file)
    except Exception as e:
        logger.error(f"写入结果到NetCDF文件失败: {str(e)}")
        raise

def process_timestep(args):
    """
    处理单个时间步的函数
    
    Args:
        args: 包含处理所需参数的元组
        
    Returns:
        处理结果信息
    """
    gridadmin_path, results_path, dem_path, output_dir, timestamp, step = args
    
    time_str = timestamp.strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"waterdepth_{time_str}.tif")
    
    try:
        # 执行水深计算
        calculate_waterdepth(
            gridadmin_path=gridadmin_path,
            results_3di_path=results_path,
            dem_path=dem_path,
            waterdepth_path=output_path,
            calculation_steps=[step]
        )
        return f"步骤 {step} 计算完成: {output_path}"
    except Exception as e:
        logger.error(f"处理时间步 {step} 失败: {str(e)}")
        return f"步骤 {step} 计算出错: {str(e)}"

def generate_tif_files(start_tmp, output_dir):
    """
    从NetCDF结果生成TIF文件
    
    Args:
        start_tmp: 开始时间戳
        output_dir: 输出目录
    
    Returns:
        生成的TIF文件路径列表
    """
    try:
        # 输入路径
        gridadmin_path = f"{MODEL_DIR}/gridadmin.h5"
        results_path = f"{output_dir}/result.nc"
        dem_path = f"{MODEL_DIR}/5m_dem.tif"
        tif_output_dir = f"{output_dir}/{start_tmp}"
        num_workers = min(mp.cpu_count() - 2, 24)  # 留出2个核心给系统
        infer_steps = 48
        
        # 创建输出目录
        os.makedirs(tif_output_dir, exist_ok=True)
        
        # 从NetCDF文件中读取时间戳
        with nc.Dataset(results_path, mode="r") as nc_dataset:
            time_var = nc_dataset.variables["time"]
            time_units = time_var.units
            time_values = time_var[:]
            base_time = datetime.strptime(time_units.split("since")[1].strip(), "%Y-%m-%d %H:%M:%S")
            timestamps = [base_time + timedelta(seconds=float(t*1800)) for t in range(infer_steps)]
        
        # 准备并行处理的参数
        args_list = [
            (gridadmin_path, results_path, dem_path, tif_output_dir, timestamps[i], i)
            for i in range(infer_steps)
        ]
        
        # 使用进程池进行并行处理
        logger.info(f"使用 {num_workers} 个进程生成TIF文件")
        
        generated_files = []
        with mp.Pool(processes=num_workers) as pool:
            # 使用tqdm显示进度条
            results = list(tqdm(
                pool.imap(process_timestep, args_list),
                total=len(args_list),
                desc="处理时间步"
            ))
        
        # 收集生成的文件路径
        for i in range(infer_steps):
            time_str = timestamps[i].strftime("%Y%m%d_%H%M%S")
            tif_path = os.path.join(tif_output_dir, f"waterdepth_{time_str}.tif")
            if os.path.exists(tif_path):
                generated_files.append(tif_path)
        
        logger.info(f"生成了 {len(generated_files)} 个TIF文件")
        return generated_files
        
    except Exception as e:
        logger.error(f"生成TIF文件时出错: {str(e)}")
        raise

def run_inference(params: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """
    运行推理流程
    
    Args:
        params: 推理参数
        output_dir: 输出目录
    
    Returns:
        推理结果信息
    """
    try:
        # 提取参数，如果没有则使用默认值
        model_path = params.get('model_path', 'best.pt')
        data_dir = params.get('data_dir', 'rainfall_20221024')
        device = params.get('device', 'cuda:0' if torch.cuda.is_available() else 'cpu')
        start_tmp = params.get('start_tmp', get_timestamp())
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 记录开始时间
        start_time = datetime.now()
        logger.info(f"开始推理，模型: {model_path}, 数据: {data_dir}, 设备: {device}")
        
        # 配置设备和数据类型
        torch_device = torch.device(device)
        dtype = torch.bfloat16 if device.startswith('cuda') else torch.float32
        
        # 动态导入Dataset类
        import sys
        sys.path.append(str(MODEL_DIR))
        from dataset import FloodDataset
        
        # 创建数据集和数据加载器
        val_dataset = FloodDataset(f'{MODEL_DIR}/{data_dir}', INFERENCE_CONFIG)
        val_loader = DataLoader(
            val_dataset,
            batch_size=1,
            shuffle=False,
            num_workers=4,
            pin_memory=False
        )
        
        # 加载模型
        model = load_model(f'{MODEL_DIR}/{model_path}', torch_device, dtype)
        
        # 加载静态数据并转换为正确的数据类型
        dem_embed = torch.load(f'{MODEL_DIR}/dem_embeddings.pt', weights_only=True).to(torch_device, dtype=dtype)
        side_lens = torch.load(f'{MODEL_DIR}/side_lengths.pt', weights_only=True).to(torch_device)
        square_centers = torch.load(f'{MODEL_DIR}/square_centers.pt', weights_only=True).to(torch_device, dtype=dtype)
        
        all_water_levels = []  # 存储 (pred, target) 元组
        
        with torch.no_grad():
            for data, rain, u_target, v_target, water_level_target, has_water_target in val_loader:
                # 将数据移至设备并转换为正确的数据类型
                data = data.to(torch_device, dtype=dtype)
                rain = rain.to(torch_device, dtype=dtype)
                water_level_target = water_level_target.to(torch_device, dtype=dtype)
                
                # 前向传递
                water_level_pred, has_water_pred, u_pred, v_pred = model(data, rain, dem_embed, side_lens, square_centers)
                
                all_water_levels.append((
                    water_level_pred.cpu().to(dtype=torch.float32).numpy(),
                    water_level_target.cpu().to(dtype=torch.float32).numpy()
                ))
        
        # 写入结果到NetCDF文件
        nc_file = write_results_to_nc(all_water_levels[0], data_dir, output_dir)
        
        # 生成TIF文件
        tif_files = generate_tif_files(start_tmp, output_dir)
        
        # 计算总耗时
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # 返回结果信息
        return {
            "success": True,
            "message": "推理成功完成",
            "timestamp": start_tmp,
            "duration_seconds": elapsed_time,
            "results": {
                "nc_file": nc_file,
                "tif_files": tif_files,
                "tif_count": len(tif_files)
            }
        }
    except Exception as e:
        logger.error(f"推理过程中发生错误: {str(e)}")
        return {
            "success": False,
            "message": f"推理过程中发生错误: {str(e)}",
            "timestamp": get_timestamp()
        }

def execute_inference_script(params: Dict[str, Any] = None) -> Tuple[Dict[str, Any], int]:
    """
    执行推理并返回带有时间戳的结果
    
    Args:
        params: 推理参数
        
    Returns:
        Tuple[Dict[str, Any], int]: 响应数据和HTTP状态码
    """
    if params is None:
        params = {}
    
    # 生成当前时间戳
    start_tmp = params.get('start_tmp', get_timestamp())
    
    # 确定输出目录
    output_dir = Path(Config.DATA_DIR) / "inference_results" / start_tmp
    
    try:
        # 运行推理
        result = run_inference(params, output_dir)
        
        if result["success"]:
            return result, HTTPStatus.OK
        else:
            return result, HTTPStatus.INTERNAL_SERVER_ERROR
            
    except Exception as e:
        logger.error(f"执行推理过程中发生意外错误: {str(e)}")
        return {
            "error": "推理过程中发生意外错误",
            "details": str(e)
        }, HTTPStatus.INTERNAL_SERVER_ERROR

def get_latest_inference_dir() -> Path:
    """
    获取最新的推理目录
    
    Returns:
        Path: 最新推理目录的路径，如果不存在则返回None
    """
    try:
        inference_dirs = sorted([
            d for d in os.listdir(Path(Config.DATA_DIR) / "inference_results")
            if (Path(Config.DATA_DIR) / "inference_results" / d).is_dir()
        ], reverse=True)
        
        if not inference_dirs:
            return None
            
        return Path(Config.DATA_DIR) / "inference_results" / inference_dirs[0]
    except (FileNotFoundError, PermissionError):
        logger.error(f"无法访问推理目录: {Path(Config.DATA_DIR) / 'inference_results'}")
        return None 