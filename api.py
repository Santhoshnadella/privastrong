"""
Image Provenance Tracking API
FastAPI implementation with all endpoints
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from datetime import datetime
import io
from PIL import Image
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import redis
import time
from prometheus_client import Counter, Histogram, generate_latest

# Import our services
from fingerprinting import ImageFingerprinter
from watermarking import InvisibleWatermarker
from tracking import DistributionTracker
from derivative_detection import DerivativeDetector
from reentry_detection import ReentryDetector
from blockchain_service import BlockchainService
from security import get_current_user, check_permissions, User, create_access_token
from config import Config


app = FastAPI(
    title="Image Provenance Tracking API",
    description="AI-aware image tracking with lineage and derivative detection",
    version="1.0.0"
)


class Token(BaseModel):
    access_token: str
    token_type: str


# Pydantic models
class ImageUploadResponse(BaseModel):
    image_id: str
    watermark_id: str
    fingerprints: Dict
    storage_url: str
    created_at: str


class EventContext(BaseModel):
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    platform: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict] = None


class ShareRequest(BaseModel):
    image_id: str
    context: EventContext
    source_event_id: Optional[str] = None


class DetectionResponse(BaseModel):
    detected: bool
    detection_time: str
    methods: List[str]
    matches: List[Dict]
    lineage: Optional[Dict]
    confidence: str


class LineageResponse(BaseModel):
    image_id: str
    original_image: Dict
    nodes: List[Dict]
    edges: List[Dict]
    statistics: Dict


# Prometheus Metrics
UPLOAD_COUNT = Counter('image_upload_total', 'Total number of image uploads')
DETECTION_COUNT = Counter('image_detection_total', 'Total number of image detections', ['method', 'confidence'])
API_LATENCY = Histogram('api_request_latency_seconds', 'API request latency', ['endpoint'])

# Database connection pool
db_pool = psycopg2.pool.SimpleConnectionPool(
    1, 20,
    dsn=Config.DATABASE_URL
)

# Redis client for rate limiting
redis_client = redis.from_url(Config.REDIS_URL)

def get_db():
    conn = db_pool.getconn()
    conn.cursor_factory = RealDictCursor
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

async def rate_limit(user: User = Depends(get_current_user)):
    """Simple Redis-based rate limiting (100 requests per minute)"""
    key = f"rate_limit:{user.username}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, 60)
    if count > 100:
        raise HTTPException(status_code=429, detail="Too many requests")
    return True


# Initialize services
fingerprinter = ImageFingerprinter()
watermarker = InvisibleWatermarker()
blockchain_service = BlockchainService()


def get_services(db=Depends(get_db)):
    """Dependency injection for services"""
    tracker = DistributionTracker(db)
    derivative_detector = DerivativeDetector(fingerprinter, db)
    reentry_detector = ReentryDetector(
        watermarker, fingerprinter, derivative_detector, tracker, db
    )
    return {
        'tracker': tracker,
        'derivative_detector': derivative_detector,
        'reentry_detector': reentry_detector
    }


# Auth Endpoints

@app.post("/api/v1/auth/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Authenticate user and return JWT token
    """
    # In production, check against database
    # For now, using the mock database from security.py
    from security import MOCK_USERS_DB, pwd_context
    
    user = MOCK_USERS_DB.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user["username"], "roles": user["roles"], "org_id": user["org_id"]}
    )
    return {"access_token": access_token, "token_type": "bearer"}


# Endpoints

@app.post("/api/v1/images/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user: User = Depends(check_permissions(["user", "admin"])),
    _ = Depends(rate_limit)
):
    """
    Upload and register a new image with complete fingerprinting
    """
    start_time = time.time()
    try:
        # Read image
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Generate fingerprints
        fingerprints = fingerprinter.fingerprint_image(
            image=image,
            image_bytes=image_bytes
        )
        
        # Generate IDs
        image_id = str(uuid.uuid4())
        watermark_id = str(uuid.uuid4())
        
        # Embed watermark
        watermark_data = {
            'uuid': watermark_id,
            'created_at': datetime.utcnow().isoformat(),
            'version': '1.0'
        }
        watermarked_image = watermarker.embed_watermark(image, watermark_data)
        
        # Save watermarked image (in production, save to S3/cloud storage)
        storage_path = f"/storage/images/{image_id}.png"
        watermarked_image.save(storage_path)
        
        # Store in database
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO images (
                id, original_filename, watermark_id,
                perceptual_hash, sha256_hash, clip_embedding, dinov2_embedding,
                file_size, mime_type, width, height,
                storage_path, uploaded_by, organization_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            image_id, file.filename, watermark_id,
            fingerprints['perceptual_hash'], fingerprints['sha256_hash'],
            fingerprints.get('clip_embedding').tolist() if 'clip_embedding' in fingerprints else None,
            fingerprints.get('dinov2_embedding').tolist() if 'dinov2_embedding' in fingerprints else None,
            len(image_bytes), file.content_type,
            fingerprints['width'], fingerprints['height'],
            storage_path, current_user.username, current_user.org_id
        ))
        
        # 4. Anchor to Blockchain (Async in production)
        anchor_result = await blockchain_service.anchor_image(
            image_id=image_id,
            image_hash=fingerprints['sha256_hash'],
            metadata={
                'uploaded_by': uploaded_by,
                'organization_id': organization_id,
                'original_filename': file.filename
            }
        )
        
        # Update image with blockchain data
        cursor.execute("""
            UPDATE images 
            SET blockchain_tx = %s, arweave_id = %s
            WHERE id = %s
        """, (anchor_result.get('polygon_tx_hash'), anchor_result.get('arweave_tx_hash'), image_id))
        
        # 5. Record upload event
        tracker = DistributionTracker(db)
        tracker.record_event(
            image_id=image_id,
            event_type='upload',
            platform='api',
            metadata={'original_filename': file.filename}
        )
        
        db.commit()
        
        UPLOAD_COUNT.inc()
        API_LATENCY.labels(endpoint='/images/upload').observe(time.time() - start_time)
        
        return ImageUploadResponse(
            image_id=image_id,
            watermark_id=watermark_id,
            fingerprints={
                'perceptual_hash': fingerprints['perceptual_hash'],
                'sha256': fingerprints['sha256_hash'],
                'dimensions': f"{fingerprints['width']}x{fingerprints['height']}"
            },
            storage_url=f"/api/v1/images/{image_id}/download",
            created_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/images/{image_id}/share")
async def share_image(
    image_id: str,
    request: ShareRequest,
    services=Depends(get_services)
):
    """
    Record a share/distribution event
    """
    tracker = services['tracker']
    
    try:
        event_id = tracker.record_event(
            image_id=image_id,
            event_type='share',
            device_fingerprint=request.context.device_id,
            ip_address=request.context.ip_address,
            platform=request.context.platform,
            user_agent=request.context.user_agent,
            source_event_id=request.source_event_id,
            metadata=request.context.metadata
        )
        
        return {
            'event_id': event_id,
            'image_id': image_id,
            'event_type': 'share',
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/images/detect", response_model=DetectionResponse)
async def detect_image(
    file: UploadFile = File(...),
    device_id: Optional[str] = Header(None),
    platform: Optional[str] = Header(None),
    services=Depends(get_services),
    db=Depends(get_db)
):
    """
    Detect if an uploaded image matches any tracked images
    Returns complete lineage if match found
    """
    try:
        # Read image
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Run detection
        context = {
            'device_id': device_id,
            'platform': platform or 'api'
        }
        
        reentry_detector = services['reentry_detector']
        result = reentry_detector.detect_image(image, image_bytes, context)
        
        return DetectionResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/images/{image_id}/lineage", response_model=LineageResponse)
async def get_image_lineage(
    image_id: str,
    services=Depends(get_services),
    db=Depends(get_db)
):
    """
    Get complete lineage graph for an image
    """
    try:
        tracker = services['tracker']
        lineage = tracker.build_lineage_graph(image_id)
        
        # Get image metadata
        cursor = db.cursor()
        cursor.execute("""
            SELECT 
                original_filename, watermark_id, created_at,
                uploaded_by, width, height
            FROM images
            WHERE id = %s
        """, (image_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Image not found")
        
        original_image = {
            'id': image_id,
            'filename': result['original_filename'],
            'watermark_id': result['watermark_id'],
            'created_at': result['created_at'].isoformat() if result['created_at'] else None,
            'uploaded_by': result['uploaded_by'],
            'dimensions': f"{result['width']}x{result['height']}"
        }
        
        return LineageResponse(
            image_id=image_id,
            original_image=original_image,
            nodes=lineage['nodes'],
            edges=lineage['edges'],
            statistics=lineage['statistics']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/images/{image_id}/hops")
async def get_hop_chain(
    image_id: str,
    services=Depends(get_services)
):
    """
    Get chronological hop chain for an image
    """
    try:
        tracker = services['tracker']
        hops = tracker.get_hop_chain(image_id)
        stats = tracker.get_hop_statistics(image_id)
        
        return {
            'image_id': image_id,
            'hops': hops,
            'statistics': stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/images/{image_id}/derivatives")
async def get_derivatives(
    image_id: str,
    similarity_threshold: float = 0.75,
    services=Depends(get_services)
):
    """
    Get all AI derivatives of an image
    """
    try:
        tracker = services['tracker']
        derivatives = tracker.find_derivative_candidates(
            image_id,
            similarity_threshold
        )
        
        return {
            'image_id': image_id,
            'derivatives': derivatives,
            'count': len(derivatives)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats/detections")
async def get_detection_stats(
    days: int = 30,
    services=Depends(get_services)
):
    """
    Get detection statistics for recent time window
    """
    try:
        reentry_detector = services['reentry_detector']
        stats = reentry_detector.get_detection_statistics(days)
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return JSONResponse(content=generate_latest().decode('utf-8'))


# Run with: uvicorn api.py --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
