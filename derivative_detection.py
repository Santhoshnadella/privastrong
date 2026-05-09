"""
AI Derivative Detection Service
Detects when an image has been used to generate AI-modified versions
"""

import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional
import io


class DerivativeDetector:
    """
    Detects AI-generated derivatives using multiple similarity techniques
    """
    
    def __init__(self, fingerprinter, db_connection):
        """
        Args:
            fingerprinter: ImageFingerprinter instance
            db_connection: Database connection
        """
        self.fingerprinter = fingerprinter
        self.db = db_connection
    
    def detect_similarity(self, 
                         candidate_image: Image.Image,
                         candidate_bytes: bytes,
                         similarity_threshold: float = 0.75) -> List[Dict]:
        """
        Detect if candidate image matches or derives from any tracked images
        
        Args:
            candidate_image: PIL Image to check
            candidate_bytes: Raw image bytes
            similarity_threshold: Minimum similarity to report
            
        Returns:
            List of matches with similarity scores
        """
        matches = []
        
        # Generate fingerprints for candidate
        candidate_fp = self.fingerprinter.fingerprint_image(
            image=candidate_image,
            image_bytes=candidate_bytes
        )
        
        # Method 1: Exact SHA-256 match
        exact_match = self._check_exact_match(candidate_fp['sha256_hash'])
        if exact_match:
            matches.append({
                'image_id': exact_match,
                'method': 'sha256_exact',
                'similarity': 1.0,
                'confidence': 'very_high'
            })
            return matches  # Exact match found, return immediately
        
        # Method 2: Perceptual hash similarity
        phash_matches = self._check_perceptual_hash(
            candidate_fp['perceptual_hash'],
            threshold=similarity_threshold
        )
        matches.extend(phash_matches)
        
        # Method 3: CLIP embedding similarity
        if 'clip_embedding' in candidate_fp:
            clip_matches = self._check_clip_similarity(
                candidate_fp['clip_embedding'],
                threshold=similarity_threshold
            )
            matches.extend(clip_matches)
        
        # Deduplicate and sort by similarity
        matches = self._deduplicate_matches(matches)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        return matches
    
    def _check_exact_match(self, sha256_hash: str) -> Optional[str]:
        """Check for exact SHA-256 match"""
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT id FROM images WHERE sha256_hash = %s",
            (sha256_hash,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def _check_perceptual_hash(self, 
                               phash: str, 
                               threshold: float = 0.75) -> List[Dict]:
        """
        Check perceptual hash against all images
        
        Note: In production, use locality-sensitive hashing (LSH) for scale
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT id, perceptual_hash FROM images")
        
        matches = []
        for image_id, stored_hash in cursor.fetchall():
            similarity = self.fingerprinter.compare_perceptual_hashes(phash, stored_hash)
            
            if similarity >= threshold:
                confidence = 'high' if similarity >= 0.9 else 'medium'
                matches.append({
                    'image_id': image_id,
                    'method': 'perceptual_hash',
                    'similarity': similarity,
                    'confidence': confidence
                })
        
        return matches
    
    def _check_clip_similarity(self, 
                              embedding: np.ndarray,
                              threshold: float = 0.75) -> List[Dict]:
        """
        Check CLIP embedding similarity using vector search
        
        Uses pgvector cosine similarity search
        """
        cursor = self.db.cursor()
        
        # Convert embedding to PostgreSQL vector format
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Vector similarity search with pgvector
        cursor.execute("""
            SELECT id, clip_embedding, 
                   1 - (clip_embedding <=> %s::vector) as similarity
            FROM images
            WHERE 1 - (clip_embedding <=> %s::vector) >= %s
            ORDER BY clip_embedding <=> %s::vector
            LIMIT 20
        """, (embedding_str, embedding_str, threshold, embedding_str))
        
        matches = []
        for image_id, stored_embedding, similarity in cursor.fetchall():
            confidence = 'high' if similarity >= 0.9 else 'medium' if similarity >= 0.8 else 'low'
            matches.append({
                'image_id': image_id,
                'method': 'clip_embedding',
                'similarity': float(similarity),
                'confidence': confidence
            })
        
        return matches
    
    def _deduplicate_matches(self, matches: List[Dict]) -> List[Dict]:
        """
        Deduplicate matches - keep highest similarity per image
        """
        seen = {}
        for match in matches:
            image_id = match['image_id']
            if image_id not in seen or match['similarity'] > seen[image_id]['similarity']:
                seen[image_id] = match
        
        return list(seen.values())
    
    def detect_partial_usage(self, 
                            candidate_image: Image.Image,
                            source_image_id: str,
                            grid_size: int = 8) -> Dict:
        """
        Detect if portions of a source image are used in candidate
        
        Uses patch-based matching
        
        Args:
            candidate_image: Image to analyze
            source_image_id: Source image ID to compare against
            grid_size: Grid divisions for patch matching
            
        Returns:
            Dictionary with matched regions and confidence
        """
        # Load source image
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT storage_path FROM images WHERE id = %s",
            (source_image_id,)
        )
        result = cursor.fetchone()
        if not result:
            return {'matched': False}
        
        source_image = Image.open(result[0])
        
        # Divide both images into patches
        candidate_patches = self._extract_patches(candidate_image, grid_size)
        source_patches = self._extract_patches(source_image, grid_size)
        
        # Compare patches
        matched_regions = []
        for i, cand_patch in enumerate(candidate_patches):
            for j, src_patch in enumerate(source_patches):
                similarity = self._compare_patches(cand_patch, src_patch)
                
                if similarity > 0.8:  # High similarity threshold
                    matched_regions.append({
                        'candidate_patch': i,
                        'source_patch': j,
                        'similarity': similarity
                    })
        
        if len(matched_regions) > 0:
            avg_similarity = np.mean([r['similarity'] for r in matched_regions])
            coverage = len(matched_regions) / len(source_patches)
            
            return {
                'matched': True,
                'regions': matched_regions,
                'average_similarity': float(avg_similarity),
                'coverage_percentage': float(coverage * 100),
                'confidence': 'high' if avg_similarity > 0.9 else 'medium'
            }
        
        return {'matched': False}
    
    def _extract_patches(self, image: Image.Image, grid_size: int) -> List[np.ndarray]:
        """Extract image patches for comparison"""
        img_array = np.array(image)
        h, w = img_array.shape[:2]
        
        patch_h = h // grid_size
        patch_w = w // grid_size
        
        patches = []
        for i in range(grid_size):
            for j in range(grid_size):
                patch = img_array[
                    i*patch_h:(i+1)*patch_h,
                    j*patch_w:(j+1)*patch_w
                ]
                patches.append(patch)
        
        return patches
    
    def _compare_patches(self, patch1: np.ndarray, patch2: np.ndarray) -> float:
        """
        Compare two image patches using normalized cross-correlation
        """
        # Resize to same size if needed
        if patch1.shape != patch2.shape:
            patch2 = np.array(Image.fromarray(patch2).resize(
                (patch1.shape[1], patch1.shape[0])
            ))
        
        # Normalize
        patch1_norm = (patch1 - np.mean(patch1)) / (np.std(patch1) + 1e-8)
        patch2_norm = (patch2 - np.mean(patch2)) / (np.std(patch2) + 1e-8)
        
        # Compute correlation
        correlation = np.mean(patch1_norm * patch2_norm)
        
        # Map to [0, 1]
        similarity = (correlation + 1) / 2
        
        return float(np.clip(similarity, 0, 1))
    
    def record_derivative(self,
                         source_image_id: str,
                         derivative_image_id: str,
                         similarity_score: float,
                         detection_method: str,
                         ai_model: Optional[str] = None,
                         transformation_type: Optional[str] = None,
                         portion_used: Optional[Dict] = None) -> str:
        """
        Record a detected AI derivative in the database
        """
        import uuid
        import json
        
        derivative_id = str(uuid.uuid4())
        
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO ai_derivatives (
                id, source_image_id, derivative_image_id,
                similarity_score, detection_method, ai_model_used,
                transformation_type, portion_used
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            derivative_id, source_image_id, derivative_image_id,
            similarity_score, detection_method, ai_model,
            transformation_type, json.dumps(portion_used) if portion_used else None
        ))
        
        self.db.commit()
        return derivative_id


# Example usage
if __name__ == "__main__":
    from fingerprinting import ImageFingerprinter
    
    print("AI Derivative Detection Example\n")
    
    # Mock database
    class MockDB:
        def cursor(self):
            return self
        def execute(self, *args):
            print(f"  SQL Query: {args[0][:60]}...")
        def fetchone(self):
            return None
        def fetchall(self):
            return []
        def commit(self):
            pass
    
    fingerprinter = ImageFingerprinter()
    detector = DerivativeDetector(fingerprinter, MockDB())
    
    # Create test images
    original = Image.new('RGB', (800, 600), color='blue')
    modified = Image.new('RGB', (800, 600), color='lightblue')  # Slightly modified
    
    print("Detecting similarity between original and modified images...")
    
    # Convert to bytes
    orig_bytes = io.BytesIO()
    original.save(orig_bytes, format='PNG')
    orig_bytes = orig_bytes.getvalue()
    
    matches = detector.detect_similarity(modified, orig_bytes, similarity_threshold=0.7)
    
    print(f"\nDetection complete. Found {len(matches)} potential matches.")
    
    for match in matches:
        print(f"  - Method: {match['method']}, Similarity: {match['similarity']:.2f}, Confidence: {match['confidence']}")
