import requests
import numpy as np
from datetime import datetime, timedelta

API_KEY = "be0569ae40c2cb69050a4ada307cb497"

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

    for i in range(len(timestamps)-2):
        timestamps_30min.append(timestamps[i+1] - timedelta(minutes=30))
        rainfall_30min.append(rainfall[i+1]/2)
        timestamps_30min.append(timestamps[i+1])
        rainfall_30min.append(rainfall[i+1]/2)

    timestamps_30min.append(timestamps[-1] - timedelta(minutes=30))
    rainfall_30min.append(rainfall[-1]/2)
    
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

def get_historical_weather(lat: float, lon: float, start: int = None, end: int = None, cnt: int = None, units: str = "metric", api_key: str = API_KEY) -> dict:
    """
    Fetches historical weather data for a given location.

    Parameters:
        lat (float): Latitude of the location
        lon (float): Longitude of the location
        start (int, optional): Start date (Unix timestamp, UTC)
        end (int, optional): End date (Unix timestamp, UTC)
        cnt (int, optional): Number of timestamps (one per hour, alternative to end)
        units (str, optional): Units of measurement ('standard', 'metric', 'imperial')
        api_key (str, optional): Your OpenWeather API key
    
    Returns:
        dict: The JSON response from the API containing historical weather data
    
    Example:
        >>> start_time = int(datetime(2024, 3, 1).timestamp())
        >>> end_time = int(datetime(2024, 3, 2).timestamp())
        >>> data = get_historical_weather(lat=-35.1082, lon=147.3598, 
        ...                              start=start_time, end=end_time)
    """
    # Construct URL in exact sequence as specified in the documentation
    url = (
        f"https://history.openweathermap.org/data/2.5/history/city"
        f"?lat={lat}"
        f"&lon={lon}"
        f"&type=hour"
    )

    # Add optional parameters in sequence
    if start is not None:
        url += f"&start={start}"
    if end is not None:
        url += f"&end={end}"
    elif cnt is not None:
        url += f"&cnt={cnt}"
    
    # Add API key and units
    url += f"&appid={api_key}"
    if units:
        url += f"&units={units}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching historical weather data: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return None

def decode_historical_weather(json_data: dict) -> dict:
    """
    Decodes the JSON response from the historical weather API.
    
    Parameters:
        json_data (dict): The JSON response from the API
    
    Returns:
        dict: Decoded weather data with the following structure:
            {
                'timestamps': list of datetime strings,
                'temperature': list of temperatures in specified units,
                'rainfall_1h': list of 1-hour rainfall values in mm,
                'rainfall_3h': list of 3-hour rainfall values in mm,
                'humidity': list of humidity values in %,
                'pressure': list of pressure values in hPa,
                'wind_speed': list of wind speeds in specified units,
                'wind_direction': list of wind directions in degrees
            }
    """
    if not json_data or "list" not in json_data:
        print("Invalid JSON data")
        return {
            'timestamps': [],
            'temperature': [],
            'rainfall_1h': [],
            'rainfall_3h': [],
            'humidity': [],
            'pressure': [],
            'wind_speed': [],
            'wind_direction': []
        }

    result = {
        'timestamps': [],
        'temperature': [],
        'rainfall_1h': [],
        'rainfall_3h': [],
        'humidity': [],
        'pressure': [],
        'wind_speed': [],
        'wind_direction': []
    }

    for item in json_data['list']:
        # Convert timestamp to datetime string
        dt = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d %H:%M:%S')
        result['timestamps'].append(dt)
        
        # Extract main weather parameters
        main = item.get('main', {})
        result['temperature'].append(main.get('temp'))
        result['humidity'].append(main.get('humidity'))
        result['pressure'].append(main.get('pressure'))
        
        # Extract wind data
        wind = item.get('wind', {})
        result['wind_speed'].append(wind.get('speed'))
        result['wind_direction'].append(wind.get('deg'))
        
        # Extract rainfall data
        rain = item.get('rain', {})
        result['rainfall_1h'].append(rain.get('1h', 0))
        result['rainfall_3h'].append(rain.get('3h', 0))

    return result

def get_historical_archive_openmeteo(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    hourly_params: list = ["temperature_2m"]
) -> dict:
    """
    Fetches historical archive data from Open-Meteo Archive API.

    Parameters:
        latitude (float): Latitude of the location
        longitude (float): Longitude of the location
        start_date (str): Start date in YYYY-MM-DD or YYYYMMDD_HHMMSS format
        end_date (str): End date in YYYY-MM-DD or YYYYMMDD_HHMMSS format
        hourly_params (list): List of hourly parameters to fetch (default: ["temperature_2m"])
                            Available parameters: temperature_2m, relative_humidity_2m,
                            dew_point_2m, apparent_temperature, precipitation,
                            rain, snowfall, cloud_cover, pressure_msl,
                            surface_pressure, wind_speed_10m, wind_direction_10m,
                            wind_gusts_10m
    
    Returns:
        dict: The JSON response from the API containing historical archive data
    
    Example:
        >>> data = get_historical_archive_openmeteo(
        ...     latitude=-35.1082,
        ...     longitude=147.3598,
        ...     start_date="20221101_000000",
        ...     end_date="20221106_000000",
        ...     hourly_params=["temperature_2m", "rain", "wind_speed_10m"]
        ... )
    """
    base_url = "https://archive-api.open-meteo.com/v1/archive"
    
    # Convert date format if needed
    def format_date(date_str: str) -> str:
        if '_' in date_str:
            # Convert from YYYYMMDD_HHMMSS to YYYY-MM-DD
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    
    start_date_formatted = format_date(start_date)
    end_date_formatted = format_date(end_date)
    
    # Construct hourly parameters string
    hourly_str = ",".join(hourly_params)
    
    # Build parameters dictionary
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date_formatted,
        "end_date": end_date_formatted,
        "hourly": hourly_str
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching historical archive data: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return None

def decode_historical_archive_openmeteo(json_data: dict) -> dict:
    """
    Decodes the JSON response from the Open-Meteo Archive API.
    
    Parameters:
        json_data (dict): The JSON response from the API
    
    Returns:
        dict: Decoded weather data with the following structure:
            {
                'timestamps': list of datetime strings,
                'temperature_2m': list of temperature values in °C,
                ... (other parameters as requested in the API call)
            }
            
    Additional information:
        - Temperature is in °C
        - Wind speed is in km/h
        - Precipitation/Rain is in mm
        - Pressure is in hPa
        - Cloud cover is in %
        - Humidity is in %
    """
    if not json_data or "hourly" not in json_data:
        print("Invalid JSON data")
        return {
            'timestamps': [],
            'temperature_2m': []
        }

    result = {}
    
    # Extract metadata
    result['metadata'] = {
        'latitude': json_data.get('latitude'),
        'longitude': json_data.get('longitude'),
        'timezone': json_data.get('timezone'),
        'elevation': json_data.get('elevation'),
        'units': json_data.get('hourly_units', {})
    }
    
    # Extract hourly data
    hourly_data = json_data['hourly']
    
    # Convert timestamps to datetime strings
    result['timestamps'] = hourly_data.get('time', [])
    
    # Extract all available hourly parameters
    for key in hourly_data.keys():
        if key != 'time':  # Skip the time key as it's already processed
            result[key] = hourly_data.get(key, [])
    
    return result