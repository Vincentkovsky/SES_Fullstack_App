import { Request, Response } from "express";
import fs from "fs";
import path from "path";

// 获取 timeseries_tiles 文件夹下的所有子文件夹名
export const getTilesList = (req: Request, res: Response): void => {
  const tilesPath = path.join(__dirname, "../timeseries_tiles");
  
  try {
    const directories = fs.readdirSync(tilesPath, { withFileTypes: true })
      .filter(dirent => dirent.isDirectory())
      .map(dirent => dirent.name);

    res.status(200).json({ message: directories });
  } catch (error) {
    console.error("Error reading tiles directory:", error);
    res.status(500).json({ error: "Unable to retrieve tiles list" });
  }
};




export const getTileByCoordinates = (req: Request, res: Response): void => {
  const {timestamp, z, x, y } = req.params; // Extract coordinates from the request parameters
  const tilePath = path.join(__dirname, `../timeseries_tiles/${timestamp}/${z}/${x}/${y}.png`);

  console.log("Backend API hit");


  try {
    if (fs.existsSync(tilePath)) {
      // Serve the tile file if it exists
      console.log("Tile found");
      res.status(200).sendFile(tilePath);
    } else {
      // Respond with a 404 if the tile doesn't exist
      res.status(404).json({ error: "Tile not found" });
    }
  } catch (error) {
    // Handle unexpected errors
    console.error("Error retrieving tile:", error);
    res.status(500).json({ error: "Unable to retrieve tile" });
  }
};

