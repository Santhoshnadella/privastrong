"""
Image Provenance Tracking SDK
Python client library for easy integration
"""

from typing import Dict, List, Optional, BinaryIO
import requests
from pathlib import Path


class ImageProvenanceClient:
    """
    Client SDK for Image Provenance Tracking API
    
    Example:
        client = ImageProvenanceClient('http://localhost:8000')
        result = client.upload_image('photo.jpg', user_id='user_123')
        print(f"Image ID: {result['image_id']}")
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize client
        
        Args:
            base_url: API base URL (e.g., 'http://localhost:8000')
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/v1"
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'X-API-Key': api_key})
    
    def upload_image(self, 
                    image_path: str,
                    user_id: str,
                    organization_id: Optional[str] = None,
                    device_id: Optional[str] = None) -> Dict:
        """
        Upload and register a new image
        
        Args:
            image_path: Path to image file
            user_id: User ID uploading the image
            organization_id: Optional organization ID
            device_id: Optional device identifier
            
        Returns:
            Dictionary with image_id, watermark_id, and fingerprints
            
        Raises:
            ImageProvenanceError: If upload fails
        """
        headers = {'uploaded-by': user_id}
        
        if organization_id:
            headers['organization-id'] = organization_id
        if device_id:
            headers['device-id'] = device_id
        
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f)}
            response = self.session.post(
                f"{self.api_url}/images/upload",
                files=files,
                headers=headers
            )
        
        self._raise_for_status(response)
        return response.json()
    
    def detect_image(self,
                    image_path: str,
                    device_id: Optional[str] = None,
                    platform: Optional[str] = None) -> Dict:
        """
        Detect if an image matches any tracked images
        
        Args:
            image_path: Path to image file
            device_id: Optional device identifier
            platform: Optional platform identifier
            
        Returns:
            Detection result with matches and lineage
            
        Raises:
            ImageProvenanceError: If detection fails
        """
        headers = {}
        
        if device_id:
            headers['device-id'] = device_id
        if platform:
            headers['platform'] = platform
        
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f)}
            response = self.session.post(
                f"{self.api_url}/images/detect",
                files=files,
                headers=headers
            )
        
        self._raise_for_status(response)
        return response.json()
    
    def get_lineage(self, image_id: str) -> Dict:
        """
        Get complete lineage for an image
        
        Args:
            image_id: Image UUID
            
        Returns:
            Lineage graph with nodes, edges, and statistics
            
        Raises:
            ImageProvenanceError: If image not found
        """
        response = self.session.get(
            f"{self.api_url}/images/{image_id}/lineage"
        )
        
        self._raise_for_status(response)
        return response.json()
    
    def get_hops(self, image_id: str) -> Dict:
        """
        Get chronological hop chain for an image
        
        Args:
            image_id: Image UUID
            
        Returns:
            Dictionary with hops list and statistics
        """
        response = self.session.get(
            f"{self.api_url}/images/{image_id}/hops"
        )
        
        self._raise_for_status(response)
        return response.json()
    
    def record_share(self,
                    image_id: str,
                    device_id: str,
                    platform: str = 'sdk',
                    source_event_id: Optional[str] = None,
                    metadata: Optional[Dict] = None) -> Dict:
        """
        Record a share/distribution event
        
        Args:
            image_id: Image UUID
            device_id: Target device identifier
            platform: Platform identifier
            source_event_id: Optional source event ID for hop chain
            metadata: Optional additional metadata
            
        Returns:
            Dictionary with event_id
        """
        data = {
            'image_id': image_id,
            'context': {
                'device_id': device_id,
                'platform': platform,
                'metadata': metadata or {}
            }
        }
        
        if source_event_id:
            data['source_event_id'] = source_event_id
        
        response = self.session.post(
            f"{self.api_url}/images/{image_id}/share",
            json=data
        )
        
        self._raise_for_status(response)
        return response.json()
    
    def get_derivatives(self,
                       image_id: str,
                       similarity_threshold: float = 0.75) -> List[Dict]:
        """
        Get all AI derivatives of an image
        
        Args:
            image_id: Source image UUID
            similarity_threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of derivative dictionaries
        """
        response = self.session.get(
            f"{self.api_url}/images/{image_id}/derivatives",
            params={'similarity_threshold': similarity_threshold}
        )
        
        self._raise_for_status(response)
        return response.json()['derivatives']
    
    def get_detection_stats(self, days: int = 30) -> Dict:
        """
        Get detection statistics
        
        Args:
            days: Time window in days
            
        Returns:
            Statistics dictionary
        """
        response = self.session.get(
            f"{self.api_url}/stats/detections",
            params={'days': days}
        )
        
        self._raise_for_status(response)
        return response.json()
    
    def health_check(self) -> Dict:
        """
        Check API health
        
        Returns:
            Health status dictionary
        """
        response = self.session.get(f"{self.base_url}/health")
        self._raise_for_status(response)
        return response.json()
    
    def _raise_for_status(self, response: requests.Response):
        """
        Raise custom exception for HTTP errors
        """
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get('detail', response.text)
            except:
                message = response.text
            
            raise ImageProvenanceError(
                f"API request failed ({response.status_code}): {message}",
                status_code=response.status_code,
                response=response
            )


class ImageProvenanceError(Exception):
    """Custom exception for SDK errors"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response: Optional[requests.Response] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


# Convenience functions

def create_client(base_url: str = 'http://localhost:8000', 
                 api_key: Optional[str] = None) -> ImageProvenanceClient:
    """
    Create a new client instance
    
    Args:
        base_url: API base URL
        api_key: Optional API key
        
    Returns:
        ImageProvenanceClient instance
    """
    return ImageProvenanceClient(base_url, api_key)


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = ImageProvenanceClient('http://localhost:8000')
    
    # Check health
    try:
        health = client.health_check()
        print(f"✓ API is {health['status']}")
    except ImageProvenanceError as e:
        print(f"✗ API error: {e}")
        exit(1)
    
    # Example workflow
    print("\nExample SDK Usage:")
    print("==================\n")
    
    print("1. Upload image:")
    print("   result = client.upload_image('photo.jpg', user_id='user_123')")
    print("   image_id = result['image_id']")
    
    print("\n2. Record share:")
    print("   client.record_share(image_id, device_id='device_mobile_1')")
    
    print("\n3. Detect image:")
    print("   detection = client.detect_image('mystery.jpg')")
    print("   if detection['detected']:")
    print("       print(f\"Match found! Confidence: {detection['confidence']}\")")
    
    print("\n4. Get lineage:")
    print("   lineage = client.get_lineage(image_id)")
    print("   print(f\"Total hops: {lineage['statistics']['total_events']}\")")
    
    print("\n5. Get derivatives:")
    print("   derivatives = client.get_derivatives(image_id)")
    print("   print(f\"Found {len(derivatives)} derivatives\")")
