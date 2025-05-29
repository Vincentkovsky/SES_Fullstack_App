# NetCDF 批量转换工具使用说明

这个文档介绍如何使用 `convert_nc_to_tiles.py` 脚本将 NetCDF 文件批量转换为 GeoTIFF 文件和地图瓦片。

## 功能概述

该脚本可以：

1. 批量处理 `3di_res/netcdf` 文件夹下的所有 NetCDF 文件
2. 将每个 NetCDF 文件转换为水深度 GeoTIFF 文件
3. 从 GeoTIFF 文件生成彩色地图瓦片
4. 按照文件名组织输出目录结构
5. 提供实时进度显示和详细的处理报告

## 输出目录结构

对于每个名为 `name.nc` 或 `startTime_endTime.nc` 的 NetCDF 文件：

- GeoTIFF 文件将保存在：`3di_res/geotiff/{name}/` 目录
- 地图瓦片将保存在：`3di_res/tiles/{name}/` 目录

其中 `{name}` 是从文件名中提取的基本名称（不带扩展名）。

## 使用方法

### 基本用法

```bash
# 使用默认参数运行
python convert_nc_to_tiles.py
```

这将使用默认路径处理所有 NetCDF 文件。

### 指定参数

```bash
# 指定自定义路径和参数
python convert_nc_to_tiles.py \
  --netcdf-dir="/path/to/netcdf/files" \
  --base-dir="/path/to/output" \
  --gridadmin-path="/path/to/gridadmin.h5" \
  --dem-path="/path/to/5m_dem.tif" \
  --color-table="/path/to/color.txt" \
  --zoom-levels="0-14" \
  --processes=8 \
  --force-recalculate
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--netcdf-dir` | `../data/3di_res/netcdf` | 包含 NetCDF 文件的目录 |
| `--base-dir` | `../data/3di_res` | 基础输出目录 |
| `--gridadmin-path` | `../data/3di_res/gridadmin.h5` | gridadmin.h5 文件路径 |
| `--dem-path` | `../data/3di_res/5m_dem.tif` | DEM 文件路径 |
| `--color-table` | `color.txt` | 颜色表文件路径 |
| `--force-recalculate` | `False` | 强制重新计算已存在的文件 |
| `--zoom-levels` | `0-14` | 瓦片缩放级别 |
| `--processes` | `8` | 并行处理的进程数 |

## 颜色表格式

颜色表文件（默认为 `color.txt`）应遵循以下格式：

```
# 注释行
值 R G B [A]
```

示例：

```
# 颜色表示例
0 255 255 255 0  # 0深度是透明的
1 151 219 242 255  # 浅蓝色表示浅水区
10 53 171 216 255  # 浅蓝色
20 32 115 174 255  # 中蓝色
50 18 64 97 255  # 深蓝色
100 7 24 36 255  # 非常深的蓝色
255 1 5 7 255  # 极深处几乎是黑色
```

## 常见问题

### 问题：脚本无法找到 NetCDF 文件

确保指定的 `--netcdf-dir` 目录中包含 `.nc` 扩展名的 NetCDF 文件。

### 问题：缺少 gridadmin.h5 或 DEM 文件

脚本现在会在启动前检查这些文件是否存在，并提供明确的错误消息。如果看到"DEM文件不存在"或"gridadmin.h5文件不存在"的错误，请确保：

1. 使用 `--dem-path` 参数指定正确的DEM文件路径（默认查找`../data/3di_res/5m_dem.tif`）
2. 使用 `--gridadmin-path` 参数指定正确的gridadmin.h5文件路径

例如：

```bash
python convert_nc_to_tiles.py --dem-path="/correct/path/to/your_dem.tif"
```

### 问题：处理过程很慢

3Di 水深度计算和瓦片生成是计算密集型任务。您可以尝试：

1. 调整 `--processes` 参数增加并行处理的进程数（根据您的 CPU 核心数）
2. 减少 `--zoom-levels` 范围（例如使用 `4-12` 代替 `0-14`）
3. 分批处理较少的文件

### 问题：生成的瓦片有问题

检查您的颜色表是否正确格式化，并确保 DEM 文件与 NetCDF 结果使用相同的坐标系统。

## 日志记录

脚本会生成详细的日志文件 `nc_conversion.log`，记录所有处理步骤和可能的错误。此外，每个处理步骤都会显示带有进度条的实时进度，以及对处理过程中使用的文件路径的明确反馈。 