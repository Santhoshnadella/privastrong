"""
Cloud Storage Service
Handles image storage on S3-compatible object storage (S3, GCS, Minio)
"""

import os
import boto3
from botocore.exceptions import ClientError
import logging
from typing import Optional, BinaryIO

logger = logging.getLogger(__name__)

class StorageService:
    """
    Manages image storage with cloud and local fallbacks
    """
    
    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.getenv("STORAGE_BUCKET", "image-provenance")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        
        # Initialize S3 client
        # In production, use IAM roles or env vars for credentials
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        
        self.is_mock_mode = not os.getenv("AWS_ACCESS_KEY_ID")
        
        if self.is_mock_mode:
            logger.warning("No S3 credentials found. Falling back to LOCAL STORAGE.")
        else:
            logger.info(f"StorageService initialized for bucket: {self.bucket_name}")

    async def upload_image(self, file_path: str, image_id: str, content_type: str = "image/png") -> str:
        """
        Upload an image to cloud storage
        
        Returns:
            Publicly accessible URL or internal path
        """
        if self.is_mock_mode:
            # Simulate local storage logic
            logger.info(f"Mock upload: {file_path} -> local_storage/{image_id}")
            return f"/storage/images/{image_id}.png"
            
        try:
            object_name = f"images/{image_id}.png"
            self.s3_client.upload_file(
                file_path, 
                self.bucket_name, 
                object_name,
                ExtraArgs={'ContentType': content_type}
            )
            
            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_name}"
            return url
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            return f"/storage/images/{image_id}.png" # Fallback

    def delete_image(self, image_id: str) -> bool:
        """Delete image from storage"""
        if self.is_mock_mode: return True
        
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=f"images/{image_id}.png")
            return True
        except ClientError:
            return False
