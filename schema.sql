-- Image Provenance and Tracking System Database Schema
-- PostgreSQL implementation

-- Core Images Table
CREATE TABLE images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(500) NOT NULL,
    watermark_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    
    -- Fingerprinting data
    perceptual_hash VARCHAR(64) NOT NULL,  -- pHash/dHash
    sha256_hash VARCHAR(64) UNIQUE NOT NULL,
    clip_embedding VECTOR(512),  -- Using pgvector extension
    dinov2_embedding VECTOR(768), -- DinoV2 base dimension
    
    -- File metadata
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    
    -- Storage
    storage_path TEXT NOT NULL,
    cdn_url TEXT,
    
    -- Ownership
    uploaded_by UUID NOT NULL,
    organization_id UUID,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Blockchain Anchoring
    blockchain_tx VARCHAR(66),
    arweave_id VARCHAR(100),
    
    -- Indexing
    CONSTRAINT valid_dimensions CHECK (width > 0 AND height > 0)
);

-- Index for fast perceptual hash lookups
CREATE INDEX idx_images_phash ON images USING hash(perceptual_hash);
CREATE INDEX idx_images_sha256 ON images USING hash(sha256_hash);
CREATE INDEX idx_images_watermark ON images (watermark_id);

-- Vector similarity index for CLIP embeddings
CREATE INDEX idx_images_clip_embedding ON images 
USING ivfflat (clip_embedding vector_cosine_ops) WITH (lists = 100);


-- Distribution Events (every hop)
CREATE TABLE distribution_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    
    -- Event tracking
    event_type VARCHAR(50) NOT NULL,  -- 'view', 'download', 'share', 'upload', 'ai_derivative'
    
    -- Device/Location tracking (hashed for privacy)
    device_fingerprint_hash VARCHAR(64),  -- Hashed device ID
    ip_address_hash VARCHAR(64),  -- Hashed IP
    approximate_location JSONB,  -- {"country": "US", "region": "CA"}
    
    -- Platform context
    platform VARCHAR(100),  -- 'mobile_app', 'web', 'api', 'third_party'
    user_agent TEXT,
    
    -- Hop chain tracking
    source_event_id UUID REFERENCES distribution_events(id),  -- Previous hop
    hop_depth INTEGER DEFAULT 0,  -- Distance from original upload
    
    -- Metadata
    metadata JSONB,  -- Flexible additional data
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_event_type CHECK (
        event_type IN ('view', 'download', 'share', 'upload', 'ai_derivative', 'modification', 'detection')
    )
);

-- Indexes for event querying
CREATE INDEX idx_events_image_id ON distribution_events(image_id);
CREATE INDEX idx_events_created ON distribution_events(created_at DESC);
CREATE INDEX idx_events_type ON distribution_events(event_type);
CREATE INDEX idx_events_chain ON distribution_events(source_event_id);
CREATE INDEX idx_events_hop_depth ON distribution_events(hop_depth);


-- AI Derivatives (when an image is used to generate new images)
CREATE TABLE ai_derivatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Original and derivative relationship
    source_image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    derivative_image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    
    -- Detection metadata
    similarity_score FLOAT NOT NULL,  -- 0.0 to 1.0
    detection_method VARCHAR(100) NOT NULL,  -- 'clip_embedding', 'perceptual_hash', 'watermark'
    
    -- AI generation details
    ai_model_used VARCHAR(200),  -- 'stable_diffusion_xl', 'midjourney', etc.
    generation_prompt TEXT,
    transformation_type VARCHAR(100),  -- 'style_transfer', 'upscale', 'inpaint', etc.
    
    -- Portion tracking
    portion_used JSONB,  -- {"x": 100, "y": 200, "width": 500, "height": 300}
    
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_similarity CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    CONSTRAINT different_images CHECK (source_image_id != derivative_image_id)
);

CREATE INDEX idx_derivatives_source ON ai_derivatives(source_image_id);
CREATE INDEX idx_derivatives_derivative ON ai_derivatives(derivative_image_id);
CREATE INDEX idx_derivatives_similarity ON ai_derivatives(similarity_score DESC);


-- Hop Graph (materialized view for fast lineage queries)
CREATE MATERIALIZED VIEW image_lineage AS
WITH RECURSIVE hop_chain AS (
    -- Base case: direct uploads (hop_depth = 0)
    SELECT 
        de.id,
        de.image_id,
        de.event_type,
        de.source_event_id,
        de.hop_depth,
        de.created_at,
        ARRAY[de.id] as path,
        de.device_fingerprint_hash
    FROM distribution_events de
    WHERE de.hop_depth = 0
    
    UNION ALL
    
    -- Recursive case: follow the chain
    SELECT 
        de.id,
        de.image_id,
        de.event_type,
        de.source_event_id,
        de.hop_depth,
        de.created_at,
        hc.path || de.id,
        de.device_fingerprint_hash
    FROM distribution_events de
    INNER JOIN hop_chain hc ON de.source_event_id = hc.id
)
SELECT * FROM hop_chain;

-- Index for lineage view
CREATE INDEX idx_lineage_image ON image_lineage(image_id);
CREATE INDEX idx_lineage_path ON image_lineage USING gin(path);


-- Users table (simplified)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- Detection Queue (for async processing of re-entered images)
CREATE TABLE detection_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    candidate_image_hash VARCHAR(64) NOT NULL,
    candidate_embedding VECTOR(512),
    candidate_metadata JSONB,
    
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processing', 'matched', 'no_match'
    matched_image_id UUID REFERENCES images(id),
    
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_queue_status ON detection_queue(status);


-- Audit log for compliance
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,  -- 'insert', 'update', 'delete'
    changed_data JSONB,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_table ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_time ON audit_log(changed_at DESC);


-- External detections (found on the web via OSINT)
CREATE TABLE external_detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    
    source_url TEXT NOT NULL,
    detection_method VARCHAR(100) NOT NULL, -- 'google_vision', 'tineye', etc.
    similarity_score FLOAT,
    page_title TEXT,
    site_name VARCHAR(200),
    
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ext_det_image ON external_detections(image_id);
CREATE INDEX idx_ext_det_time ON external_detections(detected_at DESC);
