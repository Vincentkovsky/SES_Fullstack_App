from typing import List, Optional, Union, Dict, Any
from threedi_api_client.threedi_api_client import ThreediApiClient
from threedi_api_client.api import ThreediApi
from threedi_api_client.versions import V3Api
from threedi_api_client.openapi.exceptions import ApiException
from datetime import datetime, timedelta
import time
import os
import json
from pathlib import Path
import urllib3
import ssl
import certifi
from upload_file import custom_upload_file

# 创建自定义的 SSL 上下文
ssl_context = ssl.create_default_context(cafile=certifi.where())

# 配置 urllib3 使用自定义的 SSL 上下文
urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'
urllib3.util.ssl_.create_urllib3_context = lambda *args, **kwargs: ssl_context

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 定义初始水位到边界条件的映射
INITIAL_WATER_LEVEL_MAP = {
    'extremehigh': 'EXTREMEHIGH_WATER_LEVEL',
    'high': 'HIGH_WATER_LEVEL',
    'middle': 'MIDDLE_WATER_LEVEL',
    'low': 'LOW_WATER_LEVEL'
}

class BatchSimulator:
    """A class to manage batch simulations using the ThreediApi client."""
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize the BatchSimulator.
        
        Args:
            env_file (str): Path to the environment file containing API credentials
        """
        self.env_file = env_file
        self.threedi_api: V3Api = ThreediApi(env_file)
        self.simulation_duration = 86400 * 3  # 3 days default
        self.simulation_starttime = datetime(2024, 1, 1, 0, 0, 0)
        self.progress_file = 'simulation_progress.json'
        
        # Verify authentication
        self._verify_auth()
    
    def _verify_auth(self) -> None:
        """Verify authentication with the ThreediApi."""
        try:
            user = self.threedi_api.auth_profile_list()
            print(f"Successfully logged in as {user.username}!")
        except ApiException as e:
            raise Exception("Authentication failed") from e
    
    def load_progress(self) -> Dict[str, Any]:
        """Load simulation progress from the progress file."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    return {}
        return {}
    
    def save_progress(self, progress: Dict[str, Any]) -> None:
        """
        Save simulation progress to the progress file.
        
        Args:
            progress (Dict[str, Any]): Progress data to save
        """
        with open(self.progress_file, 'w') as file:
            json.dump(progress, file, indent=4)
    
    def fetch_model(self, name: str) -> Any:
        """
        Fetch a model by name.
        
        Args:
            name (str): Name of the model to fetch
            
        Returns:
            Any: The first matching model
        """
        models = self.threedi_api.threedimodels_list(name__icontains=name)
        return models.results[0]
    
    def fetch_org_id(self, org_name: str) -> str:
        """
        Fetch organization ID by name.
        
        Args:
            org_name (str): Name of the organization
            
        Returns:
            str: Organization unique ID
        """
        orgs = self.threedi_api.organisations_list(name__icontains=org_name)
        return orgs.results[0].unique_id
    
    def search_simulation(self, simulation_name: str, simulation_tags: List[str]) -> Optional[Any]:
        """
        Search for an existing simulation by name and tags.
        
        Args:
            simulation_name (str): Name of the simulation
            simulation_tags (List[str]): List of tags to match
            
        Returns:
            Optional[Any]: Matching simulation if found, None otherwise
        """
        simulations = self.threedi_api.simulations_list(name__icontains=simulation_name)
        
        for simulation in simulations.results:
            tags = simulation.tags
            simulation_id = simulation.id
            
            status = self.threedi_api.simulations_status_list(simulation_id)
            
            tags_equal = set(tags) == set(simulation_tags)
            if status.name not in ['crashed', 'created'] and tags_equal:
                return simulation
        
        return None
    
    def create_simulation(
        self,
        model: Any,
        org_id: str,
        name: str,
        tags: Union[str, List[str]],
        starttime: Optional[datetime] = None,
        duration: Optional[int] = None
    ) -> Any:
        """
        Create a new simulation.
        
        Args:
            model: The model to use for simulation
            org_id (str): Organization ID
            name (str): Simulation name
            tags (Union[str, List[str]]): Tags for the simulation
            starttime (Optional[datetime]): Start time for simulation
            duration (Optional[int]): Duration in seconds
            
        Returns:
            Any: Created simulation object
        """
        if not isinstance(tags, list):
            tags = [tags]
            
        starttime = starttime or self.simulation_starttime
        duration = duration or self.simulation_duration
        
        template = self.threedi_api.simulation_templates_list(
            simulation__threedimodel__id=model.id
        ).results[0]
        
        data = {
            "template": template.id,
            "name": name,
            "tags": tags,
            "organisation": org_id,
            "start_datetime": starttime,
            "duration": duration,
            "clone_events": False,
            "clone_initials": False
        }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                return self.threedi_api.simulations_from_template(data=data)
            except ApiException as e:
                if e.status == 429 and attempt < max_retries - 1:
                    retry_after = int(e.headers.get("Retry-After", retry_delay))
                    print(f"Request throttled. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                    retry_delay *= 2
                else:
                    raise
    
    def wait_for_processing(self, simulation_id: int, max_retries: int = 20, retry_delay: int = 30) -> None:
        """
        等待所有文件处理完成
        
        Args:
            simulation_id: 模拟ID
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        for attempt in range(max_retries):
            files_ready = True
            
            # 检查边界条件文件
            try:
                boundary_conditions = self.threedi_api.simulations_events_boundaryconditions_file_list(
                    simulation_id
                ).results[0]
                
                if hasattr(boundary_conditions, 'state_description'):
                    if 'error' in boundary_conditions.state_description.lower():
                        raise Exception(f"Boundary conditions file processing failed: {boundary_conditions.state_description}")
                    elif 'uploaded' in boundary_conditions.state_description.lower():
                        files_ready = False
                        print("Boundary conditions file still uploading...")
                    else:
                        print("Boundary conditions file processed successfully")
            except IndexError:
                print("No boundary conditions file found")
            
            # 检查降雨文件
            try:
                rainfall = self.threedi_api.simulations_events_rain_rasters_netcdf_list(
                    simulation_id
                ).results[0]
                
                if hasattr(rainfall, 'state_description'):
                    if 'error' in rainfall.state_description.lower():
                        raise Exception(f"Rainfall file processing failed: {rainfall.state_description}")
                    elif 'uploaded' in rainfall.state_description.lower():
                        files_ready = False
                        print("Rainfall file still uploading...")
                    else:
                        print("Rainfall file processed successfully")
            except IndexError:
                print("No rainfall file found")
            
            if files_ready:
                print("All files processed successfully")
                break
            
            print(f"Files still processing, waiting {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 300)  # 指数退避，但最大不超过5分钟
        
        if attempt == max_retries - 1:
            raise Exception("Files processing timeout")

    def create_nc_rainfall_event(self, simulation: Any, file_path: str) -> None:
        """
        Create a NetCDF rainfall event for a simulation.
        
        Args:
            simulation: The simulation object
            file_path (str): Path to the NetCDF file
        """
        upload_object = self.threedi_api.simulations_events_rain_rasters_netcdf_create(
            simulation.id,
            data={"filename": file_path}
        )
        custom_upload_file(upload_object.put_url, file_path)
    
    def create_boundary_conditions(
        self,
        simulation: Any,
        file_name: str,
        boundary_type: str
    ) -> None:
        """
        Create boundary conditions for a simulation.
        
        Args:
            simulation: The simulation object
            file_name (str): Name of the boundary condition file
            boundary_type (str): Type of boundary ('water_level' or other)
        """
        try:
            boundary_conditions = self.threedi_api.simulations_events_boundaryconditions_file_list(
                simulation.id
            ).results[0]
            self.threedi_api.simulations_events_boundaryconditions_file_delete(
                boundary_conditions.id,
                simulation.id
            )
        except IndexError:
            pass
        
        if boundary_type == 'water_level':
            file_path = f"boundary_condition/{boundary_type}/{file_name}.json"
        else:
            file_path = f'boundary_condition/{boundary_type}/{file_name}.json'
            
        upload_object = self.threedi_api.simulations_events_boundaryconditions_file_create(
            simulation.id,
            data={"filename": file_path}
        )
        custom_upload_file(upload_object.put_url, file_path)
    
    def start_simulation(self, simulation: Any) -> None:
        """
        Start a simulation with retry logic for rate limits.
        
        Args:
            simulation: The simulation to start
        """
        # 等待文件处理完成
        self.wait_for_processing(simulation.id)
        
        max_retries = 5
        retry_delay = 60
        
        for attempt in range(max_retries):
            try:
                self.threedi_api.simulations_actions_create(
                    simulation.id,
                    data={"name": "queue"}
                )
                status = self.threedi_api.simulations_status_list(simulation.id)
                print(f"Simulation {simulation.name} is {status.name}")
                break
            except ApiException as e:
                if e.status == 429 and attempt < max_retries - 1:
                    print(f"Rate limit reached. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

    def upload_initial_raster(self, model: Any, raster_name: str) -> Any:
        """
        上传初始水位栅格文件
        
        Args:
            model: 模型对象
            raster_name: 栅格文件名（不含扩展名）
            
        Returns:
            Any: 上传的栅格对象
        """
        # 设置栅格文件路径
        initial_2D_water_level_file = Path(f"initial_water_level/{raster_name}.tif")
        
        # 检查是否已存在同名栅格
        results = self.threedi_api.threedimodels_rasters_list(
            model.id,
            type="initial_waterlevel_file",
            name=raster_name
        )
        
        if results.count == 0:
            # 创建新的栅格
            raster = self.threedi_api.threedimodels_rasters_create(
                model.id,
                {"name": raster_name, "type": "initial_waterlevel_file"}
            )
            print(f"Created raster with id {raster.id}")
            
            # 上传栅格文件
            upload = self.threedi_api.threedimodels_rasters_upload(
                raster.id,
                model.id,
                {"filename": raster_name}
            )
            custom_upload_file(upload.put_url, initial_2D_water_level_file)
        else:
            print(f"Raster '{raster_name}' has already been uploaded")
            raster = results.results[0]
        
        return raster

    def check_raster_processing(self, raster: Any, model: Any, max_retries: int = 12, retry_delay: int = 5) -> Any:
        """
        检查栅格处理状态并等待完成
        
        Args:
            raster: 栅格对象
            model: 模型对象
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            
        Returns:
            Any: 处理完成的初始水位对象
        """
        print(f"Looking for raster with ID {raster.id}")
        
        for attempt in range(max_retries):
            results = self.threedi_api.threedimodels_initial_waterlevels_list(model.id, limit=200)
            two_d_levels = [x for x in results.results if x.dimension == 'two_d' and x.source_raster_id == raster.id]
            
            if two_d_levels:
                initial_2d_water_level = two_d_levels[0]
                print(f"Found processed initial water level with id {initial_2d_water_level.id}")
                return initial_2d_water_level
            
            print(f"Processing not yet finished, will check again in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
        
        raise Exception(f"Could not find the 2D initial water level for raster {raster.id}")

    def update_initial_water_level(self, simulation: Any, initial_2d_water_level: Any) -> None:
        """
        更新模拟的初始水位设置
        
        Args:
            simulation: 模拟对象
            initial_2d_water_level: 初始水位对象
        """
        # 删除现有的初始水位设置（如果有）
        try:
            current = self.threedi_api.simulations_initial2d_water_level_raster_list(
                simulation_pk=simulation.id
            ).results[0]
            self.threedi_api.simulations_initial2d_water_level_raster_delete(
                simulation_pk=simulation.id,
                id=current.id
            )
        except IndexError:
            pass
        
        # 创建新的初始水位设置
        sim_initial_2d_water_level = self.threedi_api.simulations_initial2d_water_level_raster_create(
            simulation.id,
            {
                "aggregation_method": "mean",
                "initial_waterlevel": initial_2d_water_level.id
            }
        )
        print(f"Using initial 2D water level with id {sim_initial_2d_water_level.id}")

    def delete_initial_rasters(self, model: Any, initial_rasters: List[str]) -> None:
        """
        删除指定的初始水位栅格
        
        Args:
            model: 模型对象
            initial_rasters: 要删除的栅格名称列表
        """
        results = self.threedi_api.threedimodels_rasters_list(model.id)
        for raster in results.results:
            if raster.name in initial_rasters:
                self.threedi_api.threedimodels_rasters_delete(raster.id, model.id)
                print(f"Deleted raster with id {raster.id}")

    def setup_initial_conditions(
        self,
        simulation: Any,
        model: Any,
        boundary_condition: str,
        boundary_type: str = 'discharge'
    ) -> None:
        """
        设置模拟的初始条件
        
        Args:
            simulation: 模拟对象
            model: 模型对象
            boundary_condition: 边界条件名称
            boundary_type: 边界条件类型
        """
        # 获取对应的初始水位栅格名称
        initial_raster = INITIAL_WATER_LEVEL_MAP[boundary_condition]
        
        # 上传并处理初始水位栅格
        raster = self.upload_initial_raster(model, initial_raster)
        processed_initial_water_level = self.check_raster_processing(raster, model)
        
        # 更新模拟的初始水位
        self.update_initial_water_level(simulation, processed_initial_water_level)
        
        # 添加边界条件
        self.create_boundary_conditions(simulation, boundary_condition, boundary_type)

# Example usage:
if __name__ == "__main__":
    import os
    from datetime import datetime, timedelta
    
    # Initialize the simulator
    simulator = BatchSimulator()
    
    # Load any existing progress
    progress = simulator.load_progress()
    
    # Fetch model and organization
    model = simulator.fetch_model("wagga_res_5m")
    org_id = simulator.fetch_org_id("Academic License")
    
    # 设置边界条件
    boundary_condition = "high"  # 可以是 'extremehigh', 'high', 'middle', 'low'
    
    # Get all nc files from historical_netcdf_converted folder
    nc_files = [f for f in os.listdir("historical_netcdf_converted") if f.endswith(".nc")]
    
    # Process each nc file
    for nc_file in nc_files:
        # Extract dates from filename (format: rainfall_YYYYMMDDHHMM_YYYYMMDDHHMM.nc)
        date_parts = nc_file.split("_")
        start_date_str = date_parts[1]
        end_date_str = date_parts[2].split(".")[0]  # Remove .nc extension
        
        # Parse start time
        start_year = int(start_date_str[:4])
        start_month = int(start_date_str[4:6])
        start_day = int(start_date_str[6:8])
        start_hour = int(start_date_str[8:10])
        start_minute = int(start_date_str[10:12])
        start_time = datetime(start_year, start_month, start_day, start_hour, start_minute)
        
        # Parse end time
        end_year = int(end_date_str[:4])
        end_month = int(end_date_str[4:6])
        end_day = int(end_date_str[6:8])
        end_hour = int(end_date_str[8:10])
        end_minute = int(end_date_str[10:12])
        end_time = datetime(end_year, end_month, end_day, end_hour, end_minute)
        
        # Calculate duration in seconds
        duration = int((end_time - start_time).total_seconds())
        
        # Add 24 hours buffer to ensure complete coverage
        duration += 24 * 3600
        
        # Create simulation name based on the nc file and boundary condition
        simulation_name = f"historical_rainfall_{start_date_str}_bc_{boundary_condition}"
        
        # Check if simulation already exists
        if simulator.search_simulation(simulation_name, ["historical", boundary_condition]):
            print(f"Simulation {simulation_name} already exists, skipping...")
            continue
        
        print(f"Creating simulation for {nc_file} with {boundary_condition} boundary condition...")
        print(f"Duration: {duration/3600:.1f} hours ({duration/86400:.1f} days)")
        
        # Create simulation with start time matching the nc file
        simulation = simulator.create_simulation(
            model=model,
            org_id=org_id,
            name=simulation_name,
            tags=["historical", boundary_condition],
            starttime=start_time,
            duration=duration
        )
        
        # Add rainfall data
        nc_file_path = os.path.join("historical_netcdf_converted", nc_file)
        simulator.create_nc_rainfall_event(
            simulation=simulation,
            file_path=nc_file_path
        )
        
        # Setup initial conditions (includes both initial water level and boundary conditions)
        simulator.setup_initial_conditions(
            simulation=simulation,
            model=model,
            boundary_condition=boundary_condition,
            boundary_type='discharge'
        )
        
        # Start the simulation
        simulator.start_simulation(simulation)
        
        # Save progress
        progress[simulation_name] = {
            "status": "started",
            "id": simulation.id,
            "nc_file": nc_file,
            "boundary_condition": boundary_condition,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_hours": duration/3600
        }
        simulator.save_progress(progress)
        
        # Wait a bit between simulations to avoid rate limiting
        time.sleep(5)
    
    print("All historical rainfall simulations have been created and started.") 