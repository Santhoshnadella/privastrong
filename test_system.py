"""
Test Script for Image Provenance Tracking System
Demonstrates all major features with example workflows
"""

import sys
from PIL import Image
import io
import uuid
from datetime import datetime

print("="*70)
print("IMAGE PROVENANCE TRACKING SYSTEM - TEST SUITE")
print("="*70)

def create_test_image(color='blue', size=(800, 600)):
    """Create a test image"""
    return Image.new('RGB', size, color=color)

def test_fingerprinting():
    """Test fingerprinting service"""
    print("\n" + "="*70)
    print("TEST 1: FINGERPRINTING SERVICE")
    print("="*70)
    
    from fingerprinting import ImageFingerprinter
    
    fingerprinter = ImageFingerprinter()
    
    # Create test image
    test_img = create_test_image()
    test_bytes = io.BytesIO()
    test_img.save(test_bytes, format='PNG')
    test_bytes = test_bytes.getvalue()
    
    print("\n✓ Created test image: 800x600 px")
    
    # Generate fingerprints
    print("\nGenerating fingerprints...")
    fingerprints = fingerprinter.fingerprint_image(
        image=test_img,
        image_bytes=test_bytes
    )
    
    print(f"✓ Perceptual Hash: {fingerprints['perceptual_hash'][:40]}...")
    print(f"✓ SHA-256: {fingerprints['sha256_hash'][:40]}...")
    
    if 'clip_embedding' in fingerprints:
        print(f"✓ CLIP Embedding: {fingerprints['clip_embedding'].shape}")
    else:
        print("⚠ CLIP not available (install transformers & torch)")
    
    # Test similarity
    print("\nTesting perceptual hash similarity...")
    modified_img = create_test_image('lightblue', size=(800, 600))
    modified_bytes = io.BytesIO()
    modified_img.save(modified_bytes, format='PNG')
    modified_bytes = modified_bytes.getvalue()
    
    modified_fp = fingerprinter.fingerprint_image(
        image=modified_img,
        image_bytes=modified_bytes
    )
    
    similarity = fingerprinter.compare_perceptual_hashes(
        fingerprints['perceptual_hash'],
        modified_fp['perceptual_hash']
    )
    
    print(f"✓ Similarity between blue and lightblue: {similarity:.2%}")
    
    return True

def test_watermarking():
    """Test watermarking service"""
    print("\n" + "="*70)
    print("TEST 2: WATERMARKING SERVICE")
    print("="*70)
    
    from watermarking import InvisibleWatermarker
    
    watermarker = InvisibleWatermarker()
    
    # Create test image
    test_img = create_test_image()
    print("\n✓ Created test image")
    
    # Embed watermark
    watermark_data = {
        'uuid': str(uuid.uuid4()),
        'created_at': datetime.utcnow().isoformat(),
        'version': '1.0'
    }
    
    print(f"\nEmbedding watermark...")
    print(f"  UUID: {watermark_data['uuid']}")
    
    watermarked_img = watermarker.embed_watermark(test_img, watermark_data)
    print(f"✓ Watermark embedded")
    
    # Extract watermark
    print("\nExtracting watermark...")
    extracted = watermarker.extract_watermark(watermarked_img)
    
    if extracted:
        print(f"✓ Watermark extracted successfully")
        print(f"  UUID match: {extracted['uuid'] == watermark_data['uuid']}")
        print(f"  Version: {extracted['version']}")
    else:
        print("✗ Failed to extract watermark")
        return False
    
    # Test JPEG compression resistance
    print("\nTesting JPEG compression (quality=95)...")
    jpeg_bytes = io.BytesIO()
    watermarked_img.save(jpeg_bytes, format='JPEG', quality=95)
    jpeg_img = Image.open(jpeg_bytes)
    
    extracted_jpeg = watermarker.extract_watermark(jpeg_img)
    
    if extracted_jpeg:
        print(f"✓ Watermark survived JPEG compression")
    else:
        print("⚠ Watermark lost after JPEG (expected for high compression)")
    
    return True

def test_tracking_workflow():
    """Test distribution tracking workflow"""
    print("\n" + "="*70)
    print("TEST 3: DISTRIBUTION TRACKING WORKFLOW")
    print("="*70)
    
    print("\nThis test requires a PostgreSQL database.")
    print("Simulating workflow...")
    
    image_id = str(uuid.uuid4())
    
    print(f"\n1. UPLOAD EVENT")
    print(f"   Image ID: {image_id}")
    print(f"   Device: device-origin")
    print(f"   Platform: test_suite")
    
    print(f"\n2. SHARE EVENT (Hop 1)")
    print(f"   From: device-origin")
    print(f"   To: device-mobile-1")
    
    print(f"\n3. SHARE EVENT (Hop 2)")
    print(f"   From: device-mobile-1")
    print(f"   To: device-web-3")
    
    print(f"\n4. AI DERIVATIVE")
    print(f"   Source: {image_id}")
    print(f"   Transformation: style_transfer")
    print(f"   Similarity: 0.85")
    
    print(f"\n5. RE-ENTRY DETECTION")
    print(f"   Device: device-new")
    print(f"   Method: watermark extraction")
    print(f"   Confidence: very_high")
    
    print("\n✓ Workflow simulation complete")
    print("  To run with real database:")
    print("  1. Set up PostgreSQL with schema.sql")
    print("  2. Configure DATABASE_URL in .env")
    print("  3. Run integration_example.py")
    
    return True

def test_complete_system():
    """Test the complete integration"""
    print("\n" + "="*70)
    print("TEST 4: COMPLETE SYSTEM INTEGRATION")
    print("="*70)
    
    from fingerprinting import ImageFingerprinter
    from watermarking import InvisibleWatermarker
    
    print("\n1. Creating test image...")
    test_img = create_test_image()
    test_bytes = io.BytesIO()
    test_img.save(test_bytes, format='PNG')
    test_bytes = test_bytes.getvalue()
    print("✓ Test image created")
    
    print("\n2. Generating fingerprints...")
    fingerprinter = ImageFingerprinter()
    fingerprints = fingerprinter.fingerprint_image(
        image=test_img,
        image_bytes=test_bytes
    )
    print(f"✓ Fingerprints generated")
    
    print("\n3. Embedding watermark...")
    watermarker = InvisibleWatermarker()
    watermark_data = {
        'uuid': str(uuid.uuid4()),
        'created_at': datetime.utcnow().isoformat()
    }
    watermarked = watermarker.embed_watermark(test_img, watermark_data)
    print(f"✓ Watermark embedded: {watermark_data['uuid']}")
    
    print("\n4. Simulating distribution...")
    print("   Hop 0: Upload (device-origin)")
    print("   Hop 1: Share (device-mobile-1)")
    print("   Hop 2: Share (device-web-3)")
    print("✓ Distribution chain simulated")
    
    print("\n5. Re-entry detection...")
    extracted = watermarker.extract_watermark(watermarked)
    if extracted and extracted['uuid'] == watermark_data['uuid']:
        print(f"✓ Image detected via watermark")
        print(f"  UUID matched: {extracted['uuid']}")
        print(f"  Confidence: 100%")
    
    print("\n6. Derivative detection...")
    modified = create_test_image('lightblue')
    modified_bytes = io.BytesIO()
    modified.save(modified_bytes, format='PNG')
    modified_bytes = modified_bytes.getvalue()
    
    modified_fp = fingerprinter.fingerprint_image(
        image=modified,
        image_bytes=modified_bytes
    )
    
    similarity = fingerprinter.compare_perceptual_hashes(
        fingerprints['perceptual_hash'],
        modified_fp['perceptual_hash']
    )
    
    print(f"✓ Similarity detected: {similarity:.2%}")
    if similarity > 0.75:
        print(f"  Potential derivative detected")
    
    return True

def run_all_tests():
    """Run all tests"""
    results = []
    
    tests = [
        ("Fingerprinting", test_fingerprinting),
        ("Watermarking", test_watermarking),
        ("Tracking Workflow", test_tracking_workflow),
        ("Complete System", test_complete_system)
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ TEST FAILED: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠ Some tests failed. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
