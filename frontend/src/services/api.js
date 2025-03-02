import axios from 'axios';

const API_BASE_URL = 'http://localhost:3000/api';

export const fetchTilesList = async (isSteedMode = false) => {
    try {
        const response = await axios.get(`${API_BASE_URL}/tilesList`, {
            params: { isSteedMode }
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching tiles list:', error);
        throw error;
    }
};

export const fetchTileByCoordinates = async (timestamp, z, x, y, isSteedMode = false) => {
    try {
        const response = await axios.get(`${API_BASE_URL}/tiles/${timestamp}/${z}/${x}/${y}`, {
            params: { isSteedMode },
            responseType: 'blob'
        });
        return response.data;
    } catch (error) {
        console.error('Error fetching tile:', error);
        throw error;
    }
};

export const runInference = async () => {
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

export const fetchGaugingData = async (startDate, endDate) => {
    const url = new URL('http://localhost:3000/api/gauging');
    
    // Format dates as dd-MMM-yyyy HH:mm
    const formatDate = (date) => {
        const d = new Date(date);
        return d.toLocaleString('en-GB', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }).replace(',', '');
    };

    url.searchParams.append('start_date', formatDate(startDate));
    url.searchParams.append('end_date', formatDate(endDate));
    url.searchParams.append('frequency', 'Instantaneous');

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

export const fetchRainfallData = async (timestamp) => {
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

