#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API性能测试脚本
用于测试REST API的响应时间、吞吐量、并发能力和瓦片生成速度
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Tuple
import json
from pathlib import Path
import random
import argparse
from datetime import datetime
import csv

class PerformanceTest:
    """API性能测试类"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.results = []
        
    async def test_single_request(self, endpoint: str, params: dict = None) -> float:
        """测试单个请求的响应时间"""
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            try:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as response:
                    await response.read()
                    elapsed = (time.time() - start_time) * 1000  # 转换为毫秒
                    return elapsed
            except Exception as e:
                print(f"请求失败: {e}")
                return -1
    
    async def test_tile_generation_speed(
        self, 
        simulation_id: str,
        timestep_id: str,
        z: int,
        x: int,
        y: int,
        num_requests: int = 10
    ) -> Dict[str, float]:
        """
        测试实时瓦片生成速度
        
        Args:
            simulation_id: 模拟场景ID
            timestep_id: 时间步ID
            z, x, y: 瓦片坐标
            num_requests: 测试请求数
            
        Returns:
            包含统计信息的字典
        """
        endpoint = f"/api/tiles/{simulation_id}/{timestep_id}/{z}/{x}/{y}.png"
        response_times = []
        
        print(f"测试瓦片生成速度: {endpoint}")
        print(f"测试请求数: {num_requests}")
        
        # 第一次请求（可能触发缓存未命中）
        first_request_time = await self.test_single_request(endpoint)
        response_times.append(first_request_time)
        print(f"首次请求时间: {first_request_time:.2f}ms")
        
        # 等待一小段时间，确保缓存可能已建立
        await asyncio.sleep(0.1)
        
        # 后续请求（可能命中缓存）
        for i in range(num_requests - 1):
            elapsed = await self.test_single_request(endpoint)
            if elapsed > 0:
                response_times.append(elapsed)
            await asyncio.sleep(0.05)  # 短暂延迟
        
        # 计算统计信息
        if response_times:
            stats = {
                'first_request': first_request_time,
                'subsequent_requests': response_times[1:] if len(response_times) > 1 else [],
                'mean': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'p95': self._percentile(response_times, 95),
                'p99': self._percentile(response_times, 99),
                'min': min(response_times),
                'max': max(response_times),
                'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0
            }
            
            if stats['subsequent_requests']:
                stats['cached_mean'] = statistics.mean(stats['subsequent_requests'])
                stats['cached_median'] = statistics.median(stats['subsequent_requests'])
            
            return stats
        else:
            return {}
    
    async def test_throughput(
        self,
        endpoint: str,
        duration: int = 60,
        concurrency: int = 10
    ) -> Dict[str, float]:
        """
        测试吞吐量
        
        Args:
            endpoint: API端点
            duration: 测试持续时间（秒）
            concurrency: 并发数
            
        Returns:
            吞吐量统计信息
        """
        print(f"测试吞吐量: {endpoint}")
        print(f"持续时间: {duration}秒, 并发数: {concurrency}")
        
        request_count = 0
        error_count = 0
        response_times = []
        start_time = time.time()
        
        async def worker():
            nonlocal request_count, error_count
            async with aiohttp.ClientSession() as session:
                while time.time() - start_time < duration:
                    try:
                        req_start = time.time()
                        async with session.get(f"{self.base_url}{endpoint}") as response:
                            await response.read()
                            elapsed = (time.time() - req_start) * 1000
                            response_times.append(elapsed)
                            request_count += 1
                    except Exception as e:
                        error_count += 1
                    await asyncio.sleep(0.01)  # 短暂延迟避免过载
        
        # 启动并发worker
        tasks = [worker() for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        
        actual_duration = time.time() - start_time
        throughput = request_count / actual_duration
        
        stats = {
            'total_requests': request_count,
            'error_count': error_count,
            'error_rate': (error_count / request_count * 100) if request_count > 0 else 0,
            'throughput': throughput,
            'duration': actual_duration,
            'mean_response_time': statistics.mean(response_times) if response_times else 0,
            'p95_response_time': self._percentile(response_times, 95) if response_times else 0,
            'p99_response_time': self._percentile(response_times, 99) if response_times else 0
        }
        
        return stats
    
    async def test_concurrent_capacity(
        self,
        endpoint: str,
        max_concurrency: int = 200,
        step: int = 10,
        requests_per_user: int = 10
    ) -> List[Dict[str, float]]:
        """
        测试并发处理能力
        
        Args:
            endpoint: API端点
            max_concurrency: 最大并发数
            step: 并发数递增步长
            requests_per_user: 每个并发用户的请求数
            
        Returns:
            不同并发数下的性能数据列表
        """
        results = []
        
        for concurrency in range(step, max_concurrency + 1, step):
            print(f"\n测试并发数: {concurrency}")
            
            response_times = []
            error_count = 0
            start_time = time.time()
            
            async def worker():
                nonlocal error_count
                async with aiohttp.ClientSession() as session:
                    for _ in range(requests_per_user):
                        try:
                            req_start = time.time()
                            async with session.get(f"{self.base_url}{endpoint}") as response:
                                await response.read()
                                elapsed = (time.time() - req_start) * 1000
                                response_times.append(elapsed)
                        except Exception as e:
                            error_count += 1
                        await asyncio.sleep(0.01)
            
            # 启动并发worker
            tasks = [worker() for _ in range(concurrency)]
            await asyncio.gather(*tasks)
            
            total_time = time.time() - start_time
            throughput = len(response_times) / total_time if total_time > 0 else 0
            
            result = {
                'concurrency': concurrency,
                'total_requests': len(response_times),
                'error_count': error_count,
                'error_rate': (error_count / (len(response_times) + error_count) * 100) if (len(response_times) + error_count) > 0 else 0,
                'total_time': total_time,
                'throughput': throughput,
                'mean_response_time': statistics.mean(response_times) if response_times else 0,
                'p50_response_time': self._percentile(response_times, 50) if response_times else 0,
                'p95_response_time': self._percentile(response_times, 95) if response_times else 0,
                'p99_response_time': self._percentile(response_times, 99) if response_times else 0
            }
            
            results.append(result)
            print(f"  吞吐量: {throughput:.2f} req/s, 平均响应时间: {result['mean_response_time']:.2f}ms, 错误率: {result['error_rate']:.2f}%")
            
            # 如果错误率过高，提前结束
            if result['error_rate'] > 10:
                print(f"错误率过高 ({result['error_rate']:.2f}%)，停止测试")
                break
        
        return results
    
    async def test_multiple_endpoints(
        self,
        endpoints: List[Tuple[str, dict]],
        num_requests: int = 100
    ) -> Dict[str, Dict[str, float]]:
        """
        测试多个端点的响应时间
        
        Args:
            endpoints: 端点列表，每个元素为 (endpoint, params) 元组
            num_requests: 每个端点的测试请求数
            
        Returns:
            每个端点的统计信息
        """
        results = {}
        
        for endpoint, params in endpoints:
            print(f"\n测试端点: {endpoint}")
            response_times = []
            
            for i in range(num_requests):
                elapsed = await self.test_single_request(endpoint, params)
                if elapsed > 0:
                    response_times.append(elapsed)
                await asyncio.sleep(0.1)  # 避免过载
            
            if response_times:
                stats = {
                    'mean': statistics.mean(response_times),
                    'median': statistics.median(response_times),
                    'p50': self._percentile(response_times, 50),
                    'p95': self._percentile(response_times, 95),
                    'p99': self._percentile(response_times, 99),
                    'min': min(response_times),
                    'max': max(response_times),
                    'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0
                }
                results[endpoint] = stats
                print(f"  P50: {stats['p50']:.2f}ms, P95: {stats['p95']:.2f}ms, P99: {stats['p99']:.2f}ms")
        
        return results
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def save_results(self, filename: str, data: dict):
        """保存测试结果到JSON文件"""
        output_path = Path("test_results") / filename
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n结果已保存到: {output_path}")
    
    def save_results_csv(self, filename: str, data: List[Dict]):
        """保存测试结果到CSV文件"""
        output_path = Path("test_results") / filename
        output_path.parent.mkdir(exist_ok=True)
        
        if not data:
            return
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        print(f"\n结果已保存到: {output_path}")


async def main():
    parser = argparse.ArgumentParser(description='API性能测试工具')
    parser.add_argument('--base-url', default='http://localhost:3000', help='API基础URL')
    parser.add_argument('--test-type', choices=['tile', 'throughput', 'concurrent', 'endpoints', 'all'],
                       default='all', help='测试类型')
    parser.add_argument('--simulation-id', default='test_simulation', help='模拟场景ID')
    parser.add_argument('--timestep-id', default='waterdepth_20221024_1200', help='时间步ID')
    
    args = parser.parse_args()
    
    tester = PerformanceTest(base_url=args.base_url)
    results = {
        'test_time': datetime.now().isoformat(),
        'base_url': args.base_url,
        'test_type': args.test_type
    }
    
    if args.test_type in ['tile', 'all']:
        print("=" * 60)
        print("测试1: 实时瓦片生成速度")
        print("=" * 60)
        
        # 测试不同缩放级别
        for z in [10, 12, 14, 16]:
            x = random.randint(0, 2**z - 1)
            y = random.randint(0, 2**z - 1)
            
            tile_stats = await tester.test_tile_generation_speed(
                args.simulation_id,
                args.timestep_id,
                z, x, y,
                num_requests=20
            )
            
            if tile_stats:
                print(f"\n缩放级别 z={z} 的统计:")
                print(f"  首次请求: {tile_stats['first_request']:.2f}ms")
                if 'cached_mean' in tile_stats:
                    print(f"  缓存后平均: {tile_stats['cached_mean']:.2f}ms")
                print(f"  总体平均: {tile_stats['mean']:.2f}ms")
                print(f"  P95: {tile_stats['p95']:.2f}ms")
                print(f"  P99: {tile_stats['p99']:.2f}ms")
                
                results[f'tile_generation_z{z}'] = tile_stats
    
    if args.test_type in ['throughput', 'all']:
        print("\n" + "=" * 60)
        print("测试2: 吞吐量测试")
        print("=" * 60)
        
        endpoint = f"/api/tiles/{args.simulation_id}/{args.timestep_id}/14/931/619.png"
        throughput_stats = await tester.test_throughput(
            endpoint,
            duration=60,
            concurrency=20
        )
        
        print(f"\n吞吐量统计:")
        print(f"  总请求数: {throughput_stats['total_requests']}")
        print(f"  吞吐量: {throughput_stats['throughput']:.2f} req/s")
        print(f"  平均响应时间: {throughput_stats['mean_response_time']:.2f}ms")
        print(f"  P95响应时间: {throughput_stats['p95_response_time']:.2f}ms")
        print(f"  错误率: {throughput_stats['error_rate']:.2f}%")
        
        results['throughput'] = throughput_stats
    
    if args.test_type in ['concurrent', 'all']:
        print("\n" + "=" * 60)
        print("测试3: 并发处理能力")
        print("=" * 60)
        
        endpoint = f"/api/tiles/{args.simulation_id}/{args.timestep_id}/14/931/619.png"
        concurrent_results = await tester.test_concurrent_capacity(
            endpoint,
            max_concurrency=200,
            step=20,
            requests_per_user=5
        )
        
        results['concurrent_capacity'] = concurrent_results
        tester.save_results_csv('concurrent_capacity.csv', concurrent_results)
    
    if args.test_type in ['endpoints', 'all']:
        print("\n" + "=" * 60)
        print("测试4: 多端点响应时间")
        print("=" * 60)
        
        endpoints = [
            ("/api/health", None),
            (f"/api/tiles/{args.simulation_id}/{args.timestep_id}/14/931/619.png", None),
            ("/api/inference/cuda_info", None),
            ("/api/water-depth", {
                'lat': -35.117,
                'lng': 147.356,
                'timestamp': args.timestep_id,
                'simulation': args.simulation_id
            })
        ]
        
        endpoint_results = await tester.test_multiple_endpoints(
            endpoints,
            num_requests=50
        )
        
        results['endpoints'] = endpoint_results
    
    # 保存所有结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tester.save_results(f'performance_test_{timestamp}.json', results)
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
