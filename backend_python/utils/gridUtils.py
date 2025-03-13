import xarray as xr
import numpy as np
from pyproj import Transformer
import matplotlib.pyplot as plt
import numpy as np


# def getTopLeftCoord(nc_path):

#     coordinatesNC = nc_path
#     ds = xr.open_dataset(coordinatesNC)

#     edgex = ds['Mesh2DContour_x'].values
#     edgey = ds['Mesh2DContour_y'].values

#     x = min(edgex[0])
#     y = min(edgey[0])

#     return x,y



# get center-Coordinates of Top Left and Bottom Right Grids
def getCoordRange(nc_path):
    coordinatesNC = nc_path
    ds = xr.open_dataset(coordinatesNC)
    topLeftX = min(ds['Mesh2DFace_xcc'].values)
    topLeftY = min(ds['Mesh2DFace_ycc'].values)
    bottomRightX = max(ds['Mesh2DFace_xcc'].values)
    bottomRightY = max(ds['Mesh2DFace_ycc'].values)
    return topLeftX, topLeftY, bottomRightX, bottomRightY



def XYtoLonLat(x,y):
    transformer = Transformer.from_crs("EPSG:32755", "EPSG:4326", always_xy=True)
    lon,lat = transformer.transform(x,y)
    return lon,lat

def constructGrid(rows, cols,topleftX, topleftY, spacing):
       
    x = topleftX + np.arange(cols) * spacing
    y = topleftY + np.arange(rows) * spacing
    X, Y = np.meshgrid(x, y)
    # Save grid coordinates to a file for debugging
    return X,Y



def constructWeatherGrid(spacing, nc_path):
        # 假设 getCoordRange(nc_path) 和 spacing 已定义
    topLeftX, topLeftY, bottomRightX, bottomRightY = getCoordRange(nc_path)

    # 向外扩展范围一格实现全覆盖
    topLeftX = topLeftX - spacing
    topLeftY = topLeftY - spacing
    bottomRightX = bottomRightX + spacing
    bottomRightY = bottomRightY + spacing

    rows = int((bottomRightY - topLeftY) / spacing)
    cols = int((bottomRightX - topLeftX) / spacing)
    
    X, Y = constructGrid(rows, cols, topLeftX, topLeftY, spacing)
    points = []
    for i in range(rows):
        for j in range(cols):
            lon, lat = XYtoLonLat(X[i][j], Y[i][j])
            points.append([lon, lat])
    return points

