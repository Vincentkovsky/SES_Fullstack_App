import logging
import numpy as np
import rasterio
from pyproj import Transformer
from nc_reader import NCReader

def get_closest_node_level(file_path: str):
    try:
        with NCReader(file_path) as nc:
            node_id = nc.get_variable_data("Mesh2DNode_id")
            xcc = nc.get_variable_data("Mesh2DFace_xcc")
            ycc = nc.get_variable_data("Mesh2DFace_ycc")
            level = nc.get_variable_data("Mesh2D_s1")
            lon, lat = XYtoLonLat(xcc, ycc)

            # Coordinates of the gauge 410001
            gauge_lat = -35.10077
            gauge_lon = 147.36836

            # Calculate the distance between the gauge and each node
            distances = np.sqrt((lat - gauge_lat)**2 + (lon - gauge_lon)**2)

            # Find the index of the node with the minimum distance to the gauge
            closest_node_index = np.argmin(distances)

            # Get the node id of the closest node
            closest_node_id = node_id[closest_node_index]

            # Get the level data corresponding to the closest_node_id
            closest_node_level = level[:, closest_node_index]

            return closest_node_level

    except Exception as e:
        logging.error(f"Error processing NetCDF file: {str(e)}")
        raise

def get_dem_value(file_path: str, lat: float, lon: float) -> float:
    try:
        with rasterio.open(file_path) as dem:
            # Convert the latitude and longitude to the DEM's coordinate system
            transformer = Transformer.from_crs("EPSG:4326", dem.crs, always_xy=True)
            x, y = transformer.transform(lon, lat)
            
            # Read the DEM value at the specified coordinates
            row, col = dem.index(x, y)
            dem_value = dem.read(1)[row, col]
            
            return dem_value

    except Exception as e:
        logging.error(f"Error processing DEM file: {str(e)}")
        raise

def main():
    logging.basicConfig(level=logging.INFO)
    
    dem_path = "../SES_Fullstack_App/backend_python/data/3di_res/5m_dem.tif"
    nc_path = "../3DiSimulations/215545.nc"
    
    try:
        gauge_dem = get_dem_value(dem_path)
        level = get_closest_node_level(nc_path)

        print(f"Gauge DEM height: {gauge_dem}m")
        print(f"Closest node level: {level}m")
        
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()