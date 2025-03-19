from typing import List, Optional, Union, Dict, Any
from threedi_api_client.threedi_api_client import ThreediApiClient
from threedi_api_client.api import ThreediApi
from threedi_api_client.versions import V3Api
from threedi_api_client.openapi.exceptions import ApiException
from threedi_api_client.files import upload_file
import datetime
import time
import os
import json
from pathlib import Path

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
        self.simulation_starttime = datetime.datetime(2024, 1, 1, 0, 0, 0)
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
        starttime: Optional[datetime.datetime] = None,
        duration: Optional[int] = None
    ) -> Any:
        """
        Create a new simulation.
        
        Args:
            model: The model to use for simulation
            org_id (str): Organization ID
            name (str): Simulation name
            tags (Union[str, List[str]]): Tags for the simulation
            starttime (Optional[datetime.datetime]): Start time for simulation
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
        upload_file(upload_object.put_url, file_path)
    
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
            file_path = f"boundary_condition/{boundary_type}/{file_name}m_boundary.json"
        else:
            file_path = f'boundary_condition/{boundary_type}/{file_name}.json'
            
        upload_object = self.threedi_api.simulations_events_boundaryconditions_file_create(
            simulation.id,
            data={"filename": file_path}
        )
        upload_file(upload_object.put_url, file_path)
    
    def start_simulation(self, simulation: Any) -> None:
        """
        Start a simulation with retry logic for rate limits.
        
        Args:
            simulation: The simulation to start
        """
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

# Example usage:
if __name__ == "__main__":
    # Initialize the simulator
    simulator = BatchSimulator()
    
    # Load any existing progress
    progress = simulator.load_progress()
    
    # Example workflow
    model = simulator.fetch_model("your_model_name")
    org_id = simulator.fetch_org_id("your_org_name")
    
    # Create a new simulation
    simulation = simulator.create_simulation(
        model=model,
        org_id=org_id,
        name="test_simulation",
        tags=["test"],
        starttime=datetime.datetime.now(),
        duration=86400  # 1 day
    )
    
    # Add rainfall data
    simulator.create_nc_rainfall_event(
        simulation=simulation,
        file_path="path/to/rainfall.nc"
    )
    
    # Add boundary conditions
    simulator.create_boundary_conditions(
        simulation=simulation,
        file_name="boundary_condition",
        boundary_type="water_level"
    )
    
    # Start the simulation
    simulator.start_simulation(simulation)
    
    # Save progress
    progress[simulation.name] = {"status": "started", "id": simulation.id}
    simulator.save_progress(progress) 