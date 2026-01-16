#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API性能测试脚本
用于测试REST API的响应时间、吞吐量和并发处理能力
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
from collections import defaultdict
import json
import csv
from pathlib import Path
import argparse

@dataclass
class TestResult:
    """测试结果数据类"""
    endpoint: str
    response_time: float
    status_code: int
    success: bool
    error: str = ""

class APIPerformanceTester:
    """API性能测试类"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        
    async def make_request(
        self, 
        session: aiohttp.ClientSession,
        endpoint: str,
        method: str = "GET",
        **kwargs
    ) -> TestResult:
        """发送单个请求并记录响应时间"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with session.request(method, url, **kwargs) as response:
                elapsed = time.time() - start_time
                content = await response.read()
                
                return TestResult(
                    endpoint=endpoint,
                    response_time=elapsed * 1000,  # 转换为毫秒
                    status_code=response.status,
                    success=response.status == 200
                )
        except Exception as e:
            elapsed = time.time() - start_time
            return TestResult(
                endpoint=endpoint,
                response_time=elapsed * 1000,
                status_code=0,
                success=False,
                error=str(e)
            )
    
    async def test_endpoint(
        self,
        endpoint: str,
        num_requests: int = 100,
        concurrency: int = 10
    ) -> Dict[str, Any]:
        """测试单个端点的性能"""
        print(f"\n测试端点: {endpoint}")
        print(f"请求数: {num_requests}, 并发数: {concurrency}")
        
        results = []
        semaphore = asyncio.Semaphore(concurrency)
        
        async def bounded_request(session, endpoint):
            async with semaphore:
                return await self.make_request(session, endpoint)
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                bounded_request(session, endpoint)
                for _ in range(num_requests)
            ]
            results = await asyncio.gather(*tasks)
        
        return self.analyze_results(results, endpoint)
    
    def analyze_results(
        self, 
        results: List[TestResult],
        endpoint: str
    ) -> Dict[str, Any]:
        """分析测试结果"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        if not successful:
            return {
                "endpoint": endpoint,
                "total_requests": len(results),
                "successful": 0,
                "failed": len(failed),
                "error": "所有请求都失败了"
            }
        
        response_times = [r.response_time for r in successful]
        response_times.sort()
        
        n = len(response_times)
        p50_idx = int(n * 0.5)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)
        
        analysis = {
            "endpoint": endpoint,
            "total_requests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) * 100,
            "p50": response_times[p50_idx] if p50_idx < n else 0,
            "p95": response_times[p95_idx] if p95_idx < n else 0,
            "p99": response_times[p99_idx] if p99_idx < n else 0,
            "min": min(response_times),
            "max": max(response_times),
            "mean": statistics.mean(response_times),
            "median": statistics.median(response_times),
            "stdev": statistics.stdev(response_times) if len(response_times) > 1 else 0
        }
        
        if failed:
            error_types = defaultdict(int)
            for f in failed:
                error_types[f.error or f"HTTP {f.status_code}"] += 1
            analysis["errors"] = dict(error_types)
        
        return analysis
    
    async def test_throughput(
        self,
        endpoint: str,
        duration: int = 60,
        concurrency: int = 10
    ) -> Dict[str, Any]:
        """测试吞吐量（在指定时间内发送尽可能多的请求）"""
        print(f"\n吞吐量测试: {endpoint}")
        print(f"持续时间: {duration}秒, 并发数: {concurrency}")
        
        results = []
        semaphore = asyncio.Semaphore(concurrency)
        start_time = time.time()
        end_time = start_time + duration
        
        async def continuous_request(session, endpoint):
            count = 0
            while time.time() < end_time:
                async with semaphore:
                    result = await self.make_request(session, endpoint)
                    results.append(result)
                    count += 1
            return count
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                continuous_request(session, endpoint)
                for _ in range(concurrency)
            ]
            request_counts = await asyncio.gather(*tasks)
        
        total_requests = sum(request_counts)
        actual_duration = time.time() - start_time
        throughput = total_requests / actual_duration
        
        successful = [r for r in results if r.success]
        error_rate = (len(results) - len(successful)) / len(results) * 100 if results else 0
        
        return {
            "endpoint": endpoint,
            "duration": actual_duration,
            "total_requests": total_requests,
            "throughput": throughput,
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "error_rate": error_rate,
            "concurrency": concurrency
        }
    
    async def test_concurrency_limit(
        self,
        endpoint: str,
        max_concurrency: int = 100,
        requests_per_level: int = 100
    ) -> List[Dict[str, Any]]:
        """测试不同并发级别下的性能"""
        print(f"\n并发能力测试: {endpoint}")
        
        results = []
        concurrency_levels = [1, 5, 10, 20, 50, 100]
        concurrency_levels = [c for c in concurrency_levels if c <= max_concurrency]
        
        for concurrency in concurrency_levels:
            print(f"  测试并发数: {concurrency}")
            analysis = await self.test_endpoint(
                endpoint,
                num_requests=requests_per_level,
                concurrency=concurrency
            )
            analysis["concurrency"] = concurrency
            results.append(analysis)
            await asyncio.sleep(2)  # 短暂休息，避免系统过载
        
        return results
    
    def save_results(self, results: Dict[str, Any], filename: str):
        """保存测试结果到JSON文件"""
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n结果已保存到: {filepath}")
    
    def save_csv(self, results: List[Dict[str, Any]], filename: str):
        """保存测试结果到CSV文件"""
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        if not results:
            return
        
        fieldnames = list(results[0].keys())
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\nCSV结果已保存到: {filepath}")


async def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description='API性能测试')
    parser.add_argument('--base-url', default='http://localhost:3000', help='API基础URL')
    parser.add_argument('--endpoint', help='要测试的端点（如 /api/health）')
    parser.add_argument('--requests', type=int, default=100, help='请求数量')
    parser.add_argument('--concurrency', type=int, default=10, help='并发数')
    parser.add_argument('--duration', type=int, default=60, help='吞吐量测试持续时间（秒）')
    parser.add_argument('--test-type', choices=['response', 'throughput', 'concurrency'], 
                       default='response', help='测试类型')
    
    args = parser.parse_args()
    
    tester = APIPerformanceTester(base_url=args.base_url)
    
    # 默认测试端点列表
    default_endpoints = [
        "/api/health",
        "/api/inference/cuda_info",
        "/api/simulations",
    ]
    
    # 如果指定了端点，只测试该端点
    if args.endpoint:
        endpoints = [args.endpoint]
    else:
        endpoints = default_endpoints
    
    # 瓦片端点需要参数，单独处理
    tile_endpoint = None
    if args.endpoint and "tiles" in args.endpoint:
        tile_endpoint = args.endpoint
    
    all_results = {}
    
    for endpoint in endpoints:
        if args.test_type == 'response':
            result = await tester.test_endpoint(
                endpoint,
                num_requests=args.requests,
                concurrency=args.concurrency
            )
            all_results[endpoint] = result
            print(f"\n{endpoint} 测试结果:")
            print(f"  P50: {result['p50']:.2f}ms")
            print(f"  P95: {result['p95']:.2f}ms")
            print(f"  P99: {result['p99']:.2f}ms")
            print(f"  平均: {result['mean']:.2f}ms")
            print(f"  成功率: {result['success_rate']:.2f}%")
        
        elif args.test_type == 'throughput':
            result = await tester.test_throughput(
                endpoint,
                duration=args.duration,
                concurrency=args.concurrency
            )
            all_results[endpoint] = result
            print(f"\n{endpoint} 吞吐量测试结果:")
            print(f"  吞吐量: {result['throughput']:.2f} requests/sec")
            print(f"  总请求数: {result['total_requests']}")
            print(f"  错误率: {result['error_rate']:.2f}%")
        
        elif args.test_type == 'concurrency':
            results = await tester.test_concurrency_limit(
                endpoint,
                max_concurrency=args.concurrency,
                requests_per_level=args.requests
            )
            all_results[endpoint] = results
            tester.save_csv(results, f"concurrency_{endpoint.replace('/', '_')}.csv")
            print(f"\n{endpoint} 并发测试结果:")
            for r in results:
                print(f"  并发数 {r['concurrency']}: "
                      f"吞吐量 {r.get('throughput', 'N/A')}, "
                      f"P95 {r['p95']:.2f}ms, "
                      f"错误率 {100-r['success_rate']:.2f}%")
    
    # 保存结果
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    tester.save_results(all_results, f"api_test_{args.test_type}_{timestamp}.json")


if __name__ == "__main__":
    asyncio.run(main())
