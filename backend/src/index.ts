import express, { Request, Response } from "express";
import apiRoutes from "./routes/api";


const cors = require('cors');
const path = require("path");

const app = express();
const PORT = 3000;

// 配置 CORS 中间件
app.use(
  cors({
    origin: "http://localhost:5173", // 允许的前端地址
    methods: ["GET", "POST", "PUT", "DELETE"], // 允许的 HTTP 方法
    allowedHeaders: ["Content-Type", "Authorization"], // 允许的请求头
  })
);

// 中间件
app.use(express.json());

// 路由
app.use("/api", apiRoutes);

// 默认路由
app.get("/", (req: Request, res: Response) => {
  res.send("Backend is running!");
});



// 提供瓦片目录作为静态资源
app.use("/tiles", express.static(path.join(__dirname, "timeseries_tiles")));


// 启动服务器
app.listen(PORT, () => {
  console.log(`Server is running at http://localhost:${PORT}`);
});
