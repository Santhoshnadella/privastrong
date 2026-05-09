"""
Background Worker for Async Processing
Handles detection queue, derivative analysis, and heavy compute tasks
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import json
from PIL import Image
import io

from fingerprinting import ImageFingerprinter
from watermarking import InvisibleWatermarker
from derivative_detection import DerivativeDetector
from tracking import DistributionTracker
from osint_service import OsintService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackgroundWorker:
    """
    Async worker for processing image detection and analysis tasks
    """
    
    def __init__(self, db_url: str, redis_url: str = None):
        """
        Initialize worker with database and Redis connections
        
        Args:
            db_url: PostgreSQL connection string
            redis_url: Redis connection string (optional)
        """
        self.db = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        self.redis_client = redis.from_url(redis_url) if redis_url else None
        
        # Initialize services
        self.fingerprinter = ImageFingerprinter()
        self.watermarker = InvisibleWatermarker()
        self.tracker = DistributionTracker(self.db)
        self.derivative_detector = DerivativeDetector(self.fingerprinter, self.db)
        self.osint_service = OsintService()
        
        logger.info("Background worker initialized")
    
    async def process_detection_queue(self):
        """
        Process pending detection requests from queue
        """
        logger.info("Starting detection queue processor")
        
        while True:
            try:
                # Fetch pending detection jobs
                cursor = self.db.cursor()
                cursor.execute("""
                    SELECT id, candidate_image_hash, candidate_embedding, candidate_metadata
                    FROM detection_queue
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 10
                """)
                
                jobs = cursor.fetchall()
                
                if not jobs:
                    await asyncio.sleep(5)  # Wait before checking again
                    continue
                
                logger.info(f"Processing {len(jobs)} detection jobs")
                
                for job in jobs:
                    await self.process_detection_job(job)
                
            except Exception as e:
                logger.error(f"Error in detection queue processor: {e}")
                await asyncio.sleep(10)
    
    async def process_detection_job(self, job: Dict):
        """
        Process a single detection job
        """
        job_id = job['id']
        
        try:
            # Mark as processing
            cursor = self.db.cursor()
            cursor.execute("""
                UPDATE detection_queue
                SET status = 'processing', processing_started_at = NOW()
                WHERE id = %s
            """, (job_id,))
            self.db.commit()
            
            logger.info(f"Processing detection job {job_id}")
            
            # Simulate processing (in real implementation, fetch actual image)
            # For now, just check against existing hashes
            candidate_hash = job['candidate_image_hash']
            
            # Check for exact match
            cursor.execute(
                "SELECT id FROM images WHERE sha256_hash = %s",
                (candidate_hash,)
            )
            match = cursor.fetchone()
            
            if match:
                # Match found
                cursor.execute("""
                    UPDATE detection_queue
                    SET status = 'matched',
                        matched_image_id = %s,
                        processing_completed_at = NOW()
                    WHERE id = %s
                """, (match['id'], job_id))
                
                logger.info(f"Job {job_id}: Match found - {match['id']}")
                
                # Notify via Redis if available
                if self.redis_client:
                    self.redis_client.publish(
                        'detection_matches',
                        json.dumps({
                            'job_id': job_id,
                            'matched_image_id': match['id'],
                            'timestamp': datetime.utcnow().isoformat()
                        })
                    )
            else:
                # No match
                cursor.execute("""
                    UPDATE detection_queue
                    SET status = 'no_match',
                        processing_completed_at = NOW()
                    WHERE id = %s
                """, (job_id,))
                
                logger.info(f"Job {job_id}: No match found")
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            
            # Mark as failed
            cursor = self.db.cursor()
            cursor.execute("""
                UPDATE detection_queue
                SET status = 'pending',
                    processing_started_at = NULL
                WHERE id = %s
            """, (job_id,))
            self.db.commit()
    
    async def analyze_derivatives(self):
        """
        Periodically analyze images for new derivatives
        """
        logger.info("Starting derivative analyzer")
        
        while True:
            try:
                # Get recent images that haven't been analyzed in the last 24 hours
                cursor = self.db.cursor()
                cursor.execute("""
                    SELECT i.id, i.storage_path, i.perceptual_hash, i.clip_embedding
                    FROM images i
                    LEFT JOIN ai_derivatives ad ON ad.source_image_id = i.id
                    WHERE i.created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY i.id
                    HAVING MAX(ad.detected_at) IS NULL 
                        OR MAX(ad.detected_at) < NOW() - INTERVAL '24 hours'
                    LIMIT 20
                """)
                
                images = cursor.fetchall()
                
                if not images:
                    await asyncio.sleep(300)  # Wait 5 minutes
                    continue
                
                logger.info(f"Analyzing {len(images)} images for derivatives")
                
                for image in images:
                    await self.check_for_derivatives(image)
                
                await asyncio.sleep(300)  # Wait 5 minutes before next batch
                
            except Exception as e:
                logger.error(f"Error in derivative analyzer: {e}")
                await asyncio.sleep(60)
    
    async def check_for_derivatives(self, source_image: Dict):
        """
        Check if an image has new derivatives
        """
        source_id = source_image['id']
        
        try:
            # Find similar images that aren't already marked as derivatives
            cursor = self.db.cursor()
            
            if source_image['clip_embedding']:
                # Use CLIP similarity
                cursor.execute("""
                    SELECT id, clip_embedding,
                           1 - (clip_embedding <=> %s::vector) as similarity
                    FROM images
                    WHERE id != %s
                    AND id NOT IN (
                        SELECT derivative_image_id 
                        FROM ai_derivatives 
                        WHERE source_image_id = %s
                    )
                    AND 1 - (clip_embedding <=> %s::vector) >= 0.75
                    ORDER BY clip_embedding <=> %s::vector
                    LIMIT 10
                """, (
                    source_image['clip_embedding'], source_id, source_id,
                    source_image['clip_embedding'], source_image['clip_embedding']
                ))
                
                candidates = cursor.fetchall()
                
                for candidate in candidates:
                    # Record as potential derivative
                    self.derivative_detector.record_derivative(
                        source_image_id=source_id,
                        derivative_image_id=candidate['id'],
                        similarity_score=candidate['similarity'],
                        detection_method='automatic_clip',
                        transformation_type='unknown'
                    )
                    
                    logger.info(
                        f"New derivative detected: {candidate['id']} "
                        f"(similarity: {candidate['similarity']:.2f})"
                    )
        
        except Exception as e:
            logger.error(f"Error checking derivatives for {source_id}: {e}")
    
    async def cleanup_old_records(self):
        """
        Cleanup old processed detection queue entries
        """
        logger.info("Starting cleanup task")
        
        while True:
            try:
                cursor = self.db.cursor()
                
                # Delete old completed/no_match detection queue entries
                cursor.execute("""
                    DELETE FROM detection_queue
                    WHERE status IN ('matched', 'no_match')
                    AND processing_completed_at < NOW() - INTERVAL '30 days'
                """)
                
                deleted = cursor.rowcount
                self.db.commit()
                
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old detection queue entries")
                
                # Cleanup old audit logs (keep 90 days)
                cursor.execute("""
                    DELETE FROM audit_log
                    WHERE changed_at < NOW() - INTERVAL '90 days'
                """)
                
                deleted = cursor.rowcount
                self.db.commit()
                
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old audit log entries")
                
                # Wait 24 hours before next cleanup
                await asyncio.sleep(86400)
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour
    
    async def refresh_materialized_views(self):
        """
        Refresh materialized views periodically
        """
        logger.info("Starting materialized view refresh task")
        
        while True:
            try:
                cursor = self.db.cursor()
                cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY image_lineage")
                self.db.commit()
                
                logger.info("Refreshed image_lineage materialized view")
                
                # Wait 1 hour before next refresh
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error refreshing materialized views: {e}")
                await asyncio.sleep(600)  # Retry in 10 minutes

    async def osint_scan(self):
        """
        Periodically scan the web for tracked images via OSINT service
        """
        logger.info("Starting OSINT scanner")
        
        while True:
            try:
                # Get images that haven't been scanned for OSINT in the last 7 days
                # Or images that are marked as "high priority" for tracking
                cursor = self.db.cursor()
                cursor.execute("""
                    SELECT i.id, i.storage_path, i.cdn_url
                    FROM images i
                    LEFT JOIN external_detections ed ON ed.image_id = i.id
                    GROUP BY i.id
                    HAVING MAX(ed.detected_at) IS NULL 
                        OR MAX(ed.detected_at) < NOW() - INTERVAL '7 days'
                    LIMIT 5
                """)
                
                images = cursor.fetchall()
                
                if not images:
                    await asyncio.sleep(3600)  # Wait 1 hour
                    continue
                
                logger.info(f"Performing OSINT scan for {len(images)} images")
                
                for image in images:
                    # Perform web search
                    # In production, use CDN URL for external services to fetch
                    matches = await self.osint_service.search_web(
                        image_url=image['cdn_url'],
                        image_bytes=None # Would fetch from storage_path in production
                    )
                    
                    if matches:
                        logger.info(f"Found {len(matches)} web matches for image {image['id']}")
                        
                        for match in matches:
                            # Record external detection
                            cursor.execute("""
                                INSERT INTO external_detections (
                                    image_id, source_url, detection_method,
                                    similarity_score, page_title, site_name
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (
                                image['id'], match['source_url'], match['detection_method'],
                                match['similarity'], match.get('page_title'), match.get('site_name')
                            ))
                            
                        self.db.commit()
                
                # Wait before next batch to avoid API rate limits
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in OSINT scanner: {e}")
                await asyncio.sleep(600)

    async def run(self):
        """
        Run all worker tasks concurrently
        """
        logger.info("Starting all background tasks")
        
        tasks = [
            asyncio.create_task(self.process_detection_queue()),
            asyncio.create_task(self.analyze_derivatives()),
            asyncio.create_task(self.cleanup_old_records()),
            asyncio.create_task(self.refresh_materialized_views()),
            asyncio.create_task(self.osint_scan())
        ]
        
        await asyncio.gather(*tasks)
    
    def close(self):
        """Close connections"""
        self.db.close()
        if self.redis_client:
            self.redis_client.close()


async def main():
    """Main entry point"""
    import os
    
    db_url = os.getenv(
        'DATABASE_URL',
        'postgresql://provenance_user:password@localhost/image_provenance'
    )
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    logger.info("Initializing background worker")
    worker = BackgroundWorker(db_url, redis_url)
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Shutting down worker")
    finally:
        worker.close()


if __name__ == "__main__":
    asyncio.run(main())
