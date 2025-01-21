from typing import Dict, Any, Optional, List, Union
from netCDF4 import Dataset
import numpy as np
from datetime import datetime
from pyproj import Transformer
import logging

def XYtoLonLat(x, y):
    transformer = Transformer.from_crs("EPSG:32755", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return lon, lat

class NCReader:
    """NetCDF 文件读取器类"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nc = None
        
    def __enter__(self):
        self.nc = Dataset(self.file_path, mode='r')
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.nc is not None:
            self.nc.close()
    
    def get_global_attributes(self) -> Dict[str, Any]:
        return {key: getattr(self.nc, key) for key in self.nc.ncattrs()}
    
    def get_variables(self) -> List[str]:
        return list(self.nc.variables.keys())
    
    def get_dimensions(self) -> Dict[str, int]:
        return {dim: len(self.nc.dimensions[dim]) for dim in self.nc.dimensions}
    
    def get_variable_info(self, var_name: str) -> Dict[str, Any]:
        if var_name not in self.nc.variables:
            raise ValueError(f"Variable '{var_name}' not found")
            
        var = self.nc.variables[var_name]
        return {
            'dimensions': var.dimensions,
            'shape': var.shape,
            'dtype': var.dtype,
            'attributes': {key: getattr(var, key) for key in var.ncattrs()},
            'units': getattr(var, 'units', None),
            'long_name': getattr(var, 'long_name', None)
        }
    
    def get_variable_data(self, 
                         var_name: str, 
                         start: Optional[Union[int, List[int]]] = None,
                         count: Optional[Union[int, List[int]]] = None) -> np.ndarray:
        if var_name not in self.nc.variables:
            raise ValueError(f"Variable '{var_name}' not found")
            
        var = self.nc.variables[var_name]
        return var[start:count] if start is not None else var[:]
    
    def get_time_variable(self, time_var_name: str = 'time') -> List[datetime]:
        if time_var_name not in self.nc.variables:
            raise ValueError(f"Time variable '{time_var_name}' not found")
            
        time_var = self.nc.variables[time_var_name]
        units = getattr(time_var, 'units', '')
        
        if 'since' in units.lower():
            base_time_str = units.split('since')[1].strip()
            base_time = datetime.strptime(base_time_str, '%Y-%m-%d %H:%M:%S')
            
            time_values = time_var[:]
            return [base_time + np.timedelta64(int(t), 's') for t in time_values]
        else:
            raise ValueError(f"Unsupported time units: {units}")