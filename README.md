# Flood Simulation and Prediction System

## Overview
This application is a full-stack system designed for flood prediction and visualization. It combines advanced AI models with geospatial visualization to provide flood inundation forecasting and analysis tools.

## System Architecture

### Backend Components
- **AI Inference Engine**: PyTorch-based deep learning model for flood prediction
- **FastAPI Server**: Provides REST API and WebSocket endpoints for real-time data and inference tasks
- **Data Processing Pipeline**: Processes rainfall data and generates flood inundation maps

### Frontend Components
- **Vue 3 Application**: Modern SPA built with Vue 3, TypeScript, and Vite
- **DeckGL Map Visualization**: Interactive 3D map for visualizing flood predictions
- **Real-time Interface**: WebSocket-based UI for monitoring inference progress

## Key Features

### Flood Prediction
- AI-powered prediction of water depth and flood inundation
- Support for different rainfall scenarios and historical flood events
- Hardware acceleration with CUDA GPU support

### Real-time Monitoring
- WebSocket-based real-time progress updates during inference
- Elapsed time tracking and task status monitoring
- **Task Cancellation**: Ability to cancel running inference tasks with proper process termination

### Visualization
- Interactive map with multiple layer controls
- Time series data visualization for river gauge measurements
- Rainfall visualization with legend support

## Usage Instructions

### Starting the Application
```bash
# Start the full application (backend and frontend)
./start_app.sh

# Stop the application
./stop_app.sh
```

### Running Inference
1. Open the application in a web browser
2. Click the settings button to open the inference panel
3. Select your desired parameters:
   - Area (e.g., Wagga Wagga)
   - Inference window (24, 48, or 72 hours)
   - Computing device (CPU or available CUDA GPUs)
   - Rainfall data file
4. Click "Start Inference" to begin the prediction process
5. Monitor progress through the real-time interface

### Canceling a Running Task
If you need to stop a running inference task:
1. While a task is running, the "Cancel Task" button will be available
2. Click this button to terminate the inference process
3. The system will properly terminate all associated processes
4. The UI will update to show the task has been canceled

### Viewing Historical Simulations
1. Switch to the "Historical Floods" tab in the settings panel
2. Select a historical flood event from the dropdown
3. Click "Load Simulation" to visualize the historical data

## Development

### System Requirements
- Python 3.10+
- Node.js 16+
- CUDA drivers (optional, for GPU acceleration)

### Setup for Development
```bash
# Backend setup
cd backend_python
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
```

### Running in Development Mode
```bash
# Start backend in development mode
cd backend_python
python app.py

# Start frontend in development mode
cd frontend
npm run dev
```
