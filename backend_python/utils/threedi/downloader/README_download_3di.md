# 3Di Simulation Results Downloader

该脚本用于从3Di API下载模拟结果和相关元数据。它提供了一种简单的方式来访问和下载3Di模拟的结果文件，包括NetCDF文件和gridadmin.h5文件。

## 功能特点

- 连接到3Di API并进行认证
- 根据用户名、组织、标签等筛选模拟
- 下载模拟结果文件（NetCDF等）
- 下载gridadmin.h5文件（用于ThreediToolbox和threedigrid）
- 支持按文件类型筛选下载
- 显示下载进度条
- 下载后创建元数据文件
- 完善的错误处理和日志记录
- 支持从配置文件加载设置
- 自动按照标准文件结构组织下载的文件

## 文件组织结构

脚本将按照以下结构保存文件：

```
data/3di/
└── sim_YYYYMMDD/               # 基于模拟创建日期的文件夹
    ├── netcdf/                 # NetCDF文件，包括results_3di.nc和gridadmin.h5
    ├── geotiff/                # GeoTIFF文件
    ├── other/                  # 其他文件类型
    ├── tiles/                  # 处理后生成的地图瓦片
    ├── waterdepth_folder/      # 处理后生成的水深文件
    └── metadata.json           # 下载元数据信息
```

## 依赖项

- `threedi-api-client`: 用于与3Di API通信
- `tqdm`: 用于显示进度条
- `pathlib`: 用于处理文件路径
- `argparse`: 用于处理命令行参数

## 安装

```bash
pip install threedi-api-client tqdm
```

## 使用方法

### 基本用法

```bash
python download_3di_results.py --api-token YOUR_API_TOKEN
```

这将下载最新完成的模拟结果并保存到默认目录 `../data/3di/`。

### 认证

你需要提供一个3Di API个人令牌。你可以通过以下方式之一提供：

1. 使用 `--api-token` 参数：

```bash
python download_3di_results.py --api-token YOUR_API_TOKEN
```

2. 设置环境变量：

```bash
export THREEDI_API_PERSONAL_API_TOKEN=YOUR_API_TOKEN
python download_3di_results.py
```

3. 使用配置文件：

```bash
python download_3di_results.py --config-file 3di_config.json
```

### 使用配置文件

可以使用JSON配置文件存储API凭据和默认设置。创建一个类似如下内容的文件：

```json
{
    "THREEDI_API_HOST": "https://api.3di.live",
    "THREEDI_API_PERSONAL_API_TOKEN": "YOUR_API_TOKEN_HERE",
    "DEFAULT_OUTPUT_DIR": "../data/3di",
    "DEFAULT_OPTIONS": {
        "include_gridadmin": true,
        "file_types": ["nc", "h5", "csv", "log"],
        "zoom_levels": "0-14",
        "processes": 8
    }
}
```

然后可以使用 `--config-file` 参数指定配置文件：

```bash
python download_3di_results.py --config-file 3di_config.json
```

命令行参数会覆盖配置文件中的设置。

### 筛选模拟

可以使用各种筛选条件来选择特定的模拟：

```bash
# 按用户名筛选
python download_3di_results.py --username john_doe

# 按组织筛选
python download_3di_results.py --organisation "My Company"

# 按标签筛选
python download_3di_results.py --tags "flood,test"

# 按状态筛选（默认为"finished"）
python download_3di_results.py --status "postprocessing"
```

### 指定模拟ID

如果你知道特定模拟的ID，可以直接指定：

```bash
python download_3di_results.py --simulation-id 12345
```

### 仅列出模拟

如果你只想列出可用的模拟而不下载任何文件：

```bash
python download_3di_results.py --list-only

# 指定最多列出的模拟数量
python download_3di_results.py --list-only --limit 20
```

### 文件类型筛选

可以指定只下载特定类型的文件：

```bash
# 只下载NetCDF和CSV文件
python download_3di_results.py --file-types nc,csv
```

### 其他选项

```bash
# 指定输出目录
python download_3di_results.py --output-dir my_results

# 不下载gridadmin.h5文件
python download_3di_results.py --no-gridadmin

# 指定API主机（默认为https://api.3di.live）
python download_3di_results.py --api-host https://custom-api.example.com
```

## 作为Python模块使用

除了命令行调用，你还可以在其他Python脚本中导入和使用：

```python
from download_3di_results import SimulationDownloader, load_config_from_file

# 从配置文件加载
config = load_config_from_file("3di_config.json")

# 或者手动配置API客户端
config = {
    "THREEDI_API_HOST": "https://api.3di.live",
    "THREEDI_API_PERSONAL_API_TOKEN": "YOUR_API_TOKEN"
}

# 初始化下载器
downloader = SimulationDownloader(config, output_dir="../data/3di")

# 列出模拟
simulations = downloader.list_simulations(username="john_doe", limit=5)

# 下载最新的模拟结果
downloaded = downloader.select_and_download_latest(
    username="john_doe",
    include_gridadmin=True,
    file_types=["nc", "h5"]
)

# 下载特定模拟ID的结果
simulation_id = 12345
result_files = downloader.download_result_files(
    simulation_id=simulation_id,
    simulation_name="flood_simulation",
    include_gridadmin=True
)
```

## 示例输出

成功运行后，脚本将显示类似以下内容的信息：

```
===== Download Summary =====
Result files downloaded: 3
- /data/3di/sim_20240601/netcdf/results_3di.nc
- /data/3di/sim_20240601/other/aggregate_results_3di.nc
- /data/3di/sim_20240601/other/flow_summary.log

Gridadmin file: /data/3di/sim_20240601/netcdf/gridadmin.h5

All files saved to: ../data/3di
```

下载的文件将保存在指定目录中（默认为`../data/3di/`），每个模拟会创建一个遵循`sim_YYYYMMDD`格式的文件夹。

## 下载后的处理

下载完成后，NetCDF文件和gridadmin.h5可用于以下用途：

1. 使用ThreediToolbox（QGIS插件）进行分析和可视化
2. 使用threedigrid Python包进行数据分析
3. 使用process_3di_results.py脚本进行进一步处理：
   ```bash
   python process_3di_results.py --config-file 3di_config.json --color-table color.txt
   ```
   
   这将生成：
   - 水深GeoTIFF文件（保存在`waterdepth_folder`中）
   - 用于Web可视化的地图瓦片（保存在`tiles`文件夹中） 