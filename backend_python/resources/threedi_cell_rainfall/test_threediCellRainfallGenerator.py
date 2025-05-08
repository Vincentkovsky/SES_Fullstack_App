import unittest
import os
from pathlib import Path
import numpy as np
from threediCellRainfallGenerator import threediCellRainfallGenerator

class TestThreediCellRainfallGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # You'll need to replace this with a valid threedi netCDF file path
        cls.test_nc_path = "../../data/3di_res/netcdf/202210080000_flow_rate_adjusted_water_level.nc"
        cls.test_output_dir = "test_output"
        
        # Create test output directory if it doesn't exist
        os.makedirs(cls.test_output_dir, exist_ok=True)
        
        # Test parameters
        cls.utm_bounds = (520700.0, 6104100.0, 560000.0, 6121550.0)
        cls.utm_zone = 55
        cls.hemisphere = 'south'

    def test_initialization(self):
        """Test the initialization of threediCellRainfallGenerator"""
        try:
            generator = threediCellRainfallGenerator(
                threedi_nc_path=self.test_nc_path,
                utm_bounds=self.utm_bounds,
                utm_zone=self.utm_zone,
                hemisphere=self.hemisphere
            )
            self.assertIsNotNone(generator)
        except Exception as e:
            self.fail(f"Initialization failed with error: {str(e)}")

    def test_invalid_hemisphere(self):
        """Test initialization with invalid hemisphere"""
        with self.assertRaises(ValueError):
            threediCellRainfallGenerator(
                threedi_nc_path=self.test_nc_path,
                utm_bounds=self.utm_bounds,
                utm_zone=self.utm_zone,
                hemisphere='invalid'
            )

    def test_invalid_utm_zone(self):
        """Test initialization with invalid UTM zone"""
        with self.assertRaises(ValueError):
            threediCellRainfallGenerator(
                threedi_nc_path=self.test_nc_path,
                utm_bounds=self.utm_bounds,
                utm_zone=61,
                hemisphere=self.hemisphere
            )

    def test_rainfall_generation(self):
        """Test the generation of rainfall data"""
        generator = threediCellRainfallGenerator(
            threedi_nc_path=self.test_nc_path,
            utm_bounds=self.utm_bounds,
            utm_zone=self.utm_zone,
            hemisphere=self.hemisphere
        )
        
        start_date = "2022-10-08"
        end_date = "2022-10-13"
        
        try:
            result = generator.generate_threedi_cell_rainfall_netcdf(
                start_date=start_date,
                end_date=end_date,
                output_dir=self.test_output_dir,
            )
            
            self.assertIn('netcdf', result)
            self.assertTrue(os.path.exists(result['netcdf']))
            
        except Exception as e:
            self.fail(f"Rainfall generation failed with error: {str(e)}")

    # @classmethod
    # def tearDownClass(cls):
    #     # Clean up test output directory
    #     if os.path.exists(cls.test_output_dir):
    #         import shutil
    #         shutil.rmtree(cls.test_output_dir)

if __name__ == '__main__':
    unittest.main() 