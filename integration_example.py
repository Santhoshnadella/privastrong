"""
Complete Integration Example
Demonstrates the full image provenance tracking workflow
"""

from PIL import Image
import io
import uuid
from datetime import datetime
import psycopg2

# Import all services
from fingerprinting import ImageFingerprinter
from watermarking import InvisibleWatermarker
from tracking import DistributionTracker
from derivative_detection import DerivativeDetector
from reentry_detection import ReentryDetector


class ImageProvenanceSystem:
    """
    Complete integration of all components
    """
    
    def __init__(self, db_connection_string: str):
        """
        Initialize the complete system
        
        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db = psycopg2.connect(db_connection_string)
        
        # Initialize all services
        self.fingerprinter = ImageFingerprinter()
        self.watermarker = InvisibleWatermarker()
        self.tracker = DistributionTracker(self.db)
        self.derivative_detector = DerivativeDetector(self.fingerprinter, self.db)
        self.reentry_detector = ReentryDetector(
            self.watermarker,
            self.fingerprinter,
            self.derivative_detector,
            self.tracker,
            self.db
        )
    
    def upload_and_track_image(self, 
                               image_path: str,
                               uploaded_by: str,
                               device_id: str) -> dict:
        """
        Complete upload workflow:
        1. Load image
        2. Generate fingerprints
        3. Embed watermark
        4. Store in database
        5. Record upload event
        
        Returns:
            Dictionary with image_id and all tracking data
        """
        print(f"\n{'='*60}")
        print("STEP 1: UPLOAD AND REGISTER IMAGE")
        print(f"{'='*60}")
        
        # Load image
        image = Image.open(image_path)
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        print(f"✓ Loaded image: {image.size[0]}x{image.size[1]}")
        
        # Generate fingerprints
        print("\nGenerating fingerprints...")
        fingerprints = self.fingerprinter.fingerprint_image(
            image=image,
            image_bytes=image_bytes
        )
        print(f"✓ Perceptual hash: {fingerprints['perceptual_hash'][:32]}...")
        print(f"✓ SHA-256: {fingerprints['sha256_hash'][:32]}...")
        if 'clip_embedding' in fingerprints:
            print(f"✓ CLIP embedding: {fingerprints['clip_embedding'].shape}")
        
        # Generate IDs
        image_id = str(uuid.uuid4())
        watermark_id = str(uuid.uuid4())
        
        # Embed watermark
        print("\nEmbedding invisible watermark...")
        watermark_data = {
            'uuid': watermark_id,
            'created_at': datetime.utcnow().isoformat(),
            'version': '1.0',
            'uploaded_by': uploaded_by
        }
        watermarked_image = self.watermarker.embed_watermark(image, watermark_data)
        print(f"✓ Watermark embedded with UUID: {watermark_id}")
        
        # Store in database
        print("\nStoring in database...")
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
            image_id, image_path.split('/')[-1], watermark_id,
            fingerprints['perceptual_hash'], fingerprints['sha256_hash'],
            fingerprints.get('clip_embedding').tolist() if 'clip_embedding' in fingerprints else None,
            len(image_bytes), 'image/png',
            fingerprints['width'], fingerprints['height'],
            f"/storage/{image_id}.png", uploaded_by
        ))
        
        # Record upload event
        event_id = self.tracker.record_event(
            image_id=image_id,
            event_type='upload',
            device_fingerprint=device_id,
            platform='integration_example',
            metadata={'original_filename': image_path}
        )
        
        self.db.commit()
        print(f"✓ Stored in database with ID: {image_id}")
        print(f"✓ Upload event recorded: {event_id}")
        
        return {
            'image_id': image_id,
            'watermark_id': watermark_id,
            'fingerprints': fingerprints,
            'watermarked_image': watermarked_image
        }
    
    def share_image(self, 
                   image_id: str,
                   from_device: str,
                   to_device: str,
                   source_event_id: str = None) -> str:
        """
        Record image sharing between devices
        """
        print(f"\n{'='*60}")
        print("STEP 2: SHARE IMAGE")
        print(f"{'='*60}")
        
        print(f"Sharing from {from_device} to {to_device}...")
        
        event_id = self.tracker.record_event(
            image_id=image_id,
            event_type='share',
            device_fingerprint=to_device,
            platform='integration_example',
            source_event_id=source_event_id,
            metadata={
                'from_device': from_device,
                'to_device': to_device,
                'share_method': 'direct'
            }
        )
        
        print(f"✓ Share event recorded: {event_id}")
        print(f"✓ Hop chain extended")
        
        return event_id
    
    def create_ai_derivative(self,
                            source_image_id: str,
                            transformation: str = 'style_transfer') -> dict:
        """
        Simulate AI derivative creation
        """
        print(f"\n{'='*60}")
        print("STEP 3: CREATE AI DERIVATIVE")
        print(f"{'='*60}")
        
        print(f"Creating {transformation} derivative...")
        
        # In real scenario, you'd call an AI model here
        # For demo, we'll create a modified version
        
        # Get original image
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT storage_path FROM images WHERE id = %s",
            (source_image_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            raise ValueError("Source image not found")
        
        # Create derivative (simplified)
        derivative_id = str(uuid.uuid4())
        watermark_id = str(uuid.uuid4())
        
        print(f"✓ Generated derivative ID: {derivative_id}")
        
        # Record derivative relationship
        self.derivative_detector.record_derivative(
            source_image_id=source_image_id,
            derivative_image_id=derivative_id,
            similarity_score=0.85,
            detection_method='manual_creation',
            ai_model='style_transfer_model',
            transformation_type=transformation
        )
        
        print(f"✓ Derivative relationship recorded")
        print(f"✓ Similarity score: 0.85")
        
        return {
            'derivative_id': derivative_id,
            'source_id': source_image_id,
            'transformation': transformation
        }
    
    def detect_reentry(self,
                      image: Image.Image,
                      image_bytes: bytes,
                      device_id: str) -> dict:
        """
        Detect when image re-enters the network
        """
        print(f"\n{'='*60}")
        print("STEP 4: DETECT RE-ENTRY")
        print(f"{'='*60}")
        
        print("Analyzing image with multi-method detection...")
        
        context = {
            'device_id': device_id,
            'platform': 'integration_example'
        }
        
        result = self.reentry_detector.detect_image(
            image, image_bytes, context
        )
        
        print(f"\n{'='*40}")
        print("DETECTION RESULTS")
        print(f"{'='*40}")
        
        if result['detected']:
            print(f"✓ IMAGE DETECTED!")
            print(f"  Confidence: {result['confidence']}")
            print(f"  Methods used: {', '.join(result['methods'])}")
            
            for match in result['matches']:
                print(f"\n  Match via {match.get('method', 'unknown')}:")
                print(f"    Image ID: {match.get('image_id', 'N/A')}")
                if 'similarity' in match:
                    print(f"    Similarity: {match['similarity']:.2%}")
            
            if result['lineage']:
                lineage = result['lineage']
                print(f"\n  Lineage Statistics:")
                stats = lineage.get('statistics', {})
                print(f"    Total events: {stats.get('total_events', 0)}")
                print(f"    Unique devices: {stats.get('unique_devices', 0)}")
                print(f"    Max hop depth: {stats.get('max_hop_depth', 0)}")
        else:
            print("✗ No match found - image not in tracking system")
        
        return result
    
    def get_complete_lineage(self, image_id: str) -> dict:
        """
        Retrieve complete lineage visualization
        """
        print(f"\n{'='*60}")
        print("STEP 5: RETRIEVE COMPLETE LINEAGE")
        print(f"{'='*60}")
        
        lineage = self.tracker.build_lineage_graph(image_id)
        
        print(f"\nLineage for image {image_id}:")
        print(f"  Nodes: {len(lineage['nodes'])}")
        print(f"  Edges: {len(lineage['edges'])}")
        
        stats = lineage['statistics']
        print(f"\n  Statistics:")
        print(f"    Total hops: {stats['total_events']}")
        print(f"    Unique devices: {stats['unique_devices']}")
        print(f"    Max depth: {stats['max_hop_depth']}")
        
        if stats.get('event_breakdown'):
            print(f"\n  Event breakdown:")
            for event_type, count in stats['event_breakdown'].items():
                print(f"    {event_type}: {count}")
        
        return lineage
    
    def close(self):
        """Close database connection"""
        self.db.close()


def run_complete_demo():
    """
    Run a complete end-to-end demonstration
    """
    print("\n" + "="*60)
    print("IMAGE PROVENANCE TRACKING SYSTEM - COMPLETE DEMO")
    print("="*60)
    
    # Initialize system (replace with your connection string)
    # system = ImageProvenanceSystem(
    #     "postgresql://user:password@localhost/image_provenance"
    # )
    
    print("\nThis demo would execute the following workflow:")
    print("\n1. UPLOAD IMAGE")
    print("   - Load image file")
    print("   - Generate perceptual hash, SHA-256, CLIP embedding")
    print("   - Embed invisible watermark with UUID")
    print("   - Store in database with all fingerprints")
    print("   - Record upload event")
    
    print("\n2. SHARE ACROSS DEVICES")
    print("   - Device A → Device B (Hop 1)")
    print("   - Device B → Device C (Hop 2)")
    print("   - Device C → Device D (Hop 3)")
    print("   - Each hop recorded with device hash, timestamp, platform")
    
    print("\n3. CREATE AI DERIVATIVES")
    print("   - Generate style-transferred version")
    print("   - Detect similarity (85% match)")
    print("   - Link derivative to original")
    print("   - Record in ai_derivatives table")
    
    print("\n4. DETECT RE-ENTRY")
    print("   - Image appears on new device")
    print("   - Extract watermark → 100% match")
    print("   - If watermark stripped:")
    print("     • Check perceptual hash → 98% match")
    print("     • Check CLIP embedding → 94% match")
    print("   - Retrieve complete lineage")
    
    print("\n5. VISUALIZE LINEAGE")
    print("   - Show all hops chronologically")
    print("   - Display hop graph with devices")
    print("   - List all derivatives")
    print("   - Show statistics")
    
    print("\n" + "="*60)
    print("To run with real database:")
    print("1. Set up PostgreSQL with schema.sql")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Update connection string in this file")
    print("4. Run: python integration_example.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_complete_demo()
    
    # Example usage with actual system:
    # system = ImageProvenanceSystem("postgresql://...")
    # 
    # # Upload image
    # result = system.upload_and_track_image(
    #     image_path="/path/to/image.jpg",
    #     uploaded_by="user_123",
    #     device_id="device_origin"
    # )
    # 
    # # Share between devices
    # event1 = system.share_image(
    #     image_id=result['image_id'],
    #     from_device="device_origin",
    #     to_device="device_mobile_1"
    # )
    # 
    # # Create derivative
    # derivative = system.create_ai_derivative(
    #     source_image_id=result['image_id'],
    #     transformation="style_transfer"
    # )
    # 
    # # Detect re-entry
    # detection = system.detect_reentry(
    #     image=result['watermarked_image'],
    #     image_bytes=...,
    #     device_id="device_new"
    # )
    # 
    # # Get lineage
    # lineage = system.get_complete_lineage(result['image_id'])
    # 
    # system.close()
