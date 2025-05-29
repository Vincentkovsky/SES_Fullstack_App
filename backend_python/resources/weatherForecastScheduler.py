import os
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import pathlib

from ..utils.gridUtils import constructWeatherGrid
from ..utils.openweatherUtils import get_hourly_forecast, decode_hourly_forecast

# Get the current file's directory
CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
LOG_FILE = CURRENT_DIR / 'weather_forecast.log'
NC_FILE = CURRENT_DIR / 'results_3di.nc'
OUTPUT_DIR = "/projects/TCCTVS/FSI/cnnModel/rainfall_forecast_json"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
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
    """Generate filename based on next hour timestamp."""
    current = datetime.now()
    # Round up to next hour
    next_hour = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return next_hour.strftime("%Y%m%d-%H%M%S")

def process_point(point):
    """Process a single grid point for weather forecast."""
    lon, lat = point
    try:
        openweather_json = get_hourly_forecast(lat, lon, cnt=25, units="metric")
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
        ensure_directory_exists(OUTPUT_DIR)

        # Generate filename with timestamp
        filename = f"{generate_filename()}.json"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # Generate grid points
        points = constructWeatherGrid(500, NC_FILE)

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
        CronTrigger(hour='8,13,17', minute='58'),
        id='weather_forecast_job',
        name='Collect weather forecast data'
    )

    try:
        logger.info("Starting scheduler...")
        logger.info(f'scheduler: {scheduler.print_jobs()}')
        # Run the job immediately when starting
        collect_weather_forecast()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

if __name__ == "__main__":
    main() 