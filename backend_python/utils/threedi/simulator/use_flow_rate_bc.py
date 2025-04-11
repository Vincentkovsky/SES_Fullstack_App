from typing import List, Optional, Union, Dict, Any
import os
from datetime import datetime
from pathlib import Path
from threedi_api_client.openapi.exceptions import ApiException
import time
import json
import pandas as pd
import numpy as np
import rasterio
from rasterio.transform import from_origin
import logging
from pyproj import Transformer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 定义测量站的位置 (WGS84 - EPSG:4326)
GAUGE_STATIONS = {
    '410001': {
        'lat': -35.10077,  # WGS84纬度
        'lon': 147.36836,  # WGS84经度
        'name': 'Wagga Wagga',
        'dem_height': 171.14801  # 测量站位置的DEM高程，单位：米
    }
}

# 定义坐标转换器 - 从WGS84(EPSG:4326)到UTM zone 55S(EPSG:32755)
wgs84_to_utm55s = Transformer.from_crs("EPSG:4326", "EPSG:32755", always_xy=True)

# 将WGS84坐标转换为UTM坐标
def convert_coords_to_utm(lon, lat):
    """将WGS84经纬度坐标转换为UTM坐标"""
    x, y = wgs84_to_utm55s.transform(lon, lat)
    return x, y

# 更新GAUGE_STATIONS添加UTM坐标
for station_id, info in GAUGE_STATIONS.items():
    utm_x, utm_y = convert_coords_to_utm(info['lon'], info['lat'])
    GAUGE_STATIONS[station_id]['utm_x'] = utm_x
    GAUGE_STATIONS[station_id]['utm_y'] = utm_y
    logging.info(f"测量站 {station_id} ({info['name']}) 坐标转换: WGS84({info['lon']}, {info['lat']}) -> UTM55S({utm_x}, {utm_y})")

# 导入BatchSimulator类
import importlib
simulator_module = importlib.import_module("3di_simulator")
BatchSimulator = simulator_module.BatchSimulator

def load_river_level_data(station_id):
    """加载河流水位数据"""
    file_path = f"boundary_condition/gauge_data/{station_id}_river_level.csv"
    
    try:
        if not os.path.exists(file_path):
            logging.warning(f"警告: 测量站 {station_id} 的水位数据文件不存在")
            return None
        
        # 首先检查文件内容
        with open(file_path, 'r') as f:
            first_line = f.readline().strip()
            second_line = f.readline().strip() if f.readline() else ""
        
        # 根据文件格式确定如何加载
        if '"' in first_line:  # 引号分隔格式如 "2022-10-08 09:00","5.857","7",""
            # 检查是否有标题行
            if 'River Level' in first_line or 'Date' in first_line:
                # 跳过标题行
                df = pd.read_csv(file_path, header=0, skiprows=1, names=['Date', 'Level', 'Quality', 'Extra'])
            else:
                # 无标题行
                df = pd.read_csv(file_path, header=None, names=['Date', 'Level', 'Quality', 'Extra'])
                
            # 清理引号
            df['Date'] = df['Date'].str.replace('"', '')
            df['Level'] = df['Level'].str.replace('"', '').astype(float)
        else:  # 假设标准CSV格式
            # 检查是否有标题行
            if ',' in first_line and not first_line.startswith('"20'):
                # 有标题行，使用标准读取
                df = pd.read_csv(file_path)
            else:
                # 无标题行，指定列名
                df = pd.read_csv(file_path, header=None, names=['Date', 'Level', 'Quality', 'Extra'])
                
        # 转换日期列为datetime对象
        df['Date'] = pd.to_datetime(df['Date'])
        
        # 排序并设置为索引
        df = df.sort_values('Date')
        df.set_index('Date', inplace=True)
        
        # 验证是否读取了正确的数据
        if df.empty:
            logging.warning(f"测量站 {station_id} 的水位数据为空")
            return None
            
        # 打印前几行数据用于验证
        logging.info(f"成功加载测量站 {station_id} 的水位数据，前2行：\n{df.head(2)}")
        
        return df
    except Exception as e:
        logging.error(f"加载测量站 {station_id} 水位数据时出错: {str(e)}")
        # 尝试更基础的读取方式
        try:
            logging.info("尝试使用更基础的方式读取CSV...")
            # 读取所有行
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # 跳过第一行（标题行）
            data = []
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.replace('"', '').split(',')
                if len(parts) >= 2:
                    try:
                        date_str = parts[0]
                        level_str = parts[1]
                        date = pd.to_datetime(date_str)
                        level = float(level_str)
                        data.append((date, level))
                    except:
                        continue
            
            if not data:
                logging.error("无法解析有效数据")
                return None
                
            # 创建DataFrame
            df = pd.DataFrame(data, columns=['Date', 'Level'])
            df.set_index('Date', inplace=True)
            df = df.sort_index()
            
            logging.info(f"使用基础方式成功加载数据，前2行：\n{df.head(2)}")
            return df
        except Exception as nested_e:
            logging.error(f"基础读取方式也失败: {str(nested_e)}")
            return None

def adjust_initial_water_level(simulation_start_time, original_tif_path="HIGH_WATER_LEVEL"):
    """
    根据河流水位观测数据调整初始水位
    
    Args:
        simulation_start_time: 模拟开始时间
        original_tif_path: 原始水位TIF文件路径或名称
    
    Returns:
        调整后的TIF文件路径
    """
    try:
        # 1. 加载测量站水位数据
        station_id = '410001'  # Wagga Wagga站
        river_level_df = load_river_level_data(station_id)
        
        if river_level_df is None:
            logging.warning("无法加载河流水位数据，将使用原始水位")
            return original_tif_path
            
        # 2. 获取模拟开始时间最接近的水位值（注意：CSV中为水深值）
        closest_date = river_level_df.index[river_level_df.index.get_indexer([simulation_start_time], method='nearest')[0]]
        observed_depth = river_level_df.loc[closest_date, 'Level']
        
        # 获取测量站DEM高程
        station_dem_height = GAUGE_STATIONS[station_id]['dem_height']
        
        # 计算绝对水位 = DEM高程 + 水深
        observed_absolute_level = station_dem_height + observed_depth
        
        logging.info(f"模拟开始时间: {simulation_start_time}, 最接近的观测日期: {closest_date}")
        logging.info(f"观测水深: {observed_depth}m, DEM高程: {station_dem_height}m, 绝对水位: {observed_absolute_level}m")
        
        # 生成输出文件名，极简化格式以符合API的60字符限制
        # 使用简短的日期格式和舍入的水位值
        date_str = simulation_start_time.strftime('%y%m%d')  # 只使用年月日，不包含小时分钟
        level_rounded = int(observed_absolute_level)  # 舍入到整数
        output_filename = f"wl_{date_str}_{level_rounded}.tif"
        
        # 确保目录存在 - 使用initial_water_level文件夹
        output_dir = Path("initial_water_level")
        output_dir.mkdir(exist_ok=True)
        
        # 创建完整的输出路径 - 使用绝对路径
        output_path = output_dir / output_filename
        output_path_abs = output_path.absolute()
        
        logging.info(f"将创建调整后的水位文件: {output_path_abs}")
        
        # 如果文件已存在，直接返回
        if output_path.exists():
            logging.info(f"调整后的水位文件已存在: {output_path_abs}")
            return str(output_path)  # 注意这里返回的是相对路径
        
        # 3. 检查TIF文件情况
        # 尝试在常见位置查找文件
        possible_paths = [
            original_tif_path,
            f"{original_tif_path}.tif",
            os.path.join("initial_water_level", f"{original_tif_path}.tif")
        ]
        
        tif_file_exists = False
        full_tif_path = None
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                full_tif_path = path
                tif_file_exists = True
                logging.info(f"找到TIF文件: {full_tif_path}")
                break
                
        # 如果找不到物理TIF文件，返回预定义名称供BatchSimulator使用
        # 并记录下无法进行基于观测的调整
        if not tif_file_exists:
            logging.warning(f"无法找到TIF文件 '{original_tif_path}'，无法根据观测水位调整，将使用原始水位。")
            logging.warning(f"实际模拟中将使用BatchSimulator的预定义水位: {original_tif_path}")
            logging.warning(f"为使脚本能够调整水位，请确保TIF文件存在或修改代码以适应当前环境。")
            logging.warning(f"实际使用的绝对水位是: {observed_absolute_level}m (水深: {observed_depth}m + DEM高程: {station_dem_height}m)")
            
            # 记录预期的调整系数
            # 假设预定义光栅中站点位置的水位为近似值
            # 这里需要使用绝对水位值而非水深值进行比较
            assumed_tif_level = station_dem_height + 5.0  # 假设的平均水深为5.0m
            adjustment_factor = observed_absolute_level / assumed_tif_level
            logging.info(f"估计水位调整: 假设TIF站点绝对水位={assumed_tif_level}m, 观测绝对水位={observed_absolute_level}m, 估计调整系数={adjustment_factor:.4f}")
            
            # 在返回原始光栅名称前，记录观测水位信息
            # 创建一个JSON文件保存调整信息，供后续使用
            adjustment_info = {
                "simulation_start_time": simulation_start_time.isoformat(),
                "observed_date": closest_date.isoformat(),
                "observed_depth": float(observed_depth),
                "dem_height": float(station_dem_height),
                "observed_absolute_level": float(observed_absolute_level),
                "assumed_tif_level": float(assumed_tif_level),
                "estimated_adjustment_factor": float(adjustment_factor)
            }
            
            # 保存调整信息
            info_dir = Path("adjustment_info")
            info_dir.mkdir(exist_ok=True)
            info_path = info_dir / f"water_level_info_{date_str}.json"
            
            with open(info_path, 'w') as f:
                json.dump(adjustment_info, f, indent=4)
                
            logging.info(f"已保存水位调整信息到: {info_path}")
            
            # 返回原始光栅名称
            return original_tif_path
            
        # 4. 根据观测水位创建调整后的TIF文件
        with rasterio.open(full_tif_path) as src:
            # 读取原始数据
            data = src.read(1)
            
            # 验证栅格坐标系
            raster_crs = src.crs
            logging.info(f"栅格坐标系: {raster_crs}")
            
            # 获取观测站的UTM坐标
            station_info = GAUGE_STATIONS[station_id]
            station_utm_x = station_info['utm_x']
            station_utm_y = station_info['utm_y']
            
            # 使用UTM坐标找到观测站位置在栅格中的像素索引
            # 需要从栅格坐标系转换到像素坐标
            px, py = src.index(station_utm_x, station_utm_y)
            
            logging.info(f"观测站 {station_id} 在栅格中的位置: 行={py}, 列={px}")
            
            # 获取栅格中观测站位置的当前水位（这是绝对水位值）
            try:
                tif_level_at_station = data[px, py]
            except IndexError:
                # 如果坐标转换导致像素索引超出栅格范围，尝试找到最近的有效像素
                logging.warning(f"观测站位置 (行={py}, 列={px}) 超出栅格范围，尝试查找最近的有效像素")
                # 限制在栅格范围内
                py = max(0, min(py, data.shape[0] - 1))
                px = max(0, min(px, data.shape[1] - 1))
                tif_level_at_station = data[py, px]
                logging.info(f"使用临近像素 (行={py}, 列={px}) 的绝对水位值: {tif_level_at_station}")
            
            if tif_level_at_station <= 0:
                logging.warning(f"TIF中站点位置的绝对水位为 {tif_level_at_station}，尝试查找附近的非零水位...")
                
                # 在3x3区域内查找非零水位
                search_radius = 3
                non_zero_levels = []
                
                for i in range(max(0, py-search_radius), min(data.shape[0], py+search_radius+1)):
                    for j in range(max(0, px-search_radius), min(data.shape[1], px+search_radius+1)):
                        if data[i, j] > 0:
                            non_zero_levels.append(data[i, j])
                
                if non_zero_levels:
                    tif_level_at_station = np.mean(non_zero_levels)
                    logging.info(f"使用附近{len(non_zero_levels)}个非零绝对水位的平均值: {tif_level_at_station}")
                else:
                    # 如果无法从TIF文件获取水位，使用DEM高程加上默认水深
                    logging.warning(f"附近区域没有找到非零水位，将使用DEM高程加上默认水深值")
                    tif_level_at_station = station_dem_height + 5.0  # DEM高程 + 默认水深5.0m
            
            # 计算调整系数 - 使用绝对水位进行比较
            adjustment_factor = observed_absolute_level / tif_level_at_station
            
            # 调整整个光栅
            # 只对大于0的水位值进行调整（保留干燥区域）
            mask = data > 0
            adjusted_data = data.copy()
            adjusted_data[mask] = data[mask] * adjustment_factor
            
            logging.info(f"水位调整: TIF站点绝对水位={tif_level_at_station}, 观测绝对水位={observed_absolute_level}, 调整系数={adjustment_factor:.4f}")
            
            # 创建新的TIF文件，保持原始元数据
            profile = src.profile
            with rasterio.open(str(output_path_abs), 'w', **profile) as dst:
                dst.write(adjusted_data, 1)
                
        logging.info(f"已创建调整后的水位文件: {output_path_abs}")
        # 返回文件名，不包括路径 - 这是BatchSimulator期望的格式
        output_filename_only = output_filename.replace(".tif", "")
        logging.info(f"返回文件名 (不含扩展名): {output_filename_only}")
        return output_filename_only
        
    except Exception as e:
        logging.error(f"调整初始水位时出错: {str(e)}")
        logging.error(f"将使用原始水位: {original_tif_path}")
        return original_tif_path

def run_simulations_with_flow_rate():
    """使用流量边界条件运行模拟"""
    # 初始化模拟器
    simulator = BatchSimulator()
    
    # 加载任何现有进度
    progress = simulator.load_progress()
    
    # 获取模型和组织
    model = simulator.fetch_model("wagga_res_5m")
    org_id = simulator.fetch_org_id("Academic License")
    
    # 获取所有nc文件
    nc_files = [f for f in os.listdir("historical_netcdf_converted") if f.endswith(".nc")]
    
    # 处理每个nc文件
    for nc_file in nc_files:
        # 从文件名提取时间信息 (格式: rainfall_YYYYMMDDHHMM_YYYYMMDDHHMM.nc)
        date_parts = nc_file.split("_")
        start_date_str = date_parts[1]
        end_date_str = date_parts[2].split(".")[0]  # 移除 .nc 扩展名
        
        # 解析开始时间
        start_year = int(start_date_str[:4])
        start_month = int(start_date_str[4:6])
        start_day = int(start_date_str[6:8])
        start_hour = int(start_date_str[8:10])
        start_minute = int(start_date_str[10:12])
        start_time = datetime(start_year, start_month, start_day, start_hour, start_minute)
        
        # 解析结束时间
        end_year = int(end_date_str[:4])
        end_month = int(end_date_str[4:6])
        end_day = int(end_date_str[6:8])
        end_hour = int(end_date_str[8:10])
        end_minute = int(end_date_str[10:12])
        end_time = datetime(end_year, end_month, end_day, end_hour, end_minute)
        
        # 计算持续时间（秒）
        duration = int((end_time - start_time).total_seconds())
        
        # 添加24小时缓冲以确保完整覆盖
        duration += 24 * 3600
        
        # 创建模拟名称
        simulation_name = f"historical_rainfall_{start_date_str}_flow_rate_adjusted_water_level"
        
        # 检查模拟是否已存在
        if simulator.search_simulation(simulation_name, ["historical", "flow_rate", "adjusted_water_level"]):
            print(f"模拟 {simulation_name} 已存在，跳过...")
            continue
        
        print(f"为 {nc_file} 创建使用流量边界条件和观测调整水位的模拟...")
        print(f"持续时间: {duration/3600:.1f} 小时 ({duration/86400:.1f} 天)")
        
        # 根据观测水位调整初始水位
        adjusted_water_level_result = adjust_initial_water_level(start_time, "HIGH_WATER_LEVEL")
        
        # 创建模拟，开始时间与nc文件匹配
        simulation = simulator.create_simulation(
            model=model,
            org_id=org_id,
            name=simulation_name,
            tags=["historical", "flow_rate", "adjusted_water_level"],
            starttime=start_time,
            duration=duration
        )
        
        # 添加降雨数据
        nc_file_path = os.path.join("historical_netcdf_converted", nc_file)
        simulator.create_nc_rainfall_event(
            simulation=simulation,
            file_path=nc_file_path
        )
        
        # 上传并添加调整后的初始水位
        if adjusted_water_level_result == "HIGH_WATER_LEVEL":
            # 如果使用预定义光栅
            logging.info(f"使用默认的HIGH_WATER_LEVEL光栅")
            raster = simulator.upload_initial_raster(model, adjusted_water_level_result)
        else:
            # 如果使用自定义调整光栅
            logging.info(f"上传自定义调整水位光栅: {adjusted_water_level_result}")
            
            try:
                # 上传自定义光栅，使用名称调用upload_initial_raster
                raster = simulator.upload_initial_raster(model, adjusted_water_level_result)
                logging.info(f"成功上传调整后的水位光栅，栅格ID: {raster.id}")
            except Exception as e:
                logging.error(f"上传调整后的水位光栅时出错: {str(e)}")
                logging.warning(f"将使用默认水位 'HIGH_WATER_LEVEL'")
                raster = simulator.upload_initial_raster(model, "HIGH_WATER_LEVEL")
            
        processed_initial_water_level = simulator.check_raster_processing(raster, model)
        simulator.update_initial_water_level(simulation, processed_initial_water_level)
        
        # 添加流量边界条件
        # 使用对应的流量文件名
        flow_rate_file = f"flow_rate_{nc_file.replace('.nc', '')}"
        simulator.create_boundary_conditions(
            simulation=simulation,
            file_name=flow_rate_file,
            boundary_type='discharge'
        )
        
        # 启动模拟
        simulator.start_simulation(simulation)
        
        # 保存进度
        progress[simulation_name] = {
            "status": "started",
            "id": simulation.id,
            "nc_file": nc_file,
            "boundary_type": "discharge",
            "boundary_condition": "flow_rate",
            "initial_water_level": "adjusted_based_on_observation",
            "adjusted_water_level_path": adjusted_water_level_result,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_hours": duration/3600
        }
        simulator.save_progress(progress)
        
        # 避免触发速率限制，等待一段时间
        time.sleep(5)
    
    print("所有使用流量边界条件和观测调整水位的历史降雨模拟已创建并启动。")

if __name__ == "__main__":
    # 首先运行脚本生成流量边界条件
    print("生成流量边界条件文件...")
    import generate_flow_rate_bc
    generate_flow_rate_bc.main()
    
    # 然后使用生成的流量边界条件运行模拟
    print("\n启动使用流量边界条件和观测调整水位的模拟...")
    run_simulations_with_flow_rate() 