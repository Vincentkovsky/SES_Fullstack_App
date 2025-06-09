# Flood Simulation and Prediction System - Technical Report

## 1. System Overview

This system is a full-stack flood prediction and visualization platform that combines advanced artificial intelligence models with geospatial visualization technology to provide flood inundation forecasting and analysis tools. The system can generate flood inundation maps based on rainfall data and supports real-time monitoring and historical data analysis.

## 2. Technical Architecture

### 2.1 Frontend Technology Stack

- **Framework**: Vue 3 (Vue 3.5.12)
- **Development Language**: TypeScript
- **Build Tool**: Vite (5.4.10)
- **Map Visualization**: 
  - Mapbox GL (3.8.0)
  - Deck.gl (9.0.36) - High-performance WebGL map visualization library
  - @deck.gl/geo-layers, @deck.gl/layers, @deck.gl/mapbox, @deck.gl/core
- **Chart Visualization**: 
  - Chart.js (4.4.7)
  - Vue-ChartJS (5.3.2)
- **HTTP Client**: Axios (1.8.1)
- **Animation**: 
  - TWEEN.js (25.0.0)
  - Popmotion (11.0.5)
- **UI Components**: shadcn-vue (0.11.3)

### 2.2 Backend Technology Stack

- **Web Framework**: FastAPI (0.110.0)
- **ASGI Server**: Uvicorn (0.27.1)
- **Data Processing**: 
  - NumPy (1.26.4)
  - Rasterio (1.3.9) - For processing geospatial raster data
  - PyProj (3.6.1) - Coordinate system conversion
- **Real-time Communication**: WebSockets (12.0)
- **AI Inference Engine**: 
  - PyTorch (version not specified) - For deep learning models
  - CUDA support - For GPU acceleration
- **Image Processing**: Pillow (10.4.0)
- **Configuration Management**: python-dotenv (1.0.1)
- **Data Validation**: Pydantic (2.6.4)
- **Serialization**: Marshmallow (3.21.0)

### 2.3 System Architecture

#### Frontend Architecture
- Single Page Application (SPA) based on Vue 3
- Component-based structure with core components including:
  - DeckGLMap.vue - Main map visualization component
  - SettingsModal.vue - Configuration and control panel
  - RiverGaugeChart.vue - River gauging station data visualization
  - RainfallMap.vue - Rainfall data visualization
- Uses TypeScript strong type definitions to ensure code quality and maintainability
- Uses API service layer to communicate with the backend

#### Backend Architecture
- RESTful API service based on FastAPI
- Modular design with core modules including:
  - API routes (water_depth_router, inference_router, etc.)
  - Inference service (InferenceService)
  - Data processing modules
- Supports WebSocket real-time communication
- Asynchronous processing to improve concurrency

## 3. Core Features

### 3.1 Flood Prediction

- **AI Inference Engine**: PyTorch-based deep learning model that supports prediction of water depth and flood inundation area
- **Prediction Parameters**: 
  - Supports different areas (e.g., Wagga Wagga)
  - Optional prediction time windows (24 hours, 48 hours, 72 hours)
  - Supports selection of computing device (CPU or CUDA GPU)
  - Optional rainfall data file selection
- **GPU Acceleration**: Supports CUDA GPU acceleration for the inference process

### 3.2 Real-time Monitoring

- **WebSocket Communication**: Provides real-time updates of inference task progress
- **Task Management**: Supports starting, monitoring, and canceling inference tasks
- **Status Tracking**: Displays task status, time elapsed, and result information

### 3.3 Geospatial Visualization

- **Interactive Map**: 
  - High-performance map rendering based on Mapbox GL and Deck.gl
  - Supports map zooming, panning, and layer control
  - Supports switching between satellite imagery and standard maps
- **Multi-layer Control**: 
  - Flood layer - Displays flood inundation areas
  - Rainfall layer - Displays rainfall distribution
- **Time Series Animation**: 
  - Supports playing flood inundation process by time sequence
  - Adjustable playback speed (1x, 2x, 3x)
  - Progress bar and timestamp display
- **Data Query**: Supports clicking on the map to get water depth information at specific locations

### 3.4 Data Visualization

- **River Gauging Station Charts**: Displays time series data of river water levels and flow rates
- **Rainfall Data Charts**: Displays rainfall data changing over time
- **Legend**: Provides color legends for flood depth and rainfall amount

### 3.5 Historical Data Analysis

- **Historical Flood Events**: Supports loading and visualizing historical flood event data
- **Simulation Data Comparison**: Allows comparison of flood simulation results from different time periods

## 4. Technical Highlights

1. **High-performance Visualization**:
   - Uses WebGL technology (Deck.gl) to efficiently render large-scale geographic data
   - Supports layered loading and processing of raster data

2. **AI Model and Spatial Data Integration**:
   - Seamlessly integrates deep learning models with geospatial data
   - Supports flexible inference on various computing devices (CPU/GPU)

3. **Real-time Communication and Monitoring**:
   - Uses WebSocket technology to implement real-time updates of backend task progress
   - Supports task cancellation and resource release

4. **Multi-modal Data Integration**:
   - Integrates rainfall data, water depth data, and terrain data
   - Supports unified visualization of different data sources

5. **Responsive Design**:
   - Uses Vue 3's Composition API and reactive system
   - Optimized user interface and interaction experience

## 5. System Extensibility

The system design has good extensibility:

1. **Modular Architecture**: Both frontend and backend adopt modular design, facilitating feature expansion
2. **Flexible Data Processing Pipeline**: Supports adding new data sources and processing modules
3. **Pluggable AI Models**: Supports replacing or upgrading AI inference models
4. **Multi-device Support**: Flexibly adapts to different computing environments (CPU/GPU)

## 6. Deployment and Operation

The system provides simple startup and shutdown scripts:
- `start_app.sh`: Starts the complete application (frontend and backend)
- `stop_app.sh`: Stops the application and releases resources

System requirements:
- Python 3.10+
- Node.js 16+
- CUDA drivers (optional, for GPU acceleration)

## 7. Conclusion

This Flood Simulation and Prediction System is a full-stack application that combines advanced AI technology with geospatial visualization. It provides powerful flood prediction capabilities, real-time monitoring functions, and an interactive visualization interface that can be used for flood risk assessment, emergency response planning, and decision support. The system is built with a modern technology stack and features high performance, scalability, and user-friendliness. 