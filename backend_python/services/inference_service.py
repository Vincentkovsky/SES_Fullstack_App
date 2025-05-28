import os
import logging
from typing import Dict, Any, Tuple, Optional, List
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
import shutil

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


class ModelLoader:
    """Model loading and management class"""
    
    @staticmethod
    def load_model(model_path: str, device: torch.device, dtype: torch.dtype) -> torch.nn.Module:
        """
        Load the flood prediction model
        
        Args:
            model_path: Path to the model file
            device: Device to load the model to (cuda:0, cpu, etc.)
            dtype: Data type for model (torch.float32, torch.bfloat16, etc.)
        
        Returns:
            Loaded model
        
        Raises:
            RuntimeError: If model loading fails
        """
        try:
            # Dynamically import model class
            import sys
            sys.path.append(str(MODEL_DIR))
            from model import FloodTransformer
            
            # Create model with the same configuration as training
            model = FloodTransformer(
                context_length=47791,
                dem_input_dim=1280,
                rain_num_steps=48,
                width=768,
                heads=12,
                layers=12,
                pred_length=48
            )
            
            # Load checkpoint
            checkpoint = torch.load(model_path, map_location='cpu')
            model.load_state_dict(checkpoint['model_state_dict'])
            model = model.to(device).to(dtype)
            model.eval()
            
            logger.info(f"Model loaded from {model_path} to {device} device")
            return model
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise RuntimeError(f"Model loading failed: {str(e)}") from e


class ResultsProcessor:
    """Process and save inference results"""
    
    @staticmethod
    def write_results_to_nc(water_level: np.ndarray, data_dir: str, output_dir: Path) -> str:
        """
        Write prediction results to NetCDF file
        
        Args:
            water_level: Water level prediction results
            data_dir: Input data directory or path to NC file
            output_dir: Output directory
        
        Returns:
            Path to the result file
        
        Raises:
            RuntimeError: If writing results fails
        """
        try:
            wl_array = water_level[0][0].transpose(1, 0)  # (48, 47791)
            
            # Determine source file path based on whether data_dir is a file path or directory name
            data_path = Path(data_dir)
            if data_path.is_file() and data_path.suffix == '.nc':
                # Data_dir is a full file path
                source_file = data_path
                # Extract filename for dataset name
                nc_file_name = data_path.name
            else:
                # Data_dir is a directory name (original behavior)
                data_dir_path = MODEL_DIR / data_dir
                source_file = data_dir_path / f'{data_dir}.nc'
                nc_file_name = f'{data_dir}.nc'
            
            # Read initial water level
            with nc.Dataset(str(source_file), 'r') as dataset:
                wl_0 = dataset.variables['Mesh2D_s1'][0, :-12]  # 47791 initial water level
            
            # Load preprocessed data
            dem_min = torch.load(f'{MODEL_DIR}/dem_min_tensor.pt', weights_only=True).numpy()
            water_level_min = torch.load(f'{MODEL_DIR}/water_level_min.pt', weights_only=True).numpy()
            
            # Process initial water level
            wl_0 = np.ma.masked_where(wl_0 < dem_min, wl_0)
            wl_0 = (wl_0 - water_level_min)
            wl_0 = wl_0.filled(0)  # Initial water depth
            
            # Calculate water depths
            water_depths = np.zeros((48, 47791))  # Shape: (timesteps, nodes)
            water_depths[0] = wl_0 + wl_array[0]  # First timestep is initial value plus first difference
            
            for t in range(1, 48):
                water_depths[t] = water_depths[t-1] + wl_array[t]  # Add difference to previous timestep
            
            # Convert to actual water level
            wl_masked = water_depths + water_level_min
            
            # Build result file path
            result_file = Path(output_dir) / 'result.nc'
            
            # Copy original nc file to result directory
            if not result_file.exists():
                shutil.copy(source_file, result_file)
            
            # Write prediction results
            with nc.Dataset(result_file, 'r+') as dataset:
                # Get original data
                mesh2d_s1 = dataset.variables['Mesh2D_s1'][:]
                # Replace first 48 timesteps for all nodes (except last 12)
                pred_steps = wl_masked.shape[0]
                mesh2d_s1[:pred_steps, :-12] = wl_masked
                # Write back to file
                dataset.variables['Mesh2D_s1'][:pred_steps] = mesh2d_s1[:pred_steps]
            
            logger.info(f"Results written to: {result_file}")
            return str(result_file)
        except Exception as e:
            logger.error(f"Failed to write results to NetCDF file: {str(e)}")
            raise RuntimeError(f"Failed to write results: {str(e)}") from e

    @staticmethod
    def process_timestep(args: Tuple) -> str:
        """
        Process a single timestep
        
        Args:
            args: Tuple containing (gridadmin_path, results_path, dem_path, output_dir, timestamp, step)
        
        Returns:
            Processing result information
        """
        gridadmin_path, results_path, dem_path, output_dir, timestamp, step = args
        
        time_str = timestamp.strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"waterdepth_{time_str}.tif")
        
        try:
            # Execute water depth calculation
            calculate_waterdepth(
                gridadmin_path=gridadmin_path,
                results_3di_path=results_path,
                dem_path=dem_path,
                waterdepth_path=output_path,
                calculation_steps=[step]
            )
            return f"Step {step} calculation completed: {output_path}"
        except Exception as e:
            logger.error(f"Failed to process timestep {step}: {str(e)}")
            return f"Step {step} calculation error: {str(e)}"

    @staticmethod
    def generate_tif_files(start_tmp: str, output_dir: Path) -> List[str]:
        """
        Generate TIF files from NetCDF results
        
        Args:
            start_tmp: Start timestamp
            output_dir: Output directory
        
        Returns:
            List of generated TIF file paths
        
        Raises:
            RuntimeError: If TIF file generation fails
        """
        try:
            # Input paths
            gridadmin_path = f"{MODEL_DIR}/gridadmin.h5"
            results_path = f"{output_dir}/result.nc"
            dem_path = f"{MODEL_DIR}/5m_dem.tif"
            tif_output_dir = f"{output_dir}/{start_tmp}"
            num_workers = min(mp.cpu_count() - 2, 24)  # Reserve 2 cores for system
            infer_steps = 48
            
            # Create output directory
            os.makedirs(tif_output_dir, exist_ok=True)
            
            # Read timestamps from NetCDF file
            with nc.Dataset(results_path, mode="r") as nc_dataset:
                time_var = nc_dataset.variables["time"]
                time_units = time_var.units
                base_time = datetime.strptime(time_units.split("since")[1].strip(), "%Y-%m-%d %H:%M:%S")
                timestamps = [base_time + timedelta(seconds=float(t*1800)) for t in range(infer_steps)]
            
            # Prepare parallel processing parameters
            args_list = [
                (gridadmin_path, results_path, dem_path, tif_output_dir, timestamps[i], i)
                for i in range(infer_steps)
            ]
            
            # Use process pool for parallel processing
            logger.info(f"Using {num_workers} processes to generate TIF files")
            
            generated_files = []
            with mp.Pool(processes=num_workers) as pool:
                # Use tqdm to display progress bar
                results = list(tqdm(
                    pool.imap(ResultsProcessor.process_timestep, args_list),
                    total=len(args_list),
                    desc="Processing timesteps"
                ))
            
            # Collect generated file paths
            for i in range(infer_steps):
                time_str = timestamps[i].strftime("%Y%m%d_%H%M%S")
                tif_path = os.path.join(tif_output_dir, f"waterdepth_{time_str}.tif")
                if os.path.exists(tif_path):
                    generated_files.append(tif_path)
            
            logger.info(f"Generated {len(generated_files)} TIF files")
            return generated_files
            
        except Exception as e:
            logger.error(f"Error generating TIF files: {str(e)}")
            raise RuntimeError(f"TIF file generation failed: {str(e)}") from e


class InferenceService:
    """Main inference service class"""
    
    @staticmethod
    def run_inference(
        model_path: str = 'best.pt', 
        data_dir: str = 'rainfall_20221024', 
        device: str = None, 
        start_tmp: str = None, 
        output_dir: Path = None, 
        pred_length: int = 48
    ) -> Dict[str, Any]:
        """
        Run inference process
        
        Args:
            model_path: Path to the model file (default: best.pt)
            data_dir: Input data path - can be a directory name or full path to .nc file (default: rainfall_20221024)
            device: Computing device (default: cuda:0 if available, otherwise cpu)
            start_tmp: Start timestamp (default: auto-generated)
            output_dir: Output directory (default: created based on data_dir and timestamp)
            pred_length: Number of prediction timesteps (default: 48)
        
        Returns:
            Inference result information
        """
        try:
            # Use defaults if not provided
            if device is None:
                device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            if start_tmp is None:
                start_tmp = get_timestamp()
            if output_dir is None:
                output_dir = Path(Config.DATA_DIR) / "inference_results" / start_tmp
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Update inference config with pred_length
            inference_config = INFERENCE_CONFIG.copy()
            inference_config['pred_length'] = pred_length
            
            # Record start time
            start_time = datetime.now()
            logger.info(f"Starting inference, model: {model_path}, data: {data_dir}, device: {device}, pred_length: {pred_length}")
            
            # Configure device and data type
            torch_device = torch.device(device)
            dtype = torch.bfloat16 if device.startswith('cuda') else torch.float32
            
            # Dynamically import Dataset class
            import sys
            sys.path.append(str(MODEL_DIR))
            from dataset import FloodDataset
            
            # Create dataset and data loader
            val_dataset = FloodDataset(data_dir, inference_config)

            val_loader = DataLoader(
                val_dataset,
                batch_size=1,
                shuffle=False,
                num_workers=4,
                pin_memory=False
            )
            
            # Load model
            model = ModelLoader.load_model(f'{MODEL_DIR}/{model_path}', torch_device, dtype)
            
            # Load static data and convert to correct data type
            dem_embed = torch.load(f'{MODEL_DIR}/dem_embeddings.pt', weights_only=True).to(torch_device, dtype=dtype)
            side_lens = torch.load(f'{MODEL_DIR}/side_lengths.pt', weights_only=True).to(torch_device)
            square_centers = torch.load(f'{MODEL_DIR}/square_centers.pt', weights_only=True).to(torch_device, dtype=dtype)
            
            all_water_levels = []  # Store (pred, target) tuples
            
            with torch.no_grad():
                for data, rain, u_target, v_target, water_level_target, has_water_target in val_loader:
                    # Move data to device and convert to correct data type
                    data = data.to(torch_device, dtype=dtype)
                    rain = rain.to(torch_device, dtype=dtype)
                    water_level_target = water_level_target.to(torch_device, dtype=dtype)
                    
                    # Forward pass
                    water_level_pred, has_water_pred, u_pred, v_pred = model(data, rain, dem_embed, side_lens, square_centers)
                    
                    all_water_levels.append((
                        water_level_pred.cpu().to(dtype=torch.float32).numpy(),
                        water_level_target.cpu().to(dtype=torch.float32).numpy()
                    ))
            
            # Write results to NetCDF file
            nc_file = ResultsProcessor.write_results_to_nc(all_water_levels[0], data_dir, output_dir)
            
            # Generate TIF files
            tif_files = ResultsProcessor.generate_tif_files(start_tmp, output_dir)
            
            # Calculate total time
            end_time = datetime.now()
            elapsed_time = (end_time - start_time).total_seconds()
            
            # Return result information
            return {
                "success": True,
                "message": "Inference completed successfully",
                "timestamp": start_tmp,
                "duration_seconds": elapsed_time,
                "results": {
                    "nc_file": nc_file,
                    "tif_files": tif_files,
                    "tif_count": len(tif_files)
                }
            }
        except Exception as e:
            logger.error(f"Error during inference: {str(e)}")
            return {
                "success": False,
                "message": f"Error during inference: {str(e)}",
                "timestamp": get_timestamp()
            }

    @staticmethod
    def execute_inference_script(params: Dict[str, Any] = None) -> Tuple[Dict[str, Any], int]:
        """
        Execute inference and return timestamped results
        
        Args:
            params: Inference parameters
            
        Returns:
            Tuple[Dict[str, Any], int]: Response data and HTTP status code
        """
        if params is None:
            params = {}
        
        # Generate current timestamp
        start_tmp = params.get('start_tmp', get_timestamp())
        
        # Determine output directory
        output_dir = Path(Config.DATA_DIR) / "inference_results" / start_tmp
        
        try:
            # Run inference
            result = InferenceService.run_inference(
                model_path=params.get('model_path', 'best.pt'),
                data_dir=params.get('data_dir', 'rainfall_20221024'),
                device=params.get('device', 'cuda:0' if torch.cuda.is_available() else 'cpu'),
                start_tmp=start_tmp,
                output_dir=output_dir,
                pred_length=params.get('pred_length', 48)
            )
            
            if result["success"]:
                return result, HTTPStatus.OK
            else:
                return result, HTTPStatus.INTERNAL_SERVER_ERROR
                
        except Exception as e:
            logger.error(f"Unexpected error during inference execution: {str(e)}")
            return {
                "error": "Unexpected error during inference",
                "details": str(e)
            }, HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def get_latest_inference_dir() -> Optional[Path]:
        """
        Get the latest inference directory
        
        Returns:
            Path: Path to the latest inference directory, or None if it doesn't exist
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
            logger.error(f"Cannot access inference directory: {Path(Config.DATA_DIR) / 'inference_results'}")
            return None


# Export function interfaces for backward compatibility
def load_model(model_path, device, dtype):
    """Backward compatibility function for model loading"""
    return ModelLoader.load_model(model_path, device, dtype)

def write_results_to_nc(water_level, data_dir, output_dir):
    """Backward compatibility function for writing results"""
    return ResultsProcessor.write_results_to_nc(water_level, data_dir, output_dir)

def process_timestep(args):
    """Backward compatibility function for processing timesteps"""
    return ResultsProcessor.process_timestep(args)

def generate_tif_files(start_tmp, output_dir):
    """Backward compatibility function for generating TIF files"""
    return ResultsProcessor.generate_tif_files(start_tmp, output_dir)

def run_inference(params, output_dir):
    """Backward compatibility function for running inference"""
    if isinstance(params, dict):
        return InferenceService.run_inference(
            model_path=params.get('model_path', 'best.pt'),
            data_dir=params.get('data_dir', 'rainfall_20221024'),
            device=params.get('device', 'cuda:0' if torch.cuda.is_available() else 'cpu'),
            start_tmp=params.get('start_tmp', get_timestamp()),
            output_dir=output_dir,
            pred_length=params.get('pred_length', 48)
        )
    else:
        # 假设 params 是 model_path 参数
        return InferenceService.run_inference(model_path=params, output_dir=output_dir)

def execute_inference_script(params=None):
    """Backward compatibility function for executing inference script"""
    return InferenceService.execute_inference_script(params)

def get_latest_inference_dir():
    """Backward compatibility function for getting the latest inference directory"""
    return InferenceService.get_latest_inference_dir() 