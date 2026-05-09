"""
Performance Benchmarking Script
Tests system performance under various loads
"""

import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import io
import random
from typing import List, Dict
import requests
from datetime import datetime

from fingerprinting import ImageFingerprinter
from watermarking import InvisibleWatermarker


class PerformanceBenchmark:
    """
    Benchmark suite for image provenance system
    """
    
    def __init__(self, api_url: str = 'http://localhost:8000'):
        self.api_url = api_url
        self.fingerprinter = ImageFingerprinter()
        self.watermarker = InvisibleWatermarker()
        self.results = {}
    
    def create_test_image(self, size=(800, 600)):
        """Create a random test image"""
        color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )
        img = Image.new('RGB', size, color=color)
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        return img, img_bytes.getvalue()
    
    def benchmark_fingerprinting(self, num_images: int = 100):
        """
        Benchmark fingerprinting performance
        """
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Fingerprinting ({num_images} images)")
        print(f"{'='*60}")
        
        timings = []
        
        for i in range(num_images):
            img, img_bytes = self.create_test_image()
            
            start = time.time()
            fingerprints = self.fingerprinter.fingerprint_image(
                image=img,
                image_bytes=img_bytes
            )
            elapsed = time.time() - start
            timings.append(elapsed)
            
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{num_images} images...")
        
        avg_time = statistics.mean(timings)
        median_time = statistics.median(timings)
        min_time = min(timings)
        max_time = max(timings)
        
        print(f"\nResults:")
        print(f"  Average: {avg_time*1000:.2f}ms per image")
        print(f"  Median: {median_time*1000:.2f}ms")
        print(f"  Min: {min_time*1000:.2f}ms")
        print(f"  Max: {max_time*1000:.2f}ms")
        print(f"  Throughput: {1/avg_time:.2f} images/second")
        
        self.results['fingerprinting'] = {
            'avg_ms': avg_time * 1000,
            'median_ms': median_time * 1000,
            'throughput': 1 / avg_time
        }
    
    def benchmark_watermarking(self, num_images: int = 100):
        """
        Benchmark watermarking performance
        """
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Watermarking ({num_images} images)")
        print(f"{'='*60}")
        
        embed_timings = []
        extract_timings = []
        
        for i in range(num_images):
            img, _ = self.create_test_image()
            
            watermark_data = {
                'uuid': f'test_{i}',
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Benchmark embedding
            start = time.time()
            watermarked = self.watermarker.embed_watermark(img, watermark_data)
            embed_time = time.time() - start
            embed_timings.append(embed_time)
            
            # Benchmark extraction
            start = time.time()
            extracted = self.watermarker.extract_watermark(watermarked)
            extract_time = time.time() - start
            extract_timings.append(extract_time)
            
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{num_images} images...")
        
        print(f"\nEmbed Results:")
        print(f"  Average: {statistics.mean(embed_timings)*1000:.2f}ms")
        print(f"  Throughput: {1/statistics.mean(embed_timings):.2f} images/second")
        
        print(f"\nExtract Results:")
        print(f"  Average: {statistics.mean(extract_timings)*1000:.2f}ms")
        print(f"  Throughput: {1/statistics.mean(extract_timings):.2f} images/second")
        
        self.results['watermarking'] = {
            'embed_avg_ms': statistics.mean(embed_timings) * 1000,
            'extract_avg_ms': statistics.mean(extract_timings) * 1000
        }
    
    def benchmark_api_upload(self, num_images: int = 50, concurrent: int = 5):
        """
        Benchmark API upload endpoint
        """
        print(f"\n{'='*60}")
        print(f"BENCHMARK: API Upload ({num_images} images, {concurrent} concurrent)")
        print(f"{'='*60}")
        
        def upload_image(idx):
            img, img_bytes = self.create_test_image()
            
            files = {'file': (f'test_{idx}.png', img_bytes, 'image/png')}
            headers = {'uploaded-by': f'bench_user_{idx}'}
            
            start = time.time()
            response = requests.post(
                f"{self.api_url}/api/v1/images/upload",
                files=files,
                headers=headers
            )
            elapsed = time.time() - start
            
            return {
                'success': response.status_code == 200,
                'time': elapsed,
                'status': response.status_code
            }
        
        start_time = time.time()
        timings = []
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(upload_image, i) for i in range(num_images)]
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                timings.append(result['time'])
                
                if result['success']:
                    success_count += 1
                
                if (i + 1) % 10 == 0:
                    print(f"  Completed {i + 1}/{num_images} uploads...")
        
        total_time = time.time() - start_time
        
        print(f"\nResults:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Average per image: {statistics.mean(timings)*1000:.2f}ms")
        print(f"  Throughput: {num_images/total_time:.2f} uploads/second")
        print(f"  Success rate: {success_count/num_images*100:.1f}%")
        
        self.results['api_upload'] = {
            'total_time_s': total_time,
            'avg_ms': statistics.mean(timings) * 1000,
            'throughput': num_images / total_time,
            'success_rate': success_count / num_images
        }
    
    def benchmark_hash_comparison(self, num_comparisons: int = 10000):
        """
        Benchmark hash comparison speed
        """
        print(f"\n{'='*60}")
        print(f"BENCHMARK: Hash Comparison ({num_comparisons} comparisons)")
        print(f"{'='*60}")
        
        # Generate test hashes
        img1, bytes1 = self.create_test_image()
        img2, bytes2 = self.create_test_image()
        
        fp1 = self.fingerprinter.fingerprint_image(image=img1, image_bytes=bytes1)
        fp2 = self.fingerprinter.fingerprint_image(image=img2, image_bytes=bytes2)
        
        timings = []
        
        for _ in range(num_comparisons):
            start = time.time()
            similarity = self.fingerprinter.compare_perceptual_hashes(
                fp1['perceptual_hash'],
                fp2['perceptual_hash']
            )
            elapsed = time.time() - start
            timings.append(elapsed)
        
        avg_time = statistics.mean(timings)
        
        print(f"\nResults:")
        print(f"  Average: {avg_time*1000000:.2f}μs per comparison")
        print(f"  Throughput: {1/avg_time:,.0f} comparisons/second")
        
        self.results['hash_comparison'] = {
            'avg_us': avg_time * 1000000,
            'throughput': 1 / avg_time
        }
    
    def generate_report(self):
        """Generate performance report"""
        print(f"\n{'='*60}")
        print("PERFORMANCE REPORT SUMMARY")
        print(f"{'='*60}")
        
        if 'fingerprinting' in self.results:
            print(f"\nFingerprinting:")
            print(f"  {self.results['fingerprinting']['throughput']:.1f} images/sec")
            print(f"  {self.results['fingerprinting']['avg_ms']:.1f}ms average")
        
        if 'watermarking' in self.results:
            print(f"\nWatermarking:")
            print(f"  Embed: {self.results['watermarking']['embed_avg_ms']:.1f}ms")
            print(f"  Extract: {self.results['watermarking']['extract_avg_ms']:.1f}ms")
        
        if 'api_upload' in self.results:
            print(f"\nAPI Upload:")
            print(f"  {self.results['api_upload']['throughput']:.1f} uploads/sec")
            print(f"  Success rate: {self.results['api_upload']['success_rate']*100:.1f}%")
        
        if 'hash_comparison' in self.results:
            print(f"\nHash Comparison:")
            print(f"  {self.results['hash_comparison']['throughput']:,.0f} comparisons/sec")
        
        print(f"\n{'='*60}\n")


def run_benchmarks():
    """Run all benchmarks"""
    print("\n" + "="*60)
    print("IMAGE PROVENANCE SYSTEM - PERFORMANCE BENCHMARKS")
    print("="*60)
    
    bench = PerformanceBenchmark()
    
    try:
        # Core operations benchmarks
        bench.benchmark_fingerprinting(num_images=100)
        bench.benchmark_watermarking(num_images=100)
        bench.benchmark_hash_comparison(num_comparisons=10000)
        
        # API benchmarks (requires running API)
        print("\n\nAPI Benchmarks (requires running API server):")
        try:
            response = requests.get('http://localhost:8000/health', timeout=2)
            if response.status_code == 200:
                bench.benchmark_api_upload(num_images=50, concurrent=5)
            else:
                print("  ⚠ API not available, skipping API benchmarks")
        except requests.exceptions.RequestException:
            print("  ⚠ API not available, skipping API benchmarks")
        
        # Generate final report
        bench.generate_report()
        
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
    except Exception as e:
        print(f"\n\nBenchmark error: {e}")


if __name__ == "__main__":
    run_benchmarks()
