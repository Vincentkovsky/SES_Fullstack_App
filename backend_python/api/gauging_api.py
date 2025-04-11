from flask import Blueprint, request, jsonify
from http import HTTPStatus
import logging
import csv
import os
import datetime
from marshmallow import Schema, fields, ValidationError
from utils.helpers import handle_exceptions, get_timestamp

logger = logging.getLogger(__name__)

# 创建蓝图
gauging_bp = Blueprint('gauging', __name__)

# CSV文件路径
GAUGE_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'gauge_data', '410001_river_level.csv')

# 数据验证模式
class SurfaceWaterRequestSchema(Schema):
    """验证地表水API请求参数的模式"""
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    site_id = fields.String(required=False, default="410001")

def read_csv_data():
    """
    从CSV文件读取河流水位数据
    
    返回:
        包含所有数据的列表，每一项是一个字典
    """
    data = []
    try:
        # 检查文件是否存在
        if not os.path.exists(GAUGE_DATA_PATH):
            logger.error(f"CSV文件不存在: {GAUGE_DATA_PATH}")
            raise FileNotFoundError(f"CSV文件不存在: {GAUGE_DATA_PATH}")
        
        # 打印文件信息以便调试
        file_size = os.path.getsize(GAUGE_DATA_PATH)
        logger.info(f"CSV文件大小: {file_size} 字节")
        
        with open(GAUGE_DATA_PATH, 'r', encoding='utf-8') as csvfile:
            # 使用csv模块处理带引号的CSV文件
            csv_reader = csv.reader(csvfile, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, skipinitialspace=True)
            
            # 读取标题行
            try:
                headers = next(csv_reader)
                
                # 记录原始标题，用于调试
                logger.info(f"CSV原始标题: {headers}")
                
                # 确保所需列存在
                if not headers or len(headers) < 2:
                    raise ValueError(f"CSV标题不完整: {headers}")
                
                # 默认列名，用于处理不同的表头格式
                date_column = "Date"
                level_column = "River Level"
                quality_column = "Quality code"
                desc_column = "Quality code description"
                
                # 查找正确的列索引
                date_index = None
                level_index = None
                quality_index = None
                desc_index = None
                
                # 遍历查找匹配的列名（不区分大小写）
                for i, col in enumerate(headers):
                    col_lower = col.lower()
                    if 'date' in col_lower:
                        date_index = i
                    elif 'level' in col_lower or 'depth' in col_lower:
                        level_index = i
                    elif 'quality code' in col_lower:
                        quality_index = i
                    elif 'description' in col_lower:
                        desc_index = i
                
                # 如果没找到关键列，抛出错误
                if date_index is None:
                    raise ValueError(f"未找到日期列。可用列: {headers}")
                if level_index is None:
                    raise ValueError(f"未找到水位列。可用列: {headers}")
                
                logger.info(f"使用列索引: 日期={date_index}, 水位={level_index}, 质量码={quality_index}, 描述={desc_index}")
                
                # 读取数据行
                row_count = 0
                for row in csv_reader:
                    row_count += 1
                    
                    # 跳过空行或格式不正确的行
                    if not row or len(row) <= date_index or len(row) <= level_index:
                        logger.warning(f"跳过无效行 #{row_count}: {row}")
                        continue
                    
                    try:
                        # 创建数据字典
                        item = {
                            'timestamp': row[date_index].strip(),
                            'river_level': float(row[level_index].strip()),
                        }
                        
                        # 添加可选字段（如果存在）
                        if quality_index is not None and len(row) > quality_index:
                            item['quality_code'] = row[quality_index].strip()
                        
                        if desc_index is not None and len(row) > desc_index:
                            item['quality_description'] = row[desc_index].strip()
                        
                        data.append(item)
                    except ValueError as e:
                        # 处理不能转换为浮点数的情况
                        logger.warning(f"行 #{row_count} 数据格式错误: {e} - {row}")
                        continue
                
                logger.info(f"成功读取了 {len(data)}/{row_count} 条记录")
                
            except StopIteration:
                logger.error("CSV文件为空或格式错误")
                raise ValueError("CSV文件为空或格式错误")
            
        if not data:
            logger.warning("没有从CSV文件中读取到任何有效数据")
        
        return data
        
    except Exception as e:
        logger.error(f"读取CSV文件时出错: {str(e)}")
        raise

def filter_data_by_date_range(data, start_date_str, end_date_str):
    """
    根据日期范围过滤数据
    
    参数:
        data: 完整数据列表
        start_date_str: 开始日期字符串 (dd-MMM-yyyy HH:mm)
        end_date_str: 结束日期字符串 (dd-MMM-yyyy HH:mm)
        
    返回:
        过滤后的数据列表
    """
    try:
        # 将输入日期从"dd-MMM-yyyy HH:mm"格式转换为datetime对象
        # 例如: "15-Mar-2023 10:30" -> datetime
        start_date = datetime.datetime.strptime(start_date_str, "%d-%b-%Y %H:%M")
        end_date = datetime.datetime.strptime(end_date_str, "%d-%b-%Y %H:%M")
        
        filtered_data = []
        for item in data:
            try:
                # CSV中的日期格式是"2015-03-14 09:00"，需要转换为datetime对象
                item_date = datetime.datetime.strptime(item['timestamp'], "%Y-%m-%d %H:%M")
                if start_date <= item_date <= end_date:
                    filtered_data.append(item)
            except ValueError as e:
                # 跳过日期格式无效的记录
                logger.warning(f"跳过日期格式无效的记录: {item['timestamp']} - {str(e)}")
                continue
        
        logger.info(f"日期过滤后剩余 {len(filtered_data)} 条记录")
        return filtered_data
        
    except Exception as e:
        logger.error(f"过滤日期时出错: {str(e)}")
        raise

def process_water_data(data):
    """
    处理水位数据以返回前端所需的格式
    
    参数:
        data: 过滤后的数据列表
        
    返回:
        处理后的数据字典
    """
    timestamps = []
    values = []
    
    for item in data:
        try:
            # 将"2015-03-14 09:00"格式转换为"14-Mar-2015 09:00"格式
            date_obj = datetime.datetime.strptime(item['timestamp'], "%Y-%m-%d %H:%M")
            formatted_date = date_obj.strftime("%d-%b-%Y %H:%M")
            
            timestamps.append(formatted_date)
            values.append(item['river_level'])
        except (ValueError, KeyError) as e:
            # 跳过格式无效的记录
            logger.warning(f"处理数据时跳过无效记录: {str(e)}")
            continue
    
    return {
        'timestamps': timestamps,
        'values': values,
        'site_info': {
            'site_id': '410001',
            'site_name': 'Wagga Wagga',
            'variable': 'StreamWaterLevel'
        },
        'data_count': len(timestamps)
    }

@gauging_bp.route('/api/gauging', methods=['GET'])
@handle_exceptions
def get_gauging_data():
    """
    获取地表水数据并返回时间序列
    
    查询参数:
    - start_date: 字符串 (必需) - 开始日期，格式为dd-MMM-yyyy HH:mm
    - end_date: 字符串 (必需) - 结束日期，格式为dd-MMM-yyyy HH:mm
    
    返回:
        包含时间序列数据的JSON响应
    """
    # 获取查询参数
    try:
        schema = SurfaceWaterRequestSchema()
        params = schema.load({
            'start_date': request.args.get('start_date'),
            'end_date': request.args.get('end_date'),
            'site_id': '410001'  # Wagga Wagga的固定站点ID
        })
        
        logger.info(f"接收到参数: start_date={params['start_date']}, end_date={params['end_date']}")
        
        # 从CSV文件读取所有数据
        all_data = read_csv_data()
        
        # 根据日期范围过滤数据
        filtered_data = filter_data_by_date_range(
            all_data, 
            params['start_date'], 
            params['end_date']
        )
        
        # 处理并返回数据
        response_data = process_water_data(filtered_data)
        
        # 添加数据来源信息
        response_data['data_source'] = {
            'type': 'local_file',
            'file_path': os.path.basename(GAUGE_DATA_PATH),
            'timestamp': get_timestamp()
        }
        
        return jsonify(response_data), HTTPStatus.OK
    
    except ValidationError as e:
        logger.error(f"参数验证错误: {str(e)}")
        return jsonify({
            'error': '参数验证错误',
            'details': str(e)
        }), HTTPStatus.BAD_REQUEST
        
    except Exception as e:
        logger.error(f"处理河流水位数据时出错: {str(e)}")
        return jsonify({
            'error': '处理河流水位数据时出错',
            'details': str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR

@gauging_bp.route('/api/test-gauge-data', methods=['GET'])
@handle_exceptions
def test_gauge_data():
    """测试本地CSV数据读取"""
    try:
        # 读取CSV数据
        all_data = read_csv_data()
        
        # 获取数据的时间范围
        date_range = {"min": None, "max": None}
        if all_data:
            try:
                dates = [datetime.datetime.strptime(item['timestamp'], "%Y-%m-%d %H:%M") for item in all_data]
                date_range = {
                    "min": min(dates).strftime("%d-%b-%Y %H:%M"),
                    "max": max(dates).strftime("%d-%b-%Y %H:%M")
                }
            except Exception as e:
                date_range = {"error": str(e)}
        
        # 尝试进行简单的日期过滤测试
        test_results = {}
        if all_data and date_range["min"] and date_range["max"]:
            try:
                # 使用CSV中的最早和最晚日期作为测试范围
                filtered_data = filter_data_by_date_range(
                    all_data,
                    date_range["min"],
                    date_range["max"]
                )
                test_results = {
                    "filter_test": "成功",
                    "filtered_count": len(filtered_data),
                    "sample": filtered_data[:3] if filtered_data else []
                }
            except Exception as e:
                test_results = {
                    "filter_test": "失败",
                    "error": str(e)
                }
        
        # 构建诊断信息
        diagnostic = {
            "file_exists": os.path.exists(GAUGE_DATA_PATH),
            "file_size": os.path.getsize(GAUGE_DATA_PATH) if os.path.exists(GAUGE_DATA_PATH) else 0,
            "file_path": GAUGE_DATA_PATH,
            "record_count": len(all_data),
            "date_range": date_range,
            "test_results": test_results
        }
        
        # 准备示例数据
        sample_data = all_data[:5] if len(all_data) > 5 else all_data
        
        return jsonify({
            "message": "成功读取本地CSV数据" if all_data else "读取CSV数据，但未获取到有效记录",
            "timestamp": get_timestamp(),
            "data_count": len(all_data),
            "sample_data": sample_data,
            "diagnostic": diagnostic
        }), HTTPStatus.OK
    
    except Exception as e:
        logger.error(f"测试CSV数据读取时出错: {str(e)}")
        return jsonify({
            "message": "读取CSV数据失败",
            "error": str(e),
            "timestamp": get_timestamp(),
            "file_path": GAUGE_DATA_PATH,
            "diagnostic": {
                "file_exists": os.path.exists(GAUGE_DATA_PATH),
                "file_size": os.path.getsize(GAUGE_DATA_PATH) if os.path.exists(GAUGE_DATA_PATH) else 0,
                "exception_type": type(e).__name__
            }
        }), HTTPStatus.INTERNAL_SERVER_ERROR 