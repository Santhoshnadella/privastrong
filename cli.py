#!/usr/bin/env python3
"""
Image Provenance Tracking CLI
Command-line interface for system operations
"""

import click
import requests
import json
from pathlib import Path
from PIL import Image
import sys
from tabulate import tabulate
from datetime import datetime

API_URL = "http://localhost:8000/api/v1"


@click.group()
@click.option('--api-url', default=API_URL, help='API base URL')
@click.pass_context
def cli(ctx, api_url):
    """Image Provenance Tracking CLI"""
    ctx.ensure_object(dict)
    ctx.obj['API_URL'] = api_url


@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--user-id', required=True, help='User ID uploading the image')
@click.option('--device-id', help='Device identifier')
@click.option('--output', '-o', type=click.Choice(['json', 'table']), default='table')
@click.pass_context
def upload(ctx, image_path, user_id, device_id, output):
    """Upload and register a new image"""
    api_url = ctx.obj['API_URL']
    
    click.echo(f"Uploading {image_path}...")
    
    with open(image_path, 'rb') as f:
        files = {'file': f}
        headers = {'uploaded-by': user_id}
        
        if device_id:
            headers['device-id'] = device_id
        
        response = requests.post(
            f"{api_url}/images/upload",
            files=files,
            headers=headers
        )
    
    if response.status_code == 200:
        result = response.json()
        
        if output == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("\n✓ Image uploaded successfully!")
            click.echo(f"\nImage ID: {result['image_id']}")
            click.echo(f"Watermark ID: {result['watermark_id']}")
            click.echo(f"Storage URL: {result['storage_url']}")
            click.echo(f"\nFingerprints:")
            for key, value in result['fingerprints'].items():
                click.echo(f"  {key}: {value}")
    else:
        click.echo(f"✗ Upload failed: {response.status_code}", err=True)
        click.echo(response.text, err=True)
        sys.exit(1)


@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--device-id', help='Device identifier')
@click.option('--output', '-o', type=click.Choice(['json', 'table']), default='table')
@click.pass_context
def detect(ctx, image_path, device_id, output):
    """Detect if an image matches any tracked images"""
    api_url = ctx.obj['API_URL']
    
    click.echo(f"Analyzing {image_path}...")
    
    with open(image_path, 'rb') as f:
        files = {'file': f}
        headers = {}
        
        if device_id:
            headers['device-id'] = device_id
        
        response = requests.post(
            f"{api_url}/images/detect",
            files=files,
            headers=headers
        )
    
    if response.status_code == 200:
        result = response.json()
        
        if output == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            if result['detected']:
                click.echo("\n✓ IMAGE DETECTED!")
                click.echo(f"Confidence: {result['confidence']}")
                click.echo(f"Detection methods: {', '.join(result['methods'])}")
                
                click.echo("\nMatches:")
                for match in result['matches']:
                    click.echo(f"  • Image ID: {match.get('image_id', 'N/A')}")
                    click.echo(f"    Method: {match.get('method', 'unknown')}")
                    if 'similarity' in match:
                        click.echo(f"    Similarity: {match['similarity']:.2%}")
                
                if result.get('lineage'):
                    stats = result['lineage'].get('statistics', {})
                    click.echo("\nLineage Statistics:")
                    click.echo(f"  Total events: {stats.get('total_events', 0)}")
                    click.echo(f"  Unique devices: {stats.get('unique_devices', 0)}")
                    click.echo(f"  Max hop depth: {stats.get('max_hop_depth', 0)}")
            else:
                click.echo("\n✗ No match found - image not in tracking system")
    else:
        click.echo(f"✗ Detection failed: {response.status_code}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('image_id')
@click.option('--output', '-o', type=click.Choice(['json', 'table', 'tree']), default='table')
@click.pass_context
def lineage(ctx, image_id, output):
    """Get complete lineage for an image"""
    api_url = ctx.obj['API_URL']
    
    response = requests.get(f"{api_url}/images/{image_id}/lineage")
    
    if response.status_code == 200:
        result = response.json()
        
        if output == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output == 'tree':
            # Tree visualization
            click.echo("\nImage Lineage Tree:")
            click.echo(f"\n📷 {result['original_image']['filename']}")
            click.echo(f"   ID: {image_id}")
            click.echo(f"   Created: {result['original_image']['created_at']}")
            
            # Display hops
            if result['nodes']:
                click.echo("\n   Distribution Hops:")
                for node in result['nodes']:
                    if node['type'] == 'distribution':
                        depth = node.get('hop_depth', 0)
                        indent = "   " * (depth + 2)
                        click.echo(f"{indent}└─ {node['event_type']} (Hop {depth})")
        else:
            # Table format
            click.echo(f"\nImage: {result['original_image']['filename']}")
            click.echo(f"ID: {image_id}")
            
            stats = result['statistics']
            
            table_data = [
                ['Total Events', stats.get('total_events', 0)],
                ['Unique Devices', stats.get('unique_devices', 0)],
                ['Max Hop Depth', stats.get('max_hop_depth', 0)]
            ]
            
            click.echo("\n" + tabulate(table_data, headers=['Metric', 'Value']))
            
            if stats.get('event_breakdown'):
                click.echo("\nEvent Breakdown:")
                breakdown = [[k, v] for k, v in stats['event_breakdown'].items()]
                click.echo(tabulate(breakdown, headers=['Event Type', 'Count']))
    else:
        click.echo(f"✗ Failed to retrieve lineage: {response.status_code}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('image_id')
@click.option('--from-device', required=True, help='Source device')
@click.option('--to-device', required=True, help='Target device')
@click.option('--platform', default='cli', help='Platform identifier')
@click.pass_context
def share(ctx, image_id, from_device, to_device, platform):
    """Record a share/distribution event"""
    api_url = ctx.obj['API_URL']
    
    data = {
        'image_id': image_id,
        'context': {
            'device_id': to_device,
            'platform': platform,
            'metadata': {
                'from_device': from_device,
                'to_device': to_device
            }
        }
    }
    
    response = requests.post(
        f"{api_url}/images/{image_id}/share",
        json=data
    )
    
    if response.status_code == 200:
        result = response.json()
        click.echo(f"✓ Share event recorded")
        click.echo(f"Event ID: {result['event_id']}")
        click.echo(f"From: {from_device} → To: {to_device}")
    else:
        click.echo(f"✗ Failed to record share: {response.status_code}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('image_id')
@click.option('--threshold', default=0.75, help='Similarity threshold')
@click.pass_context
def derivatives(ctx, image_id, threshold):
    """List AI derivatives of an image"""
    api_url = ctx.obj['API_URL']
    
    response = requests.get(
        f"{api_url}/images/{image_id}/derivatives",
        params={'similarity_threshold': threshold}
    )
    
    if response.status_code == 200:
        result = response.json()
        
        click.echo(f"\nDerivatives for image {image_id}:")
        click.echo(f"Found {result['count']} derivatives\n")
        
        if result['derivatives']:
            table_data = [
                [
                    d['derivative_id'][:16] + '...',
                    f"{d['similarity']:.2%}",
                    d['detection_method'],
                    d.get('ai_model', 'N/A')
                ]
                for d in result['derivatives']
            ]
            
            click.echo(tabulate(
                table_data,
                headers=['Derivative ID', 'Similarity', 'Method', 'AI Model']
            ))
        else:
            click.echo("No derivatives found.")
    else:
        click.echo(f"✗ Failed to retrieve derivatives: {response.status_code}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--days', default=30, help='Time window in days')
@click.pass_context
def stats(ctx, days):
    """Show system statistics"""
    api_url = ctx.obj['API_URL']
    
    response = requests.get(
        f"{api_url}/stats/detections",
        params={'days': days}
    )
    
    if response.status_code == 200:
        result = response.json()
        
        click.echo(f"\nDetection Statistics (Last {days} days):\n")
        
        click.echo(f"Total Detections: {result.get('total_detections', 0)}")
        click.echo(f"Unique Images: {result.get('unique_images_detected', 0)}")
        
        if result.get('detection_methods'):
            click.echo("\nDetection Methods:")
            methods_data = [
                [method, data['count'], data['unique_images']]
                for method, data in result['detection_methods'].items()
            ]
            click.echo(tabulate(
                methods_data,
                headers=['Method', 'Total', 'Unique Images']
            ))
    else:
        click.echo(f"✗ Failed to retrieve stats: {response.status_code}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def health(ctx):
    """Check API health"""
    api_url = ctx.obj['API_URL']
    
    try:
        response = requests.get(f"{api_url.replace('/api/v1', '')}/health")
        
        if response.status_code == 200:
            result = response.json()
            click.echo("✓ API is healthy")
            click.echo(f"Status: {result['status']}")
            click.echo(f"Version: {result['version']}")
            click.echo(f"Timestamp: {result['timestamp']}")
        else:
            click.echo(f"✗ API unhealthy: {response.status_code}", err=True)
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        click.echo("✗ Cannot connect to API", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli(obj={})
