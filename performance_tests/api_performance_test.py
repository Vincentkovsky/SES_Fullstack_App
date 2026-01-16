#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REST API性能测试脚本
测试指标：
1. REST API响应时间（P50/P95/P99）
2. 吞吐量（requests/sec）
3. 并发处理能力
4. 实时从GeoTIFF生成瓦片的速度
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any
import json
from pathlib import Path
import argparse
from datetime import datetime
import numpy as np

class APIPerformanceTester:
    """API性能测试类"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url.rstrip('/')
        self.results: List[Dict[str, Any]] = []
        
    def calculate_percentiles(self, values: List[float], percentiles: List[float] = [50, 95, 99]) -> Dict[float, float]:
        """计算百分位数"""
        if not values:
            return {p: 0.0 for p in percentiles}
        
        sorted_values = sorted(values)
        result = {}
        for p in percentiles:
            index = int(len(sorted_values) * p / 100)
            index = min(index, len(sorted_values) - 1)
            result[p] = sorted_values[index]
        return result
    
    async def test_tile_endpoint(
        self, 
        session: aiohttp.ClientSession,
        simulation_id: str,
        timestep_id: str,
        z: int,
        x: int,
        y: int
    ) -> Dict[str, Any]:
        """测试单个瓦片端点"""
        url = f"{self.base_url}/api/tiles/{simulation_id}/{timestep_id}/{z}/{x}/{y}.png"
        
        start_time = time.time()
        try:
            async with session.get(url) as response:
                end_time = time.time()
                elapsed = (end_time - start_time) * 1000  # 转换为毫秒
                
                # 读取响应内容以测量完整传输时间
                content = await response.read()
                complete_time = time.time()
                total_elapsed = (complete_time - start_time) * 1000
                
                return {
                    'success': response.status == 200,
                    'status_code': response.status,
                    'response_time_ms': elapsed,
                    'total_time_ms': total_elapsed,
                    'content_size_bytes': len(content),
                    'url': url,
                    'error': None
                }
        except Exception as e:
            end_time = time.time()
            elapsed = (end_time - start_time) * 1000
            return {
                'success': False,
                'status_code': 0,
                'response_time_ms': elapsed,
                'total_time_ms': elapsed,
                'content_size_bytes': 0,
                'url': url,
                'error': str(e)
            }
    
    async def test_health_endpoint(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """测试健康检查端点"""
        url = f"{self.base_url}/api/health"
        start_time = time.time()
        try:
            async with session.get(url) as response:
                elapsed = (time.time() - start_time) * 1000
                return {
                    'success': response.status == 200,
                    'status_code': response.status,
                    'response_time_ms': elapsed,
                    'url': url,
                    'error': None
                }
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'status_code': 0,
                'response_time_ms': elapsed,
                'url': url,
                'error': str(e)
            }
    
    async def test_simulations_endpoint(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """测试模拟列表端点"""
        url = f"{self.base_url}/api/simulations"
        start_time = time.time()
        try:
            async with session.get(url) as response:
                elapsed = (time.time() - start_time) * 1000
                data = await response.json()
                return {
                    'success': response.status == 200,
                    'status_code': response.status,
                    'response_time_ms': elapsed,
                    'url': url,
                    'data': data,
                    'error': None
                }
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'status_code': 0,
                'response_time_ms': elapsed,
                'url': url,
                'error': str(e)
            }
    
    async def run_concurrent_tests(
        self,
        endpoint_type: str,
        num_requests: int,
        concurrency: int,
        **kwargs
    ) -> Dict[str, Any]:
        """运行并发测试"""
        print(f"\n开始测试: {endpoint_type}")
        print(f"  请求数: {num_requests}, 并发数: {concurrency}")
        
        connector = aiohttp.TCPConnector(limit=concurrency * 2)
        timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            start_time = time.time()
            
            # 根据端点类型创建任务
            if endpoint_type == 'tile':
                simulation_id = kwargs.get('simulation_id', 'test_simulation')
                timestep_id = kwargs.get('timestep_id', 'waterdepth_20221024_1200')
                z = kwargs.get('z', 14)
                
                # 生成不同的x, y坐标以测试不同的瓦片
                for i in range(num_requests):
                    x = kwargs.get('x', 931) + (i % 10)  # 在x方向变化
                    y = kwargs.get('y', 619) + (i // 10) % 10  # 在y方向变化
                    tasks.append(self.test_tile_endpoint(session, simulation_id, timestep_id, z, x, y))
            
            elif endpoint_type == 'health':
                tasks = [self.test_health_endpoint(session) for _ in range(num_requests)]
            
            elif endpoint_type == 'simulations':
                tasks = [self.test_simulations_endpoint(session) for _ in range(num_requests)]
            
            # 使用信号量控制并发
            semaphore = asyncio.Semaphore(concurrency)
            
            async def bounded_task(task):
                async with semaphore:
                    return await task
            
            # 执行所有任务
            results = await asyncio.gather(*[bounded_task(task) for task in tasks])
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # 分析结果
            successful_results = [r for r in results if r['success']]
            failed_results = [r for r in results if not r['success']]
            
            response_times = [r['response_time_ms'] for r in successful_results]
            
            analysis = {
                'endpoint_type': endpoint_type,
                'total_requests': num_requests,
                'concurrency': concurrency,
                'successful_requests': len(successful_results),
                'failed_requests': len(failed_results),
                'success_rate': len(successful_results) / num_requests * 100 if num_requests > 0 else 0,
                'total_time_seconds': total_time,
                'throughput_rps': num_requests / total_time if total_time > 0 else 0,
                'response_times': {
                    'min_ms': min(response_times) if response_times else 0,
                    'max_ms': max(response_times) if response_times else 0,
                    'mean_ms': statistics.mean(response_times) if response_times else 0,
                    'median_ms': statistics.median(response_times) if response_times else 0,
                    'stdev_ms': statistics.stdev(response_times) if len(response_times) > 1 else 0,
                },
                'percentiles_ms': self.calculate_percentiles(response_times),
                'errors': [r['error'] for r in failed_results] if failed_results else []
            }
            
            # 如果是瓦片测试，添加内容大小统计
            if endpoint_type == 'tile' and successful_results:
                content_sizes = [r['content_size_bytes'] for r in successful_results]
                analysis['content_size'] = {
                    'min_bytes': min(content_sizes),
                    'max_bytes': max(content_sizes),
                    'mean_bytes': statistics.mean(content_sizes),
                    'total_bytes': sum(content_sizes)
                }
            
            return analysis
    
    async def find_available_simulation(self) -> tuple:
        """查找可用的模拟和时间步"""
        async with aiohttp.ClientSession() as session:
            # 获取模拟列表
            url = f"{self.base_url}/api/simulations"
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success') and data.get('message'):
                            simulations = data['message']
                            if simulations:
                                simulation_id = simulations[0]
                                
                                # 获取该模拟的时间步
                                timesteps_url = f"{self.base_url}/api/simulations/{simulation_id}/timesteps"
                                async with session.get(timesteps_url) as ts_response:
                                    if ts_response.status == 200:
                                        ts_data = await ts_response.json()
                                        if ts_data.get('success') and ts_data.get('data'):
                                            timesteps = ts_data['data']
                                            if timesteps:
                                                timestep_id = timesteps[0]['timestep_id']
                                                return simulation_id, timestep_id
            except Exception as e:
                print(f"警告: 无法自动查找模拟数据: {e}")
        
        return None, None
    
    def generate_report(self, all_results: List[Dict[str, Any]], output_file: str = None):
        """生成测试报告"""
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'base_url': self.base_url,
            'results': all_results,
            'summary': {}
        }
        
        # 计算总体统计
        for result in all_results:
            endpoint = result['endpoint_type']
            if endpoint not in report['summary']:
                report['summary'][endpoint] = {
                    'total_tests': 0,
                    'avg_throughput_rps': [],
                    'avg_response_time_p50_ms': [],
                    'avg_response_time_p95_ms': [],
                    'avg_response_time_p99_ms': [],
                    'max_concurrency': 0
                }
            
            summary = report['summary'][endpoint]
            summary['total_tests'] += 1
            summary['avg_throughput_rps'].append(result['throughput_rps'])
            summary['avg_response_time_p50_ms'].append(result['percentiles_ms'].get(50, 0))
            summary['avg_response_time_p95_ms'].append(result['percentiles_ms'].get(95, 0))
            summary['avg_response_time_p99_ms'].append(result['percentiles_ms'].get(99, 0))
            summary['max_concurrency'] = max(summary['max_concurrency'], result['concurrency'])
        
        # 计算平均值
        for endpoint, summary in report['summary'].items():
            if summary['avg_throughput_rps']:
                summary['avg_throughput_rps'] = statistics.mean(summary['avg_throughput_rps'])
                summary['avg_response_time_p50_ms'] = statistics.mean(summary['avg_response_time_p50_ms'])
                summary['avg_response_time_p95_ms'] = statistics.mean(summary['avg_response_time_p95_ms'])
                summary['avg_response_time_p99_ms'] = statistics.mean(summary['avg_response_time_p99_ms'])
        
        # 打印报告
        print("\n" + "="*80)
        print("性能测试报告")
        print("="*80)
        print(f"测试时间: {report['test_timestamp']}")
        print(f"API地址: {report['base_url']}")
        print("\n总体统计:")
        for endpoint, summary in report['summary'].items():
            print(f"\n  {endpoint.upper()} 端点:")
            print(f"    测试次数: {summary['total_tests']}")
            print(f"    平均吞吐量: {summary['avg_throughput_rps']:.2f} requests/sec")
            print(f"    平均响应时间 (P50): {summary['avg_response_time_p50_ms']:.2f} ms")
            print(f"    平均响应时间 (P95): {summary['avg_response_time_p95_ms']:.2f} ms")
            print(f"    平均响应时间 (P99): {summary['avg_response_time_p99_ms']:.2f} ms")
            print(f"    最大并发数: {summary['max_concurrency']}")
        
        print("\n详细结果:")
        for i, result in enumerate(all_results, 1):
            print(f"\n  测试 {i}: {result['endpoint_type']} (并发={result['concurrency']}, 请求数={result['total_requests']})")
            print(f"    成功率: {result['success_rate']:.2f}%")
            print(f"    吞吐量: {result['throughput_rps']:.2f} requests/sec")
            print(f"    响应时间 (P50): {result['percentiles_ms'].get(50, 0):.2f} ms")
            print(f"    响应时间 (P95): {result['percentiles_ms'].get(95, 0):.2f} ms")
            print(f"    响应时间 (P99): {result['percentiles_ms'].get(99, 0):.2f} ms")
            if result.get('content_size'):
                print(f"    平均内容大小: {result['content_size']['mean_bytes']:.0f} bytes")
        
        # 保存到文件
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n报告已保存到: {output_path}")
        
        return report


async def main():
    parser = argparse.ArgumentParser(description='API性能测试工具')
    parser.add_argument('--url', default='http://localhost:3000', help='API基础URL')
    parser.add_argument('--simulation', help='模拟ID（如果不提供，将自动查找）')
    parser.add_argument('--timestep', help='时间步ID（如果不提供，将自动查找）')
    parser.add_argument('--z', type=int, default=14, help='缩放级别')
    parser.add_argument('--x', type=int, default=931, help='瓦片X坐标')
    parser.add_argument('--y', type=int, default=619, help='瓦片Y坐标')
    parser.add_argument('--output', default='performance_test_results.json', help='输出文件路径')
    
    args = parser.parse_args()
    
    tester = APIPerformanceTester(base_url=args.url)
    
    # 自动查找可用的模拟和时间步
    if not args.simulation or not args.timestep:
        print("正在查找可用的模拟数据...")
        simulation_id, timestep_id = await tester.find_available_simulation()
        if not simulation_id or not timestep_id:
            print("错误: 无法找到可用的模拟数据。请确保后端服务正在运行并且有数据。")
            print("或者使用 --simulation 和 --timestep 参数手动指定。")
            return
        args.simulation = simulation_id
        args.timestep = timestep_id
        print(f"找到模拟: {simulation_id}, 时间步: {timestep_id}")
    
    all_results = []
    
    # 测试1: 健康检查端点（低并发）
    print("\n" + "="*80)
    print("测试1: 健康检查端点")
    print("="*80)
    result1 = await tester.run_concurrent_tests(
        'health',
        num_requests=100,
        concurrency=10
    )
    all_results.append(result1)
    
    # 测试2: 模拟列表端点（低并发）
    print("\n" + "="*80)
    print("测试2: 模拟列表端点")
    print("="*80)
    result2 = await tester.run_concurrent_tests(
        'simulations',
        num_requests=50,
        concurrency=10
    )
    all_results.append(result2)
    
    # 测试3: 瓦片端点 - 不同并发级别
    print("\n" + "="*80)
    print("测试3: 瓦片生成端点 - 并发性能测试")
    print("="*80)
    
    concurrency_levels = [1, 5, 10, 20, 50, 100]
    requests_per_level = [50, 100, 200, 500, 1000, 2000]
    
    for i, (concurrency, num_requests) in enumerate(zip(concurrency_levels, requests_per_level), 1):
        print(f"\n--- 测试 3.{i}: 并发数={concurrency}, 请求数={num_requests} ---")
        result = await tester.run_concurrent_tests(
            'tile',
            num_requests=num_requests,
            concurrency=concurrency,
            simulation_id=args.simulation,
            timestep_id=args.timestep,
            z=args.z,
            x=args.x,
            y=args.y
        )
        all_results.append(result)
        
        # 短暂休息，避免服务器过载
        await asyncio.sleep(2)
    
    # 生成报告
    tester.generate_report(all_results, args.output)


if __name__ == '__main__':
    asyncio.run(main())
