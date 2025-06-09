import subprocess
import os
from pathlib import Path
import logging
from typing import Optional, List, Union, Dict
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class TileGeneratorConfig:
    """Configuration for tile generation."""
    zoom_levels: str = "0-14"
    processes: int = 8
    projection: str = "mercator"
    xyz_format: bool = True
    scale_params: Optional[List[float]] = None  # [min, max] for manual scaling

class TileGeneratorUtils:
    """Utility class for generating map tiles from GeoTIFF files."""
    
    def __init__(self, config: Optional[TileGeneratorConfig] = None):
        """
        Initialize TileGeneratorUtils with configuration.
        
        Args:
            config: Optional configuration object. If None, default config will be used.
        """
        self.config = config or TileGeneratorConfig()
        
    def _run_command(self, command: List[str], description: str) -> bool:
        """
        Execute a command and handle errors.
        
        Args:
            command: Command list to execute
            description: Description of the command for logging
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Running {description}: {' '.join(command)}")
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"Command output: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"{description} failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error during {description}: {str(e)}")
            return False

    def _create_temp_files(self, output_folder: Union[str, Path]) -> Dict[str, Path]:
        """Create paths for temporary files."""
        output_path = Path(output_folder)
        return {
            'vrt': output_path / "temp.vrt",
            'colored': output_path / "color_mapped.tif",
            'transparent': output_path / "transparent.tif"
        }

    def generate_tiles(
        self,
        input_file: Union[str, Path],
        color_table: Union[str, Path],
        output_folder: Union[str, Path],
        cleanup_temp: bool = True
    ) -> bool:
        """
        Generate map tiles for a given raster file with color mapping.

        Args:
            input_file: Path to the input raster file (GeoTIFF)
            color_table: Path to the color table file
            output_folder: Path to the output folder for tiles
            cleanup_temp: Whether to remove temporary files after processing

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure paths are Path objects
            input_path = Path(input_file)
            color_path = Path(color_table)
            output_path = Path(output_folder)
            
            # Validate inputs
            if not input_path.exists():
                logger.error(f"Input file not found: {input_path}")
                return False
            if not color_path.exists():
                logger.error(f"Color table not found: {color_path}")
                return False
                
            # Create output directory if it doesn't exist
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Get temporary file paths
            temp_files = self._create_temp_files(output_path)
            
            # Step 1: Convert to 8-bit
            convert_cmd = ["gdal_translate", "-of", "VRT", "-ot", "Byte"]
            if self.config.scale_params:
                convert_cmd.extend(["-scale", 
                    str(self.config.scale_params[0]),
                    str(self.config.scale_params[1]),
                    "0", "255"
                ])
            else:
                convert_cmd.append("-scale")
            convert_cmd.extend([str(input_path), str(temp_files['vrt'])])
            
            if not self._run_command(convert_cmd, "Converting to 8-bit"):
                return False

            # Step 2: Apply color mapping with alpha support
            color_cmd = [
                "gdaldem", "color-relief",
                "-alpha",  # Enable alpha channel support
                str(temp_files['vrt']),
                str(color_path),
                str(temp_files['colored'])
            ]
            if not self._run_command(color_cmd, "Applying color mapping"):
                return False

            # Step 3: Add transparency
            transparency_cmd = [
                "gdalwarp",
                "-dstalpha",
                "-srcnodata", "0",
                "-dstnodata", "0",
                str(temp_files['colored']),
                str(temp_files['transparent'])
            ]
            if not self._run_command(transparency_cmd, "Adding transparency"):
                return False

            # Step 4: Generate tiles
            tile_cmd = [
                "gdal2tiles.py",
                "-z", self.config.zoom_levels,
                "-p", self.config.projection,
                str(temp_files['transparent']),
                str(output_path)
            ]
            if self.config.xyz_format:
                tile_cmd.append("--xyz")
            tile_cmd.extend(["--processes", str(self.config.processes)])
            
            success = self._run_command(tile_cmd, "Generating tiles")

            # Cleanup temporary files if requested
            if cleanup_temp and success:
                for temp_file in temp_files.values():
                    if temp_file.exists():
                        temp_file.unlink()
                logger.info("Cleaned up temporary files")

            if success:
                logger.info(f"Tiles generated successfully in {output_path}")
            return success

        except Exception as e:
            logger.error(f"Error during tile generation: {str(e)}")
            return False

    @staticmethod
    def validate_color_table(color_table: Union[str, Path]) -> bool:
        """
        Validate the format of a color table file.
        Supports both RGB and RGBA formats.
        
        Args:
            color_table: Path to the color table file
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            with open(color_table, 'r') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines, 1):
                # Skip empty lines and comments
                if not line.strip() or line.strip().startswith('#'):
                    continue
                    
                parts = line.strip().split()
                # Allow both RGB (4 parts) and RGBA (5 parts) formats
                if len(parts) not in [4, 5]:
                    logger.error(f"Invalid color table format at line {i}: {line.strip()}")
                    logger.error("Each line should have either 4 values (value R G B) or 5 values (value R G B A)")
                    return False
                    
                # Validate value and color components
                try:
                    float(parts[0])  # Value should be a number
                    # Check RGB values
                    rgb = [int(x) for x in parts[1:4]]
                    if not all(0 <= x <= 255 for x in rgb):
                        logger.error(f"Invalid RGB values at line {i}: {line.strip()}")
                        return False
                    # Check Alpha value if present
                    if len(parts) == 5:
                        alpha = int(parts[4])
                        if not 0 <= alpha <= 255:
                            logger.error(f"Invalid Alpha value at line {i}: {line.strip()}")
                            return False
                except ValueError:
                    logger.error(f"Invalid number format at line {i}: {line.strip()}")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Error validating color table: {str(e)}")
            return False 