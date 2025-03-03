import os
import json
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from gridUtils import constructWeatherGrid
from openweatherUtils import get_hourly_forecast, decode_hourly_forecast

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_forecast.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def ensure_directory_exists(directory):
    """Ensure the output directory exists."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def generate_filename():
    """Generate filename based on current timestamp."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def process_point(point):
    """Process a single grid point for weather forecast."""
    lon, lat = point
    try:
        openweather_json = get_hourly_forecast(lat, lon, cnt=24, units="metric")
        if openweather_json:
            forecast_data = decode_hourly_forecast(openweather_json)
            return {
                "point": (lon, lat),
                "timestamps": forecast_data["timestamps"],
                "rainfall": forecast_data["rainfall"]
            }
        return None
    except Exception as e:
        logger.error(f"Error processing point {point}: {e}")
        return None

def collect_weather_forecast():
    """Collect weather forecast data and save to JSON file."""
    try:
        # Create output directory if it doesn't exist
        output_dir = "rainfall_forecast_json"
        ensure_directory_exists(output_dir)

        # Generate filename with timestamp
        filename = f"{generate_filename()}.json"
        output_path = os.path.join(output_dir, filename)

        # Generate grid points
        nc_path = "results_3di.nc"  # Adjust path as needed
        points = constructWeatherGrid(500, nc_path)

        # Process points with progress bar
        points_data = []
        timestamps = None

        with ThreadPoolExecutor(max_workers=40) as executor:
            futures = [executor.submit(process_point, point) for point in points]
            
            for future in tqdm(
                as_completed(futures),
                total=len(points),
                desc="Processing points",
                unit="point"
            ):
                result = future.result()
                if result:
                    if timestamps is None:
                        timestamps = result["timestamps"]
                    points_data.append({
                        "point": result["point"],
                        "rainfall": result["rainfall"]
                    })

        # Prepare and save output
        output = {
            "timestamps": timestamps or [],
            "points_data": points_data
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4)

        logger.info(f"Successfully saved weather forecast data to {output_path}")

    except Exception as e:
        logger.error(f"Error in collect_weather_forecast: {e}")

def main():
    """Main function to set up and run the scheduler."""
    scheduler = BlockingScheduler()
    
    # Schedule jobs to run at 9:00, 14:00, and 18:00 every day
    scheduler.add_job(
        collect_weather_forecast,
        CronTrigger(hour='9,14,18', minute='00'),
        id='weather_forecast_job',
        name='Collect weather forecast data'
    )

    try:
        logger.info("Starting scheduler...")
        # Run the job immediately when starting
        collect_weather_forecast()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

if __name__ == "__main__":
    main() 