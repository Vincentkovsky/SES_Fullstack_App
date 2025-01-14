import requests
API_KEY = "45b07159f9a38488403100e9f6256b67"



def get_hourly_forecast(lat, lon, api_key=API_KEY, cnt=None, units=None, lang=None):
    """
    Fetches the hourly weather forecast for a given location.

    Parameters:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.
        api_key (str): Your OpenWeather API key.
        cnt (int, optional): Number of timestamps to return. Default is None (returns all).
        units (str, optional): Units of measurement ('standard', 'metric', 'imperial'). Default is 'standard'.
        lang (str, optional): Language code for the response. Default is None (English).
    
    Returns:
        dict: The JSON response from the API.
    """
    base_url = "https://pro.openweathermap.org/data/2.5/forecast/hourly"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
    }
    if cnt:
        params["cnt"] = cnt
    if units:
        params["units"] = units
    if lang:
        params["lang"] = lang

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def decode_hourly_forecast(json_data):
    """
    Decodes the JSON response from the hourly forecast API and extracts 'dt_txt' and 'list.rain.1h'.
    If 'list.rain.1h' is not present, defaults to 0.

    Parameters:
        json_data (dict): The JSON response from the API.
    
    Returns:
        list: A list of dictionaries with 'dt_txt' and 'rain_1h'.
    """
    if not json_data or "list" not in json_data:
        print("Invalid JSON data")
        return []

    result = []
    for forecast in json_data.get("list", []):
        dt_txt = forecast.get("dt_txt", "N/A")
        # Handle missing "rain" key and default "1h" value to 0
        rain = forecast.get("rain", {}).get("1h", 0)
        result.append({"dt_txt": dt_txt, "rain_1h": rain})
    
    return result


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