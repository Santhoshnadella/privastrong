"""
Re-entry Detection Service
Identifies when a tracked image re-appears in the network
"""

from PIL import Image
from typing import Dict, List, Optional, Tuple
import uuid
from datetime import datetime
import json


class ReentryDetector:
    """
    Detects when an image re-enters the tracking network
    Combines watermark extraction, hash matching, and similarity detection
    """
    
    def __init__(self, watermarker, fingerprinter, derivative_detector, tracker, db_connection):
        """
        Args:
            watermarker: InvisibleWatermarker instance
            fingerprinter: ImageFingerprinter instance
            derivative_detector: DerivativeDetector instance
            tracker: DistributionTracker instance
            db_connection: Database connection
        """
        self.watermarker = watermarker
        self.fingerprinter = fingerprinter
        self.derivative_detector = derivative_detector
        self.tracker = tracker
        self.db = db_connection
    
    def detect_image(self, 
                    image: Image.Image,
                    image_bytes: bytes,
                    context: Optional[Dict] = None) -> Dict:
        """
        Comprehensive detection pipeline for re-entered images
        
        Args:
            image: PIL Image object
            image_bytes: Raw image bytes
            context: Additional context (device, platform, etc.)
            
        Returns:
            Detection result with match information and lineage
        """
        detection_result = {
            'detected': False,
            'detection_time': datetime.utcnow().isoformat(),
            'methods': [],
            'matches': [],
            'lineage': None,
            'confidence': 'none'
        }
        
        # Method 1: Extract watermark (highest confidence)
        watermark_result = self._check_watermark(image)
        if watermark_result['found']:
            detection_result['detected'] = True
            detection_result['methods'].append('watermark')
            detection_result['matches'].append(watermark_result)
            detection_result['confidence'] = 'very_high'
            
            # Retrieve full lineage
            image_id = watermark_result['image_id']
            detection_result['lineage'] = self._retrieve_lineage(image_id)
            
            # Record re-entry event
            self._record_reentry_event(image_id, 'watermark', context)
            
            return detection_result
        
        # Method 2: Hash-based detection
        hash_result = self._check_hashes(image, image_bytes)
        if hash_result['found']:
            detection_result['detected'] = True
            detection_result['methods'].append('hash')
            detection_result['matches'].append(hash_result)
            detection_result['confidence'] = 'high'
            
            image_id = hash_result['image_id']
            detection_result['lineage'] = self._retrieve_lineage(image_id)
            
            self._record_reentry_event(image_id, 'hash', context)
            
            return detection_result
        
        # Method 3: Similarity-based detection (AI derivatives)
        similarity_results = self._check_similarity(image, image_bytes)
        if similarity_results:
            detection_result['detected'] = True
            detection_result['methods'].append('similarity')
            detection_result['matches'].extend(similarity_results)
            
            # Use highest similarity match
            best_match = max(similarity_results, key=lambda x: x['similarity'])
            detection_result['confidence'] = best_match['confidence']
            
            image_id = best_match['image_id']
            detection_result['lineage'] = self._retrieve_lineage(image_id)
            
            # Check if this is a derivative
            if best_match['similarity'] < 0.95:
                detection_result['is_derivative'] = True
                self._record_derivative(image_id, best_match, image, image_bytes)
            
            self._record_reentry_event(image_id, 'similarity', context)
        
        return detection_result
    
    def _check_watermark(self, image: Image.Image) -> Dict:
        """Extract and verify watermark"""
        watermark_data = self.watermarker.extract_watermark(image)
        
        if watermark_data and 'uuid' in watermark_data:
            # Verify watermark UUID exists in database
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT id FROM images WHERE watermark_id = %s",
                (watermark_data['uuid'],)
            )
            result = cursor.fetchone()
            
            if result:
                return {
                    'found': True,
                    'method': 'watermark',
                    'image_id': result[0],
                    'watermark_data': watermark_data,
                    'confidence': 'very_high'
                }
        
        return {'found': False}
    
    def _check_hashes(self, image: Image.Image, image_bytes: bytes) -> Dict:
        """Check perceptual and SHA-256 hashes"""
        fingerprints = self.fingerprinter.fingerprint_image(
            image=image,
            image_bytes=image_bytes
        )
        
        # Check exact SHA-256 match first
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT id FROM images WHERE sha256_hash = %s",
            (fingerprints['sha256_hash'],)
        )
        result = cursor.fetchone()
        
        if result:
            return {
                'found': True,
                'method': 'sha256_exact',
                'image_id': result[0],
                'similarity': 1.0,
                'confidence': 'very_high'
            }
        
        # Check perceptual hash with high threshold
        cursor.execute("SELECT id, perceptual_hash FROM images")
        
        for image_id, stored_hash in cursor.fetchall():
            similarity = self.fingerprinter.compare_perceptual_hashes(
                fingerprints['perceptual_hash'],
                stored_hash
            )
            
            if similarity >= 0.95:  # Very high threshold for hash matching
                return {
                    'found': True,
                    'method': 'perceptual_hash',
                    'image_id': image_id,
                    'similarity': similarity,
                    'confidence': 'high'
                }
        
        return {'found': False}
    
    def _check_similarity(self, image: Image.Image, image_bytes: bytes) -> List[Dict]:
        """Check similarity-based matches"""
        matches = self.derivative_detector.detect_similarity(
            image,
            image_bytes,
            similarity_threshold=0.75
        )
        
        return matches
    
    def _retrieve_lineage(self, image_id: str) -> Dict:
        """Retrieve complete lineage including hops and derivatives"""
        lineage = self.tracker.build_lineage_graph(image_id)
        
        # Add image metadata
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT 
                original_filename, watermark_id, created_at,
                uploaded_by, width, height
            FROM images
            WHERE id = %s
        """, (image_id,))
        
        result = cursor.fetchone()
        if result:
            lineage['original_image'] = {
                'id': image_id,
                'filename': result[0],
                'watermark_id': result[1],
                'created_at': result[2].isoformat() if result[2] else None,
                'uploaded_by': result[3],
                'dimensions': f"{result[4]}x{result[5]}"
            }
        
        return lineage
    
    def _record_reentry_event(self, 
                              image_id: str, 
                              detection_method: str,
                              context: Optional[Dict] = None):
        """Record that image has re-entered the network"""
        metadata = {
            'detection_method': detection_method,
            'reentry': True
        }
        
        if context:
            metadata.update(context)
        
        self.tracker.record_event(
            image_id=image_id,
            event_type='detection',
            device_fingerprint=context.get('device_id') if context else None,
            ip_address=context.get('ip_address') if context else None,
            platform=context.get('platform') if context else None,
            metadata=metadata
        )
    
    def _record_derivative(self,
                          source_image_id: str,
                          match_info: Dict,
                          derivative_image: Image.Image,
                          derivative_bytes: bytes):
        """Record a newly discovered derivative"""
        # Store derivative as new image
        derivative_id = str(uuid.uuid4())
        watermark_id = str(uuid.uuid4())
        
        fingerprints = self.fingerprinter.fingerprint_image(
            image=derivative_image,
            image_bytes=derivative_bytes
        )
        
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO images (
                id, original_filename, watermark_id,
                perceptual_hash, sha256_hash, clip_embedding,
                file_size, mime_type, width, height,
                storage_path, uploaded_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            derivative_id, f"derivative_{derivative_id[:8]}.png",
            watermark_id, fingerprints['perceptual_hash'],
            fingerprints['sha256_hash'], 
            fingerprints.get('clip_embedding').tolist() if 'clip_embedding' in fingerprints else None,
            len(derivative_bytes), 'image/png',
            fingerprints['width'], fingerprints['height'],
            f"/storage/derivatives/{derivative_id}.png",
            None  # System-detected derivative
        ))
        
        # Record derivative relationship
        self.derivative_detector.record_derivative(
            source_image_id=source_image_id,
            derivative_image_id=derivative_id,
            similarity_score=match_info['similarity'],
            detection_method=match_info['method']
        )
        
        self.db.commit()
    
    def batch_detect(self, images: List[Tuple[Image.Image, bytes, Dict]]) -> List[Dict]:
        """
        Batch detection for multiple images
        
        Args:
            images: List of (image, bytes, context) tuples
            
        Returns:
            List of detection results
        """
        results = []
        
        for image, image_bytes, context in images:
            result = self.detect_image(image, image_bytes, context)
            results.append(result)
        
        return results
    
    def get_detection_statistics(self, time_window_days: int = 30) -> Dict:
        """Get statistics on recent detections"""
        cursor = self.db.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT image_id) as unique_images,
                metadata->>'detection_method' as method
            FROM distribution_events
            WHERE event_type = 'detection'
            AND created_at >= NOW() - INTERVAL '%s days'
            GROUP BY metadata->>'detection_method'
        """, (time_window_days,))
        
        stats = {
            'total_detections': 0,
            'unique_images_detected': 0,
            'detection_methods': {}
        }
        
        for total, unique, method in cursor.fetchall():
            stats['total_detections'] += total
            stats['detection_methods'][method or 'unknown'] = {
                'count': total,
                'unique_images': unique
            }
        
        return stats


# Example usage
if __name__ == "__main__":
    print("Re-entry Detection Example\n")
    
    # This would require all components initialized
    print("This service integrates:")
    print("  1. Watermark extraction")
    print("  2. Hash-based matching") 
    print("  3. Similarity detection")
    print("  4. Lineage retrieval")
    print("  5. Event recording")
    
    print("\nExample flow:")
    print("  → Image re-enters network")
    print("  → System extracts watermark (100% confidence)")
    print("  → Retrieves complete lineage from database")
    print("  → Shows all hops, derivatives, and timeline")
    print("  → Records detection event")
