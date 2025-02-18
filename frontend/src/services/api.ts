export const fetchTilesList = async (): Promise<{ message: string[] }> => {
    const response = await fetch("http://localhost:3000/api/tilesList");
    return response.json();
};

export const runInference = async (): Promise<{ message: string }> => {
    const response = await fetch('http://localhost:3000/api/run-inference', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Inference failed');
    }

    return response.json();
};

export const fetchTileByCoordinates = async (
    timestamp: string,
    z: number,
    x: number,
    y: number
  ): Promise<Blob> => {
    const url = `http://localhost:3000/api/tiles/${timestamp}/${z}/${x}/${y}`; // Replace with your API URL
  
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch tile: ${response.statusText}`);
      }
      return await response.blob(); // Return the tile as a Blob
    } catch (error) {
      console.error("Error fetching tile:", error);
      throw error; // Rethrow the error for handling by the caller
    }
  };

export interface GaugingData {
  site_id: string;
  timeseries: Array<{
    timestamp: string;
    maxDepth: number;
  }>;
  total_records: number;
}

export const fetchGaugingData = async (startDate: string): Promise<GaugingData> => {
  const url = new URL('http://localhost:3000/api/gauging');
  url.searchParams.append('start_date', startDate);

  const response = await fetch(url.toString());
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'Failed to fetch gauging data');
  }

  return response.json();
};

const OPENWEATHERMAP_API_KEY = 'YOUR_API_KEY'; // Replace with your API key
const WAGGA_COORDINATES = {
  lat: -35.117,
  lon: 147.356
};

export const fetchRainfallData = async (timestamp: string): Promise<number> => {
  const match = timestamp.match(/waterdepth_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/);
  if (!match) throw new Error('Invalid timestamp format');

  const [_, year, month, day, hour] = match;
  const dt = Math.floor(new Date(`${year}-${month}-${day}T${hour}:00:00Z`).getTime() / 1000);

  const url = new URL('https://api.openweathermap.org/data/2.5/weather/history');
  url.searchParams.append('lat', WAGGA_COORDINATES.lat.toString());
  url.searchParams.append('lon', WAGGA_COORDINATES.lon.toString());
  url.searchParams.append('dt', dt.toString());
  url.searchParams.append('appid', OPENWEATHERMAP_API_KEY);

  const response = await fetch(url.toString());
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'Failed to fetch rainfall data');
  }

  const data = await response.json();
  return data.rain?.['1h'] || 0; // Returns rainfall in mm for the last hour
};