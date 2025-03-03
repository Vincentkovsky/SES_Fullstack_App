import requests
import numpy as np
from datetime import datetime, timedelta

API_KEY = "45b07159f9a38488403100e9f6256b67"

def get_hourly_forecast(lat, lon, api_key=API_KEY, cnt=24, units="metric", lang=None):
    """
    Fetches the hourly weather forecast for a given location.

    Parameters:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.
        api_key (str): Your OpenWeather API key.
        cnt (int): Number of timestamps to return (default 24 for 24 hours).
        units (str): Units of measurement ('standard', 'metric', 'imperial').
        lang (str, optional): Language code for the response.
    
    Returns:
        dict: The JSON response from the API.
    """
    base_url = "https://pro.openweathermap.org/data/2.5/forecast/hourly"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "cnt": cnt,
        "units": units
    }
    if lang:
        params["lang"] = lang

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def interpolate_30min_rainfall(hourly_data):
    """
    Converts hourly rainfall data to 30-minute intervals by dividing hourly values in half.
    This assumes uniform distribution of rainfall within the hour.
    
    Parameters:
        hourly_data (list): List of dictionaries containing hourly rainfall data
    
    Returns:
        tuple: (timestamps_30min, rainfall_30min) - Lists of 30-min timestamps and rainfall values
    """
    if not hourly_data or "list" not in hourly_data:
        return [], []

    timestamps = []
    rainfall = []

    # Extract hourly data
    for item in hourly_data["list"]:
        dt = datetime.fromtimestamp(item["dt"])
        rain_1h = item.get("rain", {}).get("1h", 0)
        timestamps.append(dt)
        rainfall.append(rain_1h)

    # Create 30-minute timestamps and rainfall values
    timestamps_30min = []
    rainfall_30min = []
    
    timestamps_30min.append(timestamps[0])
    rainfall_30min.append(rainfall[0]/2)

    for i in range(len(timestamps)-1):
        timestamps_30min.append(timestamps[i+1] - timedelta(minutes=30))
        rainfall_30min.append(rainfall[i+1]/2)
        timestamps_30min.append(timestamps[i+1])
        rainfall_30min.append(rainfall[i+1]/2)
    
    # Convert timestamps to string format
    timestamps_str = [ts.strftime("%Y%m%d-%H%M%S") for ts in timestamps_30min]
    
    return timestamps_str, rainfall_30min

def decode_hourly_forecast(json_data):
    """
    Decodes the JSON response from the hourly forecast API and extracts timestamps and rainfall data.
    
    Parameters:
        json_data (dict): The JSON response from the API.
    
    Returns:
        dict: A dictionary with timestamps and interpolated rainfall data.
    """
    if not json_data or "list" not in json_data:
        print("Invalid JSON data")
        return {"timestamps": [], "rainfall": []}

    timestamps, rainfall = interpolate_30min_rainfall(json_data)
    
    return {
        "timestamps": timestamps,
        "rainfall": rainfall
    }

def decode_hourly_forecast_as_array(json_data):
    """
    Decodes the JSON response from the hourly forecast API and extracts 'rain_1h' as an array.
    If 'list.rain.1h' is not present, defaults to 0.

    Parameters:
        json_data (dict): The JSON response from the API.
    
    Returns:
        list: A list of 'rain_1h' values.
    """
    if not json_data or "list" not in json_data:
        print("Invalid JSON data")
        return []

    rain_1h_values = []
    for forecast in json_data.get("list", []):
        # Handle missing "rain" key and default "1h" value to 0
        rain = forecast.get("rain", {}).get("1h", 0)
        rain_1h_values.append(rain)
    
    return rain_1h_values

def extract_dt_txt_array(json_data):
    """
    Extracts an array of 'dt_txt' values from the JSON response of the hourly forecast API.

    Parameters:
        json_data (dict): The JSON response from the API.
    
    Returns:
        list: A list of 'dt_txt' strings.
    """
    if not json_data or "list" not in json_data:
        print("Invalid JSON data")
        return []

    # Initialize an empty list for dt_txt values
    dt_txt_array = []

    # Extract dt_txt from each forecast entry
    for forecast in json_data.get("list", []):
        dt_txt = forecast.get("dt_txt", "N/A")
        dt_txt_array.append(dt_txt)

    return dt_txt_array