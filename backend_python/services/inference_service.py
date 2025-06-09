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
import pwd
import grp

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
    def generate_tif_files(start_tmp: str, output_dir: Path, progress_callback = None) -> List[str]:
        """
        Generate TIF files from NetCDF results
        
        Args:
            start_tmp: Start timestamp
            output_dir: Output directory
            progress_callback: Optional callback function to report progress (default: None)
                              Function signature: progress_callback(progress, message)
        
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
            tif_output_dir = f"{output_dir}/geotiff"
            num_workers = min(mp.cpu_count() - 2, 24)  # Reserve 2 cores for system
            infer_steps = 48
            
            # Create output directory
            os.makedirs(tif_output_dir, exist_ok=True)
            
            # Set appropriate permissions (rwxrwsr-x)
            try:
                # Set permissions to 0o2775 (setgid bit + rwxrwsr-x)
                os.chmod(tif_output_dir, 0o2775)
                logger.info(f"Set permissions of {tif_output_dir} to 0o2775 (rwxrwsr-x)")
            except Exception as e:
                logger.warning(f"Failed to set permissions on {tif_output_dir}: {str(e)}")
            
            # Report progress if callback is available
            if progress_callback:
                try:
                    progress_callback(5, "Preparing to generate TIF files")
                except Exception as e:
                    logger.error(f"Error calling progress_callback: {str(e)}")
                    # If callback fails, set it to None to avoid further errors
                    progress_callback = None
            
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
            
            # Report progress if callback is available
            if progress_callback:
                try:
                    progress_callback(10, f"Using {num_workers} processes to generate {infer_steps} TIF files")
                except Exception as e:
                    logger.error(f"Error calling progress_callback: {str(e)}")
                    progress_callback = None
            
            # Use process pool for parallel processing
            logger.info(f"Using {num_workers} processes to generate TIF files")
            
            generated_files = []
            
            # Track progress for the callback
            completed_steps = 0
            total_steps = len(args_list)
            
            # Define a callback for each completed step
            def step_completed(result):
                nonlocal completed_steps
                completed_steps += 1
                progress_percent = int((completed_steps / total_steps) * 80) + 10  # Scale from 10% to 90%
                if progress_callback:
                    try:
                        progress_callback(progress_percent, f"Generated {completed_steps}/{total_steps} TIF files")
                    except Exception as e:
                        logger.error(f"Error calling progress_callback: {str(e)}")
            
            with mp.Pool(processes=num_workers) as pool:
                # Create async results and add callback
                async_results = []
                for args in args_list:
                    res = pool.apply_async(ResultsProcessor.process_timestep, (args,), callback=step_completed)
                    async_results.append(res)
                
                # Wait for all to complete
                for res in async_results:
                    res.wait()
            
            # Collect generated file paths
            for i in range(infer_steps):
                time_str = timestamps[i].strftime("%Y%m%d_%H%M%S")
                tif_path = os.path.join(tif_output_dir, f"waterdepth_{time_str}.tif")
                if os.path.exists(tif_path):
                    generated_files.append(tif_path)
            
            # Report final progress if callback is available
            if progress_callback:
                try:
                    progress_callback(100, f"Generated {len(generated_files)} TIF files")
                except Exception as e:
                    logger.error(f"Error calling progress_callback: {str(e)}")
            
            logger.info(f"Generated {len(generated_files)} TIF files")
            return generated_files
            
        except Exception as e:
            # Report error in progress if callback is available
            if progress_callback:
                try:
                    progress_callback(0, f"Error generating TIF files: {str(e)}")
                except Exception as callback_error:
                    logger.error(f"Error calling progress_callback: {str(callback_error)}")
            
            logger.error(f"Error generating TIF files: {str(e)}")
            raise RuntimeError(f"TIF file generation failed: {str(e)}") from e


class InferenceService:
    """Main inference service class"""
    
    def __init__(self):
        """Initialize inference service with process tracking variables"""
        self._is_running = False
        self._terminated = False
        self._process = None
    
    def terminate(self):
        """Terminate the running inference process"""
        logger.info("Received termination request for inference process")
        self._terminated = True
        
        # 如果有子进程，终止它
        if self._process is not None:
            try:
                logger.info(f"Attempting to terminate subprocess with PID: {self._process.pid}")
                import signal
                import os
                os.kill(self._process.pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to process {self._process.pid}")
                return True
            except Exception as e:
                logger.error(f"Error terminating subprocess: {str(e)}")
                return False
        return True
    
    def is_alive(self):
        """Check if the inference process is still alive"""
        return self._is_running and not self._terminated
    
    def run_inference(
        self,
        model_path: str = 'best.pt', 
        data_dir: str = 'rainfall_20221024', 
        device: str = None, 
        start_tmp: str = None, 
        output_dir: Path = None, 
        pred_length: int = 48,
        progress_callback = None
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
            progress_callback: Optional callback function to report progress (default: None)
                               Function signature: progress_callback(stage, progress, message)
        
        Returns:
            Inference result information
        """
        self._is_running = True
        self._terminated = False
        
        try:
            # Progress tracking function
            def update_progress(stage, progress, message=None):
                # 检查是否已请求终止
                if self._terminated:
                    if progress_callback:
                        progress_callback("cancelled", progress, "Task cancelled by user")
                    raise InterruptedError("Inference task was cancelled by user")
                
                if progress_callback:
                    progress_callback(stage, progress, message)
                logger.info(f"Progress - {stage}: {progress}% - {message or ''}")
            
            # Update progress - Initialization
            update_progress("initialization", 0, "Starting inference process")
            
            # Use defaults if not provided
            if device is None:
                device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            if start_tmp is None:
                start_tmp = get_timestamp()
            if output_dir is None:
                output_dir = Path(Config.DATA_DIR) / "inference_results" / start_tmp
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Set appropriate permissions (rwxrwsr-x)
            try:
                # Set permissions to 0o2775 (setgid bit + rwxrwsr-x)
                os.chmod(output_dir, 0o2775)
                logger.info(f"Set permissions of {output_dir} to 0o2775 (rwxrwsr-x)")
            except Exception as e:
                logger.warning(f"Failed to set permissions on {output_dir}: {str(e)}")
            
            # Update inference config with pred_length
            inference_config = INFERENCE_CONFIG.copy()
            inference_config['pred_length'] = pred_length
            
            # Record start time
            start_time = datetime.now()
            logger.info(f"Starting inference, model: {model_path}, data: {data_dir}, device: {device}, pred_length: {pred_length}")
            
            # Progress - Configuration complete
            update_progress("initialization", 5, "Configuration complete")
            
            # Configure device and data type
            torch_device = torch.device(device)
            dtype = torch.bfloat16 if device.startswith('cuda') else torch.float32
            
            # Progress - Device configured
            update_progress("initialization", 10, f"Using device: {device}")
            
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
            
            
            # Progress - Loading model
            update_progress("model_loading", 15, f"Loading model from {model_path}")
            
            # Load model
            model = ModelLoader.load_model(f'{MODEL_DIR}/{model_path}', torch_device, dtype)
            
            # Load static data and convert to correct data type
            dem_embed = torch.load(f'{MODEL_DIR}/dem_embeddings.pt', weights_only=True).to(torch_device, dtype=dtype)
            side_lens = torch.load(f'{MODEL_DIR}/side_lengths.pt', weights_only=True).to(torch_device)
            square_centers = torch.load(f'{MODEL_DIR}/square_centers.pt', weights_only=True).to(torch_device, dtype=dtype)
            
            # Progress - Model and data loaded
            update_progress("model_loading", 20, "Model loaded")
            
            
            # Progress - Loading dataset
            update_progress("data_loading", 25, "Loading dataset")
            
            all_water_levels = []  # Store (pred, target) tuples
            
            with torch.no_grad():
                for data, rain, u_target, v_target, water_level_target, has_water_target in val_loader:
                    # Move data to device and convert to correct data type
                    data = data.to(torch_device, dtype=dtype)
                    rain = rain.to(torch_device, dtype=dtype)
                    water_level_target = water_level_target.to(torch_device, dtype=dtype)
                    
                    # Progress - Dataset loaded
                    update_progress("data_loading", 40, "Dataset loaded to device")

                    # Progress - Running inference
                    update_progress("inference", 45, "Starting model inference")

                    # Forward pass
                    water_level_pred, has_water_pred, u_pred, v_pred = model(data, rain, dem_embed, side_lens, square_centers)
                    
                    all_water_levels.append((
                        water_level_pred.cpu().to(dtype=torch.float32).numpy(),
                        water_level_target.cpu().to(dtype=torch.float32).numpy()
                    ))
            
            # Progress - Inference complete, writing results
            update_progress("processing_results", 50, "Inference complete, writing results to NetCDF file")
            
            # Write results to NetCDF file
            nc_file = ResultsProcessor.write_results_to_nc(all_water_levels[0], data_dir, output_dir)
            
            # Progress - Generating TIF files
            update_progress("generating_tif_files", 60, "Generating TIF files")
            
            # Generate TIF files with a wrapped callback for TIF generation progress
            def tif_progress_callback(progress, message):
                # Scale progress from 0-100 to 60-100 range for overall progress
                scaled_progress = 60 + (progress * 0.4)
                update_progress("generating_tif_files", scaled_progress, message)
            
            # Generate TIF files
            tif_files = ResultsProcessor.generate_tif_files(start_tmp, output_dir, progress_callback=tif_progress_callback)
            
            # Progress - Process complete
            update_progress("completion", 100, "Processing complete")
            
            # Calculate total time
            end_time = datetime.now()
            elapsed_time = (end_time - start_time).total_seconds()
            
            # Create metadata.json with important information about the inference
            try:
                metadata = {
                    "task_id": start_tmp,
                    "timestamp": start_tmp,
                    "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": elapsed_time,
                    "model": model_path,
                    "data_source": data_dir,
                    "device": device,
                    "pred_length": pred_length,
                    "results": {
                        "nc_file": os.path.basename(nc_file) if nc_file else None,
                        "tif_count": len(tif_files),
                        "first_timestamp": os.path.basename(tif_files[0]) if tif_files else None,
                        "last_timestamp": os.path.basename(tif_files[-1]) if tif_files else None,
                    },
                    "simulation_name": os.path.basename(data_dir).replace('.nc', '')
                }
                
                # Write metadata to file
                metadata_path = os.path.join(output_dir, "metadata.json")
                with open(metadata_path, "w") as f:
                    import json
                    json.dump(metadata, f, indent=2)
                
                # Set appropriate permissions for the metadata file
                try:
                    os.chmod(metadata_path, 0o2775)
                    logger.info(f"Created metadata file at {metadata_path} with permissions 0o2775")
                except Exception as e:
                    logger.warning(f"Failed to set permissions on {metadata_path}: {str(e)}")
            except Exception as e:
                logger.error(f"Error creating metadata file: {str(e)}")
            
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
        except InterruptedError as e:
            # 处理取消任务的情况
            logger.info(f"Inference task was cancelled: {str(e)}")
            self._is_running = False
            return {
                "success": False,
                "message": f"Task cancelled: {str(e)}",
                "timestamp": get_timestamp(),
                "cancelled": True
            }
        except Exception as e:
            # Report error in progress if callback is available
            if progress_callback:
                progress_callback("error", 0, f"Error during inference: {str(e)}")
            
            logger.error(f"Error during inference: {str(e)}")
            self._is_running = False
            return {
                "success": False,
                "message": f"Error during inference: {str(e)}",
                "timestamp": get_timestamp()
            }
        finally:
            self._is_running = False

    def execute_inference_script(self, params: Dict[str, Any] = None) -> Tuple[Dict[str, Any], int]:
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
            result = self.run_inference(
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
    inference_service = InferenceService()
    
    if isinstance(params, dict):
        return inference_service.run_inference(
            model_path=params.get('model_path', 'best.pt'),
            data_dir=params.get('data_dir', 'rainfall_20221024'),
            device=params.get('device', 'cuda:0' if torch.cuda.is_available() else 'cpu'),
            start_tmp=params.get('start_tmp', get_timestamp()),
            output_dir=output_dir,
            pred_length=params.get('pred_length', 48)
        )
    else:
        # 假设 params 是 model_path 参数
        return inference_service.run_inference(model_path=params, output_dir=output_dir)

def execute_inference_script(params=None):
    """Backward compatibility function for executing inference script"""
    inference_service = InferenceService()
    return inference_service.execute_inference_script(params)

def get_latest_inference_dir():
    """Backward compatibility function for getting the latest inference directory"""
    return InferenceService.get_latest_inference_dir() 