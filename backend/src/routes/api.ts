import { Router } from "express";
import { getTilesList,getTileByCoordinates } from "../controllers/tilesListController";

const router = Router();

// 定义 API 路由
router.get("/tilesList", getTilesList);
router.get("/tiles/:timestamp/:z/:x/:y", getTileByCoordinates);


export default router;