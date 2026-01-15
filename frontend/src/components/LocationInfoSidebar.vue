<template>
  <div class="location-sidebar" :class="{ 'open': isOpen }">
    <div class="sidebar-header">
      <h3>Location Information</h3>
      <button class="close-btn" @click="$emit('close')" aria-label="Close">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
    
    <div class="sidebar-content">
      <div class="info-section">
        <div class="info-item timestamp-item">
          <span class="info-label">Timestamp</span>
          <span class="info-value">{{ formatTimestamp(locationData.timestamp) }}</span>
        </div>
        
        <div class="info-item">
          <span class="info-label">Latitude</span>
          <span class="info-value">{{ formatCoordinate(locationData.lat, 'lat') }}</span>
        </div>
        
        <div class="info-item">
          <span class="info-label">Longitude</span>
          <span class="info-value">{{ formatCoordinate(locationData.lon, 'lon') }}</span>
        </div>
        
        <div class="info-divider"></div>
        
        <div class="info-item">
          <span class="info-label">DEM Elevation</span>
          <span class="info-value">{{ formatNumber(locationData.dem) }} m</span>
        </div>
        
        <div class="info-item">
          <span class="info-label">Water Level</span>
          <span class="info-value">{{ formatNumber(locationData.waterLevel) }} m</span>
        </div>
        
        <div class="info-item highlight">
          <span class="info-label">Water Depth</span>
          <span class="info-value">{{ formatNumber(locationData.waterDepth) }} m</span>
        </div>
        
        <div class="info-divider"></div>
        
        <div class="info-item">
          <span class="info-label">Velocity X</span>
          <span class="info-value">{{ formatNumber(locationData.velocityX) }} m/s</span>
        </div>
        
        <div class="info-item">
          <span class="info-label">Velocity Y</span>
          <span class="info-value">{{ formatNumber(locationData.velocityY) }} m/s</span>
        </div>
      </div>
      
      <div class="info-note">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
        <span>Click on map to update</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface LocationData {
  timestamp: string;
  lat: number;
  lon: number;
  dem: number;
  waterLevel: number;
  waterDepth: number;
  velocityX: number;
  velocityY: number;
}

interface Props {
  isOpen: boolean;
  locationData: LocationData;
}

const props = defineProps<Props>();

defineEmits<{
  (e: 'close'): void;
}>();

// Helper functions
const formatCoordinate = (value: number, type: 'lat' | 'lon'): string => {
  if (value === null || value === undefined) return 'N/A';
  const direction = type === 'lat' 
    ? (value >= 0 ? 'N' : 'S')
    : (value >= 0 ? 'E' : 'W');
  return `${Math.abs(value).toFixed(6)}° ${direction}`;
};

const formatNumber = (value: number): string => {
  if (value === null || value === undefined) return 'N/A';
  return value.toFixed(2);
};

const formatTimestamp = (ts: string): string => {
  if (!ts) return 'N/A';
  
  // Try to parse "waterdepth_YYYYMMDD_HHMM"
  const match = ts.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (match) {
    const [_, year, month, day, hour, minute] = match;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${day} ${months[parseInt(month)-1]} ${year} ${hour}:${minute}`;
  }
  
  // Fallback: remove prefix and return shorter string
  return ts.replace('waterdepth_', '').replace('inference_', '');
};
</script>

<style scoped>
.location-sidebar {
  position: fixed;
  top: 0;
  left: -20vw; /* Hidden to the left */
  width: 20vw;  /* Occupation of 1/5th screen width */
  height: calc(100vh - 60px); /* Leave space for bottom bar */
  background: #ffffff;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  z-index: 2000; /* Increased to overlay everything */
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e0e0e0;
  transition: left 0.3s ease-in-out;
}

.location-sidebar.open {
  left: 0;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
  font-family: 'Times New Roman', Times, serif;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.close-btn:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.close-btn svg {
  color: #666;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.timestamp-item {
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.timestamp-item .info-value {
  text-align: left;
  width: 100%;
}

.info-item:hover {
  background: #e9ecef;
}

.info-item.highlight {
  background: #e3f2fd;
  border-left: 3px solid #2196F3;
}

.info-item.highlight:hover {
  background: #bbdefb;
}

.info-label {
  font-weight: 500;
  color: #555;
  font-size: 14px;
  font-family: 'Times New Roman', Times, serif;
}

.info-value {
  font-weight: 600;
  color: #2c3e50;
  font-size: 15px;
  font-family: 'Courier New', Courier, monospace;
  text-align: right;
}

.info-divider {
  height: 1px;
  background: #e0e0e0;
  margin: 8px 0;
}

.info-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 24px;
  padding: 12px;
  background: #fff3cd;
  border-left: 3px solid #ffc107;
  border-radius: 4px;
  font-size: 13px;
  color: #856404;
  line-height: 1.5;
}

.info-note svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: #ffc107;
}

/* Scrollbar styling */
.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
