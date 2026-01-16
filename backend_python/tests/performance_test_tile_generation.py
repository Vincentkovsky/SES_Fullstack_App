#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
瓦片生成速度测试脚本
专门测试从GeoTIFF文件实时生成瓦片的性能
"""

import time
import asyncio
import aiohttp
import statistics
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
import csv
import argparse
from collections import defaultdict

@dataclass
class TileTestResult:
    """瓦片测试结果"""
    simulation_id: str
    timestep_id: str
    z: int
    x: int
    y: int
    response_time: float
    status_code: int
    success: bool
    cache_hit: bool = False  # 需要从响应头或日志判断

class TileGenerationTester:
    """瓦片生成性能测试类"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.results: List[TileTestResult] = []
        
    async def generate_tile(
        self,
        session: aiohttp.ClientSession,
        simulation_id: str,
        timestep_id: str,
        z: int,
        x: int,
        y: int
    ) -> TileTestResult:
        """生成单个瓦片并记录时间"""
        endpoint = f"/api/tiles/{simulation_id}/{timestep_id}/{z}/{x}/{y}.png"
        url = f"{self.base_url}{endpoint}"
        
        start_time = time.time()
        try:
            async with session.get(url) as response:
                elapsed = (time.time() - start_time) * 1000  # 转换为毫秒
                content = await response.read()
                
                # 尝试从响应头判断是否缓存命中（如果后端有设置）
                cache_hit = response.headers.get('X-Cache-Hit', 'false').lower() == 'true'
                
                return TileTestResult(
                    simulation_id=simulation_id,
                    timestep_id=timestep_id,
                    z=z,
                    x=x,
                    y=y,
                    response_time=elapsed,
                    status_code=response.status,
                    success=response.status == 200,
                    cache_hit=cache_hit
                )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return TileTestResult(
                simulation_id=simulation_id,
                timestep_id=timestep_id,
                z=z,
                x=x,
                y=y,
                response_time=elapsed,
                status_code=0,
                success=False
            )
    
    def get_tile_coordinates_for_zoom(
        self, 
        z: int, 
        center_lat: float = -35.117, 
        center_lon: float = 147.356,
        num_tiles: int = 10
    ) -> List[Tuple[int, int]]:
        """根据中心点和缩放级别生成瓦片坐标"""
        import math
        
        def lat_lon_to_tile(lat, lon, zoom):
            """将经纬度转换为瓦片坐标"""
            n = 2.0 ** zoom
            x = int((lon + 180.0) / 360.0 * n)
            lat_rad = math.radians(lat)
            y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
            return x, y
        
        center_x, center_y = lat_lon_to_tile(center_lat, center_lon, z)
        
        # 生成中心点周围的瓦片坐标
        tiles = []
        radius = int(math.sqrt(num_tiles) / 2) + 1
        
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if len(tiles) >= num_tiles:
                    break
                tiles.append((center_x + dx, center_y + dy))
            if len(tiles) >= num_tiles:
                break
        
        return tiles[:num_tiles]
    
    async def test_tile_generation_speed(
        self,
        simulation_id: str,
        timestep_id: str,
        zoom_levels: List[int] = [13, 14, 15, 16],
        tiles_per_zoom: int = 20,
        clear_cache_first: bool = False
    ) -> Dict[str, Any]:
        """测试不同缩放级别下的瓦片生成速度"""
        print(f"\n瓦片生成速度测试")
        print(f"模拟ID: {simulation_id}, 时间步: {timestep_id}")
        print(f"缩放级别: {zoom_levels}, 每级别瓦片数: {tiles_per_zoom}")
        
        all_results = {}
        
        async with aiohttp.ClientSession() as session:
            for z in zoom_levels:
                print(f"\n测试缩放级别 z={z}")
                
                # 获取瓦片坐标
                tile_coords = self.get_tile_coordinates_for_zoom(z, num_tiles=tiles_per_zoom)
                
                # 第一轮：测试实时生成（假设缓存未命中）
                if clear_cache_first:
                    # 可以通过发送特殊请求清除缓存，或等待缓存过期
                    print("  清除缓存...")
                    await asyncio.sleep(1)
                
                print(f"  第一轮测试（实时生成）: {len(tile_coords)} 个瓦片")
                first_round_times = []
                
                for x, y in tile_coords:
                    result = await self.generate_tile(session, simulation_id, timestep_id, z, x, y)
                    if result.success:
                        first_round_times.append(result.response_time)
                    await asyncio.sleep(0.1)  # 短暂延迟，避免过载
                
                # 第二轮：测试缓存命中（立即请求相同的瓦片）
                print(f"  第二轮测试（缓存命中）: {len(tile_coords)} 个瓦片")
                second_round_times = []
                
                for x, y in tile_coords:
                    result = await self.generate_tile(session, simulation_id, timestep_id, z, x, y)
                    if result.success:
                        second_round_times.append(result.response_time)
                    await asyncio.sleep(0.1)
                
                # 分析结果
                if first_round_times and second_round_times:
                    all_results[f"z_{z}"] = {
                        "zoom_level": z,
                        "tiles_tested": len(tile_coords),
                        "real_time_generation": {
                            "count": len(first_round_times),
                            "mean": statistics.mean(first_round_times),
                            "median": statistics.median(first_round_times),
                            "min": min(first_round_times),
                            "max": max(first_round_times),
                            "p95": statistics.quantiles(first_round_times, n=20)[18] if len(first_round_times) > 1 else first_round_times[0],
                            "p99": statistics.quantiles(first_round_times, n=100)[98] if len(first_round_times) > 1 else first_round_times[0],
                        },
                        "cache_hit": {
                            "count": len(second_round_times),
                            "mean": statistics.mean(second_round_times),
                            "median": statistics.median(second_round_times),
                            "min": min(second_round_times),
                            "max": max(second_round_times),
                            "p95": statistics.quantiles(second_round_times, n=20)[18] if len(second_round_times) > 1 else second_round_times[0],
                            "p99": statistics.quantiles(second_round_times, n=100)[98] if len(second_round_times) > 1 else second_round_times[0],
                        },
                        "speedup": statistics.mean(first_round_times) / statistics.mean(second_round_times) if second_round_times else 0
                    }
                    
                    print(f"    实时生成: 平均 {statistics.mean(first_round_times):.2f}ms, "
                          f"P95 {all_results[f'z_{z}']['real_time_generation']['p95']:.2f}ms")
                    print(f"    缓存命中: 平均 {statistics.mean(second_round_times):.2f}ms, "
                          f"P95 {all_results[f'z_{z}']['cache_hit']['p95']:.2f}ms")
                    print(f"    加速比: {all_results[f'z_{z}']['speedup']:.2f}x")
        
        return all_results
    
    async def test_batch_tile_generation(
        self,
        simulation_id: str,
        timestep_id: str,
        z: int,
        num_tiles: int = 100,
        concurrency: int = 10
    ) -> Dict[str, Any]:
        """测试批量瓦片生成的吞吐量"""
        print(f"\n批量瓦片生成测试")
        print(f"缩放级别: z={z}, 瓦片数: {num_tiles}, 并发数: {concurrency}")
        
        tile_coords = self.get_tile_coordinates_for_zoom(z, num_tiles=num_tiles)
        results = []
        semaphore = asyncio.Semaphore(concurrency)
        
        async def bounded_generate(session, sim_id, ts_id, z_level, x, y):
            async with semaphore:
                return await self.generate_tile(session, sim_id, ts_id, z_level, x, y)
        
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            tasks = [
                bounded_generate(session, simulation_id, timestep_id, z, x, y)
                for x, y in tile_coords[:num_tiles]
            ]
            results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        successful = [r for r in results if r.success]
        
        response_times = [r.response_time for r in successful]
        
        return {
            "zoom_level": z,
            "total_tiles": num_tiles,
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "total_time": elapsed,
            "throughput": len(successful) / elapsed,
            "mean_time": statistics.mean(response_times) if response_times else 0,
            "median_time": statistics.median(response_times) if response_times else 0,
            "p95_time": statistics.quantiles(response_times, n=20)[18] if len(response_times) > 1 else (response_times[0] if response_times else 0),
            "concurrency": concurrency
        }
    
    def save_results(self, results: Dict[str, Any], filename: str):
        """保存测试结果"""
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n结果已保存到: {filepath}")


async def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description='瓦片生成速度测试')
    parser.add_argument('--base-url', default='http://localhost:3000', help='API基础URL')
    parser.add_argument('--simulation-id', required=True, help='模拟ID')
    parser.add_argument('--timestep-id', required=True, help='时间步ID')
    parser.add_argument('--zoom-levels', nargs='+', type=int, default=[13, 14, 15, 16], 
                       help='要测试的缩放级别')
    parser.add_argument('--tiles-per-zoom', type=int, default=20, help='每个缩放级别测试的瓦片数')
    parser.add_argument('--test-type', choices=['speed', 'throughput'], default='speed',
                       help='测试类型: speed=生成速度, throughput=吞吐量')
    parser.add_argument('--concurrency', type=int, default=10, help='并发数（用于吞吐量测试）')
    parser.add_argument('--num-tiles', type=int, default=100, help='总瓦片数（用于吞吐量测试）')
    
    args = parser.parse_args()
    
    tester = TileGenerationTester(base_url=args.base_url)
    
    if args.test_type == 'speed':
        results = await tester.test_tile_generation_speed(
            simulation_id=args.simulation_id,
            timestep_id=args.timestep_id,
            zoom_levels=args.zoom_levels,
            tiles_per_zoom=args.tiles_per_zoom
        )
        
        print("\n=== 测试结果汇总 ===")
        for key, data in results.items():
            print(f"\n缩放级别 z={data['zoom_level']}:")
            print(f"  实时生成: 平均 {data['real_time_generation']['mean']:.2f}ms, "
                  f"P95 {data['real_time_generation']['p95']:.2f}ms")
            print(f"  缓存命中: 平均 {data['cache_hit']['mean']:.2f}ms, "
                  f"P95 {data['cache_hit']['p95']:.2f}ms")
            print(f"  加速比: {data['speedup']:.2f}x")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        tester.save_results(results, f"tile_generation_speed_{timestamp}.json")
    
    elif args.test_type == 'throughput':
        results = []
        for z in args.zoom_levels:
            result = await tester.test_batch_tile_generation(
                simulation_id=args.simulation_id,
                timestep_id=args.timestep_id,
                z=z,
                num_tiles=args.num_tiles,
                concurrency=args.concurrency
            )
            results.append(result)
            
            print(f"\n缩放级别 z={z}:")
            print(f"  吞吐量: {result['throughput']:.2f} tiles/sec")
            print(f"  平均时间: {result['mean_time']:.2f}ms")
            print(f"  P95时间: {result['p95_time']:.2f}ms")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        tester.save_results({"throughput_results": results}, f"tile_generation_throughput_{timestamp}.json")


if __name__ == "__main__":
    asyncio.run(main())
