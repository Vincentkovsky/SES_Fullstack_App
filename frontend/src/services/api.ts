import axios, { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';

/**
 * API configuration constants
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
 * Response type interface
 */
export interface ApiResponse<T> {
  message: T;
  status?: string;
}

/**
 * Time series data point interface
 */
export interface TimeSeriesPoint {
  timestamp: string;
  waterLevel: number | null;
  flowRate: number | null;
}

/**
 * Gauging data interface
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
 * Inference settings interface
 */
export interface InferenceSettings {
  area: string;
  window: string;
}

/**
 * Inference task interface
 */
export interface InferenceTask {
  task_id: string;
  status: string;
  start_time: number;
  elapsed_time?: number;
  end_time?: number;
  parameters?: any;
  results?: any;
  results_dir?: string;
}

/**
 * Inference parameters interface
 */
export interface InferenceParams {
  model_path?: string;
  data_dir?: string;
  device?: string;
  pred_length?: number;
}

/**
 * Water depth information interface
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
 * CUDA device information interface
 */
export interface CudaDeviceInfo {
  device_id: number;
  device_name: string;
  compute_capability: string;
  total_memory_gb: number;
  reserved_memory_gb: number;
  allocated_memory_gb: number;
  free_memory_gb: number;
  reserved_percent: number;
  allocated_percent: number;
  multiprocessor_count: number;
  current_device: boolean;
}

/**
 * CUDA information response interface
 */
export interface CudaInfoResponse {
  success: boolean;
  data: {
    cuda_available: boolean;
    device_count: number;
    devices: CudaDeviceInfo[];
    current_device: number | null;
  };
}

/**
 * Rainfall file information interface
 */
export interface RainfallFileInfo {
  name: string;
  path: string;
  size_mb: number;
  last_modified: string;
}

/**
 * Rainfall files response interface
 */
export interface RainfallFilesResponse {
  success: boolean;
  data: {
    rainfall_files: RainfallFileInfo[];
    total_count: number;
    base_path: string;
  };
}

/**
 * Format date to 'dd-MMM-yyyy HH:mm' format
 * @param date Date string or Date object
 * @returns Formatted date string
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
 * Extract date and time from timestamp string
 * @param timestamp Timestamp string (format: waterdepth_yyyyMMdd_HHmm)
 * @returns Parsed date time object
 * @throws If timestamp format is invalid
 */
const parseDateFromTimestamp = (timestamp: string): Date => {
  const match = timestamp.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (!match) throw new Error('Invalid timestamp format');

  const [_, year, month, day, hour, minute] = match;
  return new Date(`${year}-${month}-${day}T${hour}:${minute}:00Z`);
};

/**
 * Generic error handling function
 * @param error Caught error
 * @param customMessage Custom error message
 * @throws Re-throws error with context
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
 * Get tiles list
 * @param isSteedMode Whether to enable Steed mode
 * @param simulation Optional simulation parameter
 * @returns Tiles list data
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
 * Get tile by coordinates
 * @param timestamp Timestamp
 * @param z Zoom level
 * @param x X coordinate
 * @param y Y coordinate
 * @param isSteedMode Whether to enable Steed mode
 * @param simulation Optional simulation parameter
 * @returns Tile data (Blob)
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
    // Prepare request parameters
    const params: Record<string, string | boolean> = { isSteedMode };
    
    // If simulation parameter is provided, add to request
    if (simulation) {
      params.simulation = simulation;
      console.log(`Using simulation parameter: ${simulation}`);
    }
    
    // If simulation parameter is provided and not null/undefined/empty string, use new route
    if (simulation && simulation.trim() !== '') {
      console.log(`Using simulation path: /tiles/simulation/${simulation}/${timestamp}/${z}/${x}/${y}`);
      const response = await axios.get(
        `${API_CONFIG.BASE_URL}/tiles/simulation/${simulation}/${timestamp}/${z}/${x}/${y}`, 
        {
          responseType: 'blob'
        }
      );
      return response.data;
    } else {
      // Otherwise use original route
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
 * Get gauging data
 * @param startDate Start date
 * @param endDate End date
 * @param frequency Data frequency, default is "Instantaneous"
 * @returns Gauging data
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
 * Get rainfall data
 * @param timestamp Timestamp
 * @returns Rainfall amount (mm/hour)
 */
export const fetchRainfallData = async (timestamp: string): Promise<number> => {
  try {
    // Get API key from environment variables
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

    return response.data.rain?.['1h'] || 0; // Return rainfall amount for the last hour (mm)
  } catch (error) {
    return handleApiError(error, 'Failed to fetch rainfall data');
  }
};

/**
 * Get historical simulation list
 * @returns Historical simulation folder names list
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
 * Get water depth information for specific location
 * @param lat Latitude
 * @param lng Longitude
 * @param timestamp Optional timestamp (format: waterdepth_yyyyMMdd_HHmmss)
 * @param simulation Optional simulation ID
 * @returns Water depth information data
 */
export const fetchWaterDepth = async (
  lat: number,
  lng: number,
  timestamp?: string,
  simulation?: string
): Promise<{ success: boolean; depth: number | null; message?: string }> => {
  try {
    if (!timestamp || !simulation) {
      throw new Error('Timestamp and simulation ID cannot be empty');
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
    console.error('Failed to get water depth:', error);
    return {
      success: false,
      depth: null,
      message: error instanceof Error ? error.message : 'Failed to get water depth'
    };
  }
};

/**
 * Get rainfall tiles list for specific simulation
 * @param simulation Simulation name
 * @returns Rainfall tiles timestamps list
 */
export const fetchRainfallTilesList = async (simulation: string): Promise<string[]> => {
  try {
    if (!simulation) {
      throw new Error('Simulation name cannot be empty');
    }
    
    const response: AxiosResponse<ApiResponse<string[]>> = await axios.get(
      `${API_CONFIG.BASE_URL}/rainfall-tiles/${simulation}`
    );
    return response.data.message || [];
  } catch (error) {
    return handleApiError(error, `Unable to get rainfall tiles list for simulation ${simulation}`);
  }
};

/**
 * Get rainfall tile by coordinates
 * @param simulation Simulation name
 * @param z Zoom level
 * @param x X coordinate
 * @param y Y coordinate
 * @returns Rainfall tile image data (Blob)
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
    return handleApiError(error, `Failed to get rainfall tile: ${simulation}/${z}/${x}/${y}`);
  }
};

/**
 * Run inference task (new API)
 * @param params Inference parameters
 * @returns Inference task information
 */
export const runInferenceTask = async (params: InferenceParams = {}): Promise<{ success: boolean; data: { task_id: string; status: string; message: string } }> => {
  try {
    const response = await axios.post(
      `${API_CONFIG.BASE_URL}/inference/run`,
      {
        model_path: params.model_path || 'best.pt',
        data_dir: params.data_dir || null,
        device: params.device || null,
        pred_length: params.pred_length || 48
      },
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    return response.data;
  } catch (error) {
    console.error('Inference task start failed:', error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};

/**
 * Get inference task status
 * @param taskId Task ID
 * @returns Task status information
 */
export const getInferenceTaskStatus = async (taskId: string): Promise<{ success: boolean; data: InferenceTask }> => {
  try {
    const response = await axios.get(`${API_CONFIG.BASE_URL}/inference/tasks/${taskId}`);
    return response.data;
  } catch (error) {
    console.error(`Failed to get task ${taskId} status:`, error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};

/**
 * Get all inference tasks list
 * @returns Tasks list
 */
export const getInferenceTasksList = async (): Promise<{ success: boolean; data: { tasks: InferenceTask[]; total: number } }> => {
  try {
    const response = await axios.get(`${API_CONFIG.BASE_URL}/inference/tasks`);
    return response.data;
  } catch (error) {
    console.error('Failed to get tasks list:', error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};

/**
 * Get inference service status
 * @returns Service status information
 */
export const getInferenceServiceStatus = async (): Promise<{ success: boolean; data: any }> => {
  try {
    const response = await axios.get(`${API_CONFIG.BASE_URL}/inference/status`);
    return response.data;
  } catch (error) {
    console.error('Failed to get inference service status:', error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};

/**
 * Get CUDA device information and utilization
 * @returns CUDA information including available devices and their utilization
 */
export const getCudaInfo = async (): Promise<CudaInfoResponse> => {
  try {
    const response = await axios.get(`${API_CONFIG.BASE_URL}/inference/cuda_info`);
    return response.data;
  } catch (error) {
    console.error('Failed to get CUDA information:', error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};


/**
 * Get available rainfall data files
 * @returns List of available rainfall data files with their information
 */
export const getRainfallFiles = async (): Promise<RainfallFilesResponse> => {
  try {
    const response = await axios.get(`${API_CONFIG.BASE_URL}/inference/rainfall_files`);
    return response.data;
  } catch (error) {
    console.error('Failed to get rainfall files:', error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};

/**
 * Cancel an inference task
 * @param taskId Task ID to cancel
 * @returns API response with success status
 */
export const cancelInferenceTask = async (taskId: string): Promise<{ success: boolean; message: string; data?: any }> => {
  try {
    const response = await axios.post(`${API_CONFIG.BASE_URL}/inference/tasks/${taskId}/cancel`);
    return response.data;
  } catch (error) {
    console.error(`Failed to cancel task ${taskId}:`, error);
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      const responseData = axiosError.response?.data as any;
      throw new Error(responseData?.detail || responseData?.message || axiosError.message);
    }
    throw error instanceof Error ? error : new Error(String(error));
  }
};
