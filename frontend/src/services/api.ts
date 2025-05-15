import axios, { AxiosError, AxiosResponse } from 'axios';

/**
 * API配置常量
 */
const API_CONFIG = {
  BASE_URL: `http://${import.meta.env.VITE_HOST || 'localhost'}:${import.meta.env.VITE_BACKEND_PORT || 3000}/api`,
  WEATHER_BASE_URL: 'https://api.openweathermap.org/data/2.5',
  WAGGA_COORDINATES: {
    lat: -35.117,
    lon: 147.356
  }
};

/**
 * 响应类型接口
 */
export interface ApiResponse<T> {
  message: T;
  status?: string;
}

/**
 * 时间序列数据点接口
 */
export interface TimeSeriesPoint {
  timestamp: string;
  waterLevel: number | null;
  flowRate: number | null;
}

/**
 * 测量数据接口
 */
export interface GaugingData {
  data_count: number;
  data_source: {
    file_path: string;
    timestamp: string;
    type: string;
  };
  site_info: {
    site_id: string;
    site_name: string;
    variable: string;
  };
  timestamps: string[];
  values: number[];
}

/**
 * 推断设置接口
 */
export interface InferenceSettings {
  area: string;
  window: string;
}

/**
 * 水深信息接口
 */
export interface WaterDepthInfo {
  latitude: number;
  longitude: number;
  dem_elevation: number;
  water_level: number;
  water_depth: number;
  simulation: string;
  timestamp: string;
}

/**
 * 格式化日期为 'dd-MMM-yyyy HH:mm' 格式
 * @param date 日期字符串或Date对象
 * @returns 格式化后的日期字符串
 */
const formatDateForApi = (date: string | Date): string => {
  const d = date instanceof Date ? date : new Date(date);
  const day = d.getDate().toString().padStart(2, '0');
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = monthNames[d.getMonth()];
  const year = d.getFullYear();
  const hours = d.getHours().toString().padStart(2, '0');
  const minutes = d.getMinutes().toString().padStart(2, '0');
  
  return `${day}-${month}-${year} ${hours}:${minutes}`;
};

/**
 * 从时间戳字符串中提取日期时间
 * @param timestamp 时间戳字符串 (格式: waterdepth_yyyyMMdd_HHmm)
 * @returns 解析的日期时间对象
 * @throws 如果时间戳格式无效
 */
const parseDateFromTimestamp = (timestamp: string): Date => {
  const match = timestamp.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (!match) throw new Error('Invalid timestamp format');

  const [_, year, month, day, hour, minute] = match;
  return new Date(`${year}-${month}-${day}T${hour}:${minute}:00Z`);
};

/**
 * 通用错误处理函数
 * @param error 捕获的错误
 * @param customMessage 自定义错误消息
 * @throws 重新抛出带有上下文的错误
 */
const handleApiError = (error: unknown, customMessage: string): never => {
  console.error(`${customMessage}:`, error);
  
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    const responseData = axiosError.response?.data as any;
    throw new Error(responseData?.error || responseData?.message || axiosError.message);
  }
  
  throw error instanceof Error ? error : new Error(String(error));
};

/**
 * 获取图块列表
 * @param isSteedMode 是否启用Steed模式
 * @param simulation 可选的模拟参数
 * @returns 图块列表数据
 */
export const fetchTilesList = async (isSteedMode: boolean = false, simulation?: string): Promise<ApiResponse<string[]>> => {
  try {
    const params = new URLSearchParams();
    if (isSteedMode) {
      params.append('isSteedMode', 'true');
    }
    if (simulation) {
      params.append('simulation', simulation);
    }

    const response: AxiosResponse<ApiResponse<string[]>> = await axios.get(
      `${API_CONFIG.BASE_URL}/tilesList${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Error fetching tiles list');
  }
};

/**
 * 运行推断
 * @param settings 可选的推断设置
 * @returns 推断结果消息
 */
export const runInference = async (settings?: InferenceSettings): Promise<ApiResponse<string>> => {
  try {
    const response: AxiosResponse<ApiResponse<string>> = await axios.post(
      `${API_CONFIG.BASE_URL}/run-inference`,
      settings || {},
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Inference failed');
  }
};

/**
 * 按坐标获取瓦片
 * @param timestamp 时间戳
 * @param z 缩放级别
 * @param x X坐标
 * @param y Y坐标
 * @param isSteedMode 是否启用Steed模式
 * @param simulation 可选的模拟参数
 * @returns 瓦片数据（Blob）
 */
export const fetchTileByCoordinates = async (
  timestamp: string, 
  z: string | number, 
  x: string | number, 
  y: string | number, 
  isSteedMode: boolean = false,
  simulation?: string
): Promise<Blob> => {
  try {
    // 准备请求参数
    const params: Record<string, string | boolean> = { isSteedMode };
    
    // 如果提供了simulation参数，添加到请求中
    if (simulation) {
      params.simulation = simulation;
      console.log(`使用simulation参数: ${simulation}`);
    }
    
    // 如果有simulation参数且不为null/undefined/空字符串，使用新的路由
    if (simulation && simulation.trim() !== '') {
      console.log(`使用simulation路径: /tiles/simulation/${simulation}/${timestamp}/${z}/${x}/${y}`);
      const response = await axios.get(
        `${API_CONFIG.BASE_URL}/tiles/simulation/${simulation}/${timestamp}/${z}/${x}/${y}`, 
        {
          responseType: 'blob'
        }
      );
      return response.data;
    } else {
      // 否则使用原始路由
      const response = await axios.get(
        `${API_CONFIG.BASE_URL}/tiles/${timestamp}/${z}/${x}/${y}`, 
        {
          params,
          responseType: 'blob'
        }
      );
      return response.data;
    }
  } catch (error) {
    return handleApiError(error, 'Error fetching tile');
  }
};

/**
 * 获取测量数据
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @param frequency 数据频率，默认为"Instantaneous"
 * @returns 测量数据
 */
export const fetchGaugingData = async (
  startDate: string | Date, 
  endDate: string | Date,
  frequency: string = 'Instantaneous'
): Promise<GaugingData> => {
  try {
    const params = new URLSearchParams({
      start_date: formatDateForApi(startDate),
      end_date: formatDateForApi(endDate),
      frequency
    });

    const response = await axios.get<GaugingData>(
      `${API_CONFIG.BASE_URL}/gauging?${params.toString()}`
    );
    
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch gauging data');
  }
};

/**
 * 获取降雨数据
 * @param timestamp 时间戳
 * @returns 降雨量（毫米/小时）
 */
export const fetchRainfallData = async (timestamp: string): Promise<number> => {
  try {
    // 获取环境变量中的API密钥
    const apiKey = import.meta.env.VITE_SHARED_OPENWEATHERMAP_API_KEY;
    if (!apiKey) {
      throw new Error('OpenWeatherMap API key is missing');
    }

    const date = parseDateFromTimestamp(timestamp);
    const dt = Math.floor(date.getTime() / 1000);

    const params = new URLSearchParams({
      lat: API_CONFIG.WAGGA_COORDINATES.lat.toString(),
      lon: API_CONFIG.WAGGA_COORDINATES.lon.toString(),
      dt: dt.toString(),
      appid: apiKey
    });

    const response = await axios.get(
      `${API_CONFIG.WEATHER_BASE_URL}/weather/history?${params.toString()}`
    );

    return response.data.rain?.['1h'] || 0; // 返回最近一小时的降雨量（毫米）
  } catch (error) {
    return handleApiError(error, 'Failed to fetch rainfall data');
  }
};

/**
 * 获取历史模拟列表
 * @returns 历史模拟文件夹名称列表
 */
export const fetchHistoricalSimulations = async (): Promise<string[]> => {
  try {
    const response: AxiosResponse<ApiResponse<string[]>> = await axios.get(
      `${API_CONFIG.BASE_URL}/simulations`
    );
    return response.data.message || [];
  } catch (error) {
    return handleApiError(error, 'Error fetching historical simulations');
  }
};

/**
 * 获取指定位置的水深信息
 * @param lat 纬度
 * @param lng 经度
 * @param timestamp 可选的时间戳 (格式: waterdepth_yyyyMMdd_HHmmss)
 * @param simulation 可选的模拟ID
 * @returns 水深信息数据
 */
export const fetchWaterDepth = async (
  lat: number,
  lng: number,
  timestamp?: string,
  simulation?: string
): Promise<{ success: boolean; depth: number | null; message?: string }> => {
  try {
    if (!timestamp || !simulation) {
      throw new Error('时间戳和模拟ID不能为空');
    }

    const params = new URLSearchParams({
      lat: lat.toString(),
      lng: lng.toString(),
      simulation,
      timestamp
    });
    
    const response = await axios.get(
      `${API_CONFIG.BASE_URL}/water-depth?${params.toString()}`
    );
    
    return response.data;
  } catch (error) {
    console.error('获取水深度失败:', error);
    return {
      success: false,
      depth: null,
      message: error instanceof Error ? error.message : '获取水深失败'
    };
  }
};

/**
 * 获取特定模拟的降雨瓦片时间戳列表
 * @param simulation 模拟名称
 * @returns 降雨瓦片时间戳列表
 */
export const fetchRainfallTilesList = async (simulation: string): Promise<string[]> => {
  try {
    if (!simulation) {
      throw new Error('模拟名称不能为空');
    }
    
    const response: AxiosResponse<ApiResponse<string[]>> = await axios.get(
      `${API_CONFIG.BASE_URL}/rainfall-tiles/${simulation}`
    );
    return response.data.message || [];
  } catch (error) {
    return handleApiError(error, `无法获取模拟 ${simulation} 的降雨瓦片列表`);
  }
};

/**
 * 根据坐标获取降雨瓦片
 * @param simulation 模拟名称
 * @param z 缩放级别
 * @param x X坐标
 * @param y Y坐标
 * @returns 降雨瓦片图像数据（Blob）
 */
export const fetchRainfallTile = async (
  simulation: string,
  z: string | number,
  x: string | number,
  y: string | number
): Promise<Blob> => {
  try {
    const response = await axios.get(
      `${API_CONFIG.BASE_URL}/rainfall-tiles/${simulation}/${z}/${x}/${y}`,
      {
        responseType: 'blob'
      }
    );
    
    return response.data;
  } catch (error) {
    return handleApiError(error, `无法获取降雨瓦片: ${simulation}/${z}/${x}/${y}`);
  }
};
