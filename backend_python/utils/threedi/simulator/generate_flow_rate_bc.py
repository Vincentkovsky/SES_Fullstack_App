import os
import pandas as pd
import json
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 创建discharge文件夹（如果不存在）
os.makedirs('boundary_condition/discharge', exist_ok=True)

# 测量站ID到边界条件ID的映射
STATION_TO_BC_ID = {
    '410001': 2,  # 410001 对应 id 为 2
    '410047': 3,  # 410047 对应 id 为 3
    '410143': 1   # 410143 对应 id 为 1
}

# 单位转换: ML/Day 转换为 m³/s
# 1 ML/Day = 1000 m³/Day = 1000/86400 m³/s = 0.01157 m³/s
ML_DAY_TO_M3_S = 0.01157

def validate_flow_rate(flow_rate, station_id):
    """验证流量值的有效性"""
    if pd.isna(flow_rate):
        raise ValueError(f"Station {station_id} has NaN flow rate value")
    if flow_rate < 0:
        logging.warning(f"Station {station_id} has negative flow rate: {flow_rate}")
    return flow_rate

def load_flow_rate_data(station_id):
    """加载指定测量站的流量数据"""
    file_path = f"boundary_condition/gauge_data/{station_id}_flow_rate.csv"
    
    try:
        if not os.path.exists(file_path):
            logging.warning(f"警告: 测量站 {station_id} 的流量数据文件不存在")
            return None
        
        df = pd.read_csv(file_path)
        # 转换日期列为datetime对象
        df['Date'] = pd.to_datetime(df['Date'])
        # 将数据按照日期排序
        df = df.sort_values('Date')
        # 设置Date为索引
        df.set_index('Date', inplace=True)
        
        # 验证数据
        df['Flow Rate'] = df['Flow Rate'].apply(lambda x: validate_flow_rate(x, station_id))
        
        return df
    except Exception as e:
        logging.error(f"加载测量站 {station_id} 数据时出错: {str(e)}")
        return None

def interpolate_time_series(df, start_time, end_time, freq='h'):
    """对时间序列进行插值"""
    if df is None or df.empty:
        return None
        
    # 创建完整的时间索引
    full_index = pd.date_range(start=start_time, end=end_time, freq=freq)
    
    # 重新索引
    df = df.reindex(full_index)
    
    # 推断对象类型并转换为适当的数据类型
    df = df.infer_objects()
    
    # 对于开始的 NaN 值，使用第一个有效值填充
    first_valid_value = df['Flow Rate'].first_valid_index()
    if first_valid_value is not None:
        df.loc[:first_valid_value, 'Flow Rate'] = df.loc[first_valid_value, 'Flow Rate']
    
    # 对于结尾的 NaN 值，使用最后一个有效值填充
    last_valid_value = df['Flow Rate'].last_valid_index()
    if last_valid_value is not None:
        df.loc[last_valid_value:, 'Flow Rate'] = df.loc[last_valid_value, 'Flow Rate']
    
    # 进行线性插值填充中间的 NaN 值
    df = df.interpolate(method='linear')
    
    return df

def get_netcdf_time_ranges():
    """获取所有历史降雨NetCDF文件的时间范围"""
    time_ranges = []
    nc_dir = "historical_netcdf_converted"
    
    try:
        if not os.path.exists(nc_dir):
            raise FileNotFoundError(f"Directory {nc_dir} not found")
            
        for file_name in os.listdir(nc_dir):
            if not file_name.endswith('.nc'):
                continue
                
            # 从文件名提取时间信息 (格式: rainfall_YYYYMMDDHHMM_YYYYMMDDHHMM.nc)
            try:
                parts = file_name.split("_")
                if len(parts) != 3:
                    logging.warning(f"Invalid filename format: {file_name}")
                    continue
                    
                start_str = parts[1]
                end_str = parts[2].split(".")[0]  # 移除 .nc 扩展名
                
                # 解析时间
                start_datetime = datetime.strptime(start_str, '%Y%m%d%H%M')
                end_datetime = datetime.strptime(end_str, '%Y%m%d%H%M')
                
                time_ranges.append({
                    'file_name': file_name.replace('.nc', ''),
                    'start_time': start_datetime,
                    'end_time': end_datetime
                })
            except ValueError as e:
                logging.error(f"Error parsing datetime from filename {file_name}: {str(e)}")
                continue
                
        return time_ranges
    except Exception as e:
        logging.error(f"Error getting NetCDF time ranges: {str(e)}")
        return []

def filter_gauge_data(gauge_df, start_time, end_time):
    """根据指定的时间范围筛选测量站数据"""
    if gauge_df is None:
        return None
    
    try:
        # 确保开始和结束时间是datetime对象
        start_time = pd.to_datetime(start_time)
        end_time = pd.to_datetime(end_time)
        
        # 筛选数据
        filtered_df = gauge_df[start_time:end_time]
        
        return filtered_df
    except Exception as e:
        logging.error(f"Error filtering gauge data: {str(e)}")
        return None

def create_flow_rate_boundary_json(time_range, station_ids=STATION_TO_BC_ID.keys()):
    """为指定的时间范围和测量站创建流量边界条件JSON"""
    try:
        start_time = time_range['start_time']
        end_time = time_range['end_time']
        file_name = time_range['file_name']
        
        # 创建边界条件数组
        boundary_conditions = []
        
        # 加载所有测量站数据
        station_data = {}
        for station_id in station_ids:
            df = load_flow_rate_data(station_id)
            if df is not None:
                station_data[station_id] = df
        
        # 如果410143没有数据，但410001和410047都有数据，使用它们的差值
        if '410143' not in station_data and '410001' in station_data and '410047' in station_data:
            logging.info("测量站 410143 没有数据，使用 410001 - 410047 的数据替代")
            
            # 计算差值
            df_410143 = station_data['410001'].copy()
            df_410143['Flow Rate'] = station_data['410001']['Flow Rate'] - station_data['410047']['Flow Rate']
            station_data['410143'] = df_410143
        
        # 处理每个测量站
        for station_id in station_ids:
            bc_id = STATION_TO_BC_ID[station_id]
            
            if station_id not in station_data:
                logging.warning(f"警告: 测量站 {station_id} 没有数据，跳过")
                continue
            
            gauge_df = station_data[station_id]
            
            # 筛选时间范围内的数据
            filtered_df = filter_gauge_data(gauge_df, start_time, end_time)
            
            if filtered_df is None or filtered_df.empty:
                logging.warning(f"警告: 测量站 {station_id} 在时间范围内没有有效数据")
                continue
            
            # 准备流量值
            values = []
            
            # 获取第一个数据点的值，用于0时刻
            first_value = filtered_df.iloc[0]['Flow Rate']
            first_time = filtered_df.index[0]
            first_seconds = int((first_time - start_time).total_seconds())
            
            # 如果第一个数据点不是在0秒，添加0秒的值
            if first_seconds > 0:
                flow_rate_zero = float(first_value) * ML_DAY_TO_M3_S
                flow_rate_zero = -abs(flow_rate_zero)
                values.append([0, flow_rate_zero])
            
            # 遍历数据点
            for timestamp, row in filtered_df.iterrows():
                # 计算相对开始时间的秒数
                seconds = int((timestamp - start_time).total_seconds())
                
                # 单位转换：从 ML/Day 到 m³/s
                flow_rate = float(row['Flow Rate']) * ML_DAY_TO_M3_S
                
                # 确保流量为负值（表示流出）
                flow_rate = -abs(flow_rate)
                
                values.append([seconds, flow_rate])
            
            # 确保有至少两个值
            if len(values) < 2:
                logging.warning(f"测量站 {station_id} 数据点不足，使用默认值")
                end_seconds = int((end_time - start_time).total_seconds())
                values = [[0, -1.0], [end_seconds, -1.0]]
            
            # 添加边界条件
            boundary_condition = {
                "id": bc_id,
                "type": "2D",
                "interpolate": True,
                "values": values
            }
            
            boundary_conditions.append(boundary_condition)
        
        # 保存到JSON文件
        output_dir = "boundary_condition/discharge"
        output_path = os.path.join(output_dir, f"flow_rate_{file_name}.json")
        
        with open(output_path, 'w') as f:
            json.dump(boundary_conditions, f, indent=4)
        
        logging.info(f"已创建流量边界条件文件: {output_path}")
        return output_path
        
    except Exception as e:
        logging.error(f"Error creating flow rate boundary JSON: {str(e)}")
        return None

def main():
    try:
        # 获取所有NetCDF文件的时间范围
        time_ranges = get_netcdf_time_ranges()
        
        if not time_ranges:
            logging.error("没有找到历史降雨NetCDF文件")
            return
        
        # 为每个时间范围创建边界条件
        output_files = []
        for time_range in time_ranges:
            logging.info(f"处理时间范围: {time_range['start_time']} 到 {time_range['end_time']}")
            output_file = create_flow_rate_boundary_json(time_range)
            if output_file:
                output_files.append(output_file)
        
        return output_files
        
    except Exception as e:
        logging.error(f"Error in main function: {str(e)}")
        return None

if __name__ == "__main__":
    main() 