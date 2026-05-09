"""
Centralized Configuration Module
Consolidates all environment variables and secrets
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

class Config:
    # 🔐 Security & Auth
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-this-in-prod")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 day
    
    # 🗄️ Database & Redis
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:your_password@localhost/image_provenance")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # ☁️ Cloud Storage (AWS S3)
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "image-provenance-assets")
    
    # 🔍 OSINT & Search APIs
    GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")
    TINEYE_API_KEY = os.getenv("TINEYE_API_KEY")
    
    # ⛓️ Blockchain (Polygon / Arweave)
    BLOCKCHAIN_RPC_URL = os.getenv("BLOCKCHAIN_RPC_URL")
    BLOCKCHAIN_PRIVATE_KEY = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
    ARWEAVE_WALLET_JSON = os.getenv("ARWEAVE_WALLET_JSON") # Path to JSON file
    
    # 🛡️ Provenance & C2PA
    C2PA_PRIVATE_KEY_PATH = os.getenv("C2PA_PRIVATE_KEY_PATH")
    HSM_ENABLED = os.getenv("HSM_ENABLED", "false").lower() == "true"
    
    # 📐 Watermarking & Detection
    WATERMARK_STRENGTH = float(os.getenv("WATERMARK_STRENGTH", "5.0"))
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
    DINOV2_MODEL = os.getenv("DINOV2_MODEL", "facebook/dinov2-base")
    
    # 🇪🇺 Legal & Compliance
    GDPR_SALT_SECRET = os.getenv("GDPR_SALT_SECRET", "change-me-for-compliance")

    @classmethod
    def is_production(cls):
        return os.getenv("NODE_ENV") == "production"
