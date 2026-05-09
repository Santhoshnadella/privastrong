"""
Distribution Tracking Service
Records and tracks image distribution events across devices and platforms
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
import hashlib
import json
import redis
import os


class DistributionTracker:
    """
    Tracks image distribution events and builds hop chains
    """
    
    def __init__(self, db_connection):
        """
        Args:
            db_connection: Database connection object (psycopg2 or similar)
        """
        self.db = db_connection
        self.redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    
    def hash_identifier(self, identifier: str) -> str:
        """
        Hash sensitive identifiers for privacy
        
        Args:
            identifier: Device ID, IP address, etc.
            
        Returns:
            SHA-256 hash
        """
        return hashlib.sha256(identifier.encode()).hexdigest()
    
    def record_event(self,
                    image_id: str,
                    event_type: str,
                    device_fingerprint: Optional[str] = None,
                    ip_address: Optional[str] = None,
                    platform: Optional[str] = None,
                    user_agent: Optional[str] = None,
                    source_event_id: Optional[str] = None,
                    metadata: Optional[Dict] = None) -> str:
        """
        Record a distribution event
        
        Args:
            image_id: UUID of the image
            event_type: Type of event ('view', 'download', 'share', 'upload', 'ai_derivative')
            device_fingerprint: Device identifier (will be hashed)
            ip_address: IP address (will be hashed)
            platform: Platform identifier ('mobile_app', 'web', 'api')
            user_agent: User agent string
            source_event_id: ID of the previous event in the hop chain
            metadata: Additional metadata
            
        Returns:
            Event ID
        """
        # Hash sensitive data
        device_hash = self.hash_identifier(device_fingerprint) if device_fingerprint else None
        ip_hash = self.hash_identifier(ip_address) if ip_address else None
        
        # Determine hop depth
        hop_depth = 0
        if source_event_id:
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT hop_depth FROM distribution_events WHERE id = %s",
                (source_event_id,)
            )
            result = cursor.fetchone()
            if result:
                hop_depth = result[0] + 1
        
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Insert event
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO distribution_events (
                id, image_id, event_type, device_fingerprint_hash,
                ip_address_hash, platform, user_agent, source_event_id,
                hop_depth, metadata, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            event_id, image_id, event_type, device_hash,
            ip_hash, platform, user_agent, source_event_id,
            hop_depth, json.dumps(metadata) if metadata else None,
            datetime.utcnow()
        ))
        
        self.db.commit()
        
        return event_id
    
    def get_hop_chain(self, image_id: str) -> List[Dict]:
        """
        Get complete hop chain for an image
        
        Args:
            image_id: UUID of the image
            
        Returns:
            List of events in chronological order
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT 
                id, event_type, device_fingerprint_hash,
                platform, hop_depth, created_at, metadata
            FROM distribution_events
            WHERE image_id = %s
            ORDER BY created_at ASC
        """, (image_id,))
        
        events = []
        for row in cursor.fetchall():
            events.append({
                'id': row[0],
                'event_type': row[1],
                'device_hash': row[2],
                'platform': row[3],
                'hop_depth': row[4],
                'created_at': row[5].isoformat() if row[5] else None,
                'metadata': json.loads(row[6]) if row[6] else None
            })
        
        return events
    
    def get_hop_statistics(self, image_id: str) -> Dict:
        """
        Get statistics about image distribution
        
        Args:
            image_id: UUID of the image
            
        Returns:
            Statistics dictionary
        """
        cursor = self.db.cursor()
        
        # Total events
        cursor.execute(
            "SELECT COUNT(*) FROM distribution_events WHERE image_id = %s",
            (image_id,)
        )
        total_events = cursor.fetchone()[0]
        
        # Unique devices
        cursor.execute(
            "SELECT COUNT(DISTINCT device_fingerprint_hash) FROM distribution_events WHERE image_id = %s",
            (image_id,)
        )
        unique_devices = cursor.fetchone()[0]
        
        # Max hop depth
        cursor.execute(
            "SELECT MAX(hop_depth) FROM distribution_events WHERE image_id = %s",
            (image_id,)
        )
        max_depth = cursor.fetchone()[0] or 0
        
        # Event type breakdown
        cursor.execute("""
            SELECT event_type, COUNT(*) 
            FROM distribution_events 
            WHERE image_id = %s 
            GROUP BY event_type
        """, (image_id,))
        
        event_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            'total_events': total_events,
            'unique_devices': unique_devices,
            'max_hop_depth': max_depth,
            'event_breakdown': event_breakdown
        }
    
    def find_derivative_candidates(self, source_image_id: str, 
                                  similarity_threshold: float = 0.75) -> List[Dict]:
        """
        Find potential AI derivatives of an image
        
        Args:
            source_image_id: Original image UUID
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of potential derivatives
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT 
                derivative_image_id, similarity_score, 
                detection_method, ai_model_used
            FROM ai_derivatives
            WHERE source_image_id = %s 
            AND similarity_score >= %s
            ORDER BY similarity_score DESC
        """, (source_image_id, similarity_threshold))
        
        derivatives = []
        for row in cursor.fetchall():
            derivatives.append({
                'derivative_id': row[0],
                'similarity': row[1],
                'detection_method': row[2],
                'ai_model': row[3]
            })
        
        return derivatives
    
    def build_lineage_graph(self, image_id: str) -> Dict:
        """
        Build complete lineage graph including derivatives
        
        Args:
            image_id: UUID of the image
            
        Returns:
            Graph structure with nodes and edges
        """
        # Try to get from cache first
        cache_key = f"lineage:{image_id}"
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Get main hop chain
        hops = self.get_hop_chain(image_id)
        
        # Get derivatives
        derivatives = self.find_derivative_candidates(image_id)
        
        # Build graph
        nodes = [{
            'id': image_id,
            'type': 'original',
            'label': 'Original Image'
        }]
        
        edges = []
        
        # Add hop chain nodes and edges
        for i, hop in enumerate(hops):
            node_id = f"hop_{hop['id']}"
            nodes.append({
                'id': node_id,
                'type': 'distribution',
                'event_type': hop['event_type'],
                'hop_depth': hop['hop_depth'],
                'timestamp': hop['created_at']
            })
            
            if hop.get('source_event_id'):
                edges.append({
                    'source': f"hop_{hop['source_event_id']}",
                    'target': node_id,
                    'type': 'distribution'
                })
        
        # Add derivative nodes and edges
        for deriv in derivatives:
            nodes.append({
                'id': deriv['derivative_id'],
                'type': 'derivative',
                'similarity': deriv['similarity']
            })
            
            edges.append({
                'source': image_id,
                'target': deriv['derivative_id'],
                'type': 'ai_generation',
                'similarity': deriv['similarity']
            })
        
        result = {
            'nodes': nodes,
            'edges': edges,
            'statistics': self.get_hop_statistics(image_id)
        }
        
        # Cache for 1 hour
        self.redis_client.setex(cache_key, 3600, json.dumps(result))
        
        return result


# Example usage (requires database connection)
if __name__ == "__main__":
    # Note: This is a demonstration. In production, use proper connection pooling
    
    print("Distribution Tracker example")
    print("This requires a PostgreSQL database with the schema loaded.")
    print("\nExample event recording:")
    
    # Mock database connection for demonstration
    class MockDB:
        def cursor(self):
            return self
        def execute(self, *args):
            print(f"  SQL: {args[0][:80]}...")
        def fetchone(self):
            return (5,)
        def fetchall(self):
            return []
        def commit(self):
            pass
    
    tracker = DistributionTracker(MockDB())
    
    image_id = str(uuid.uuid4())
    print(f"\nImage ID: {image_id}")
    
    # Record upload event
    event1 = tracker.record_event(
        image_id=image_id,
        event_type='upload',
        device_fingerprint='device-abc123',
        ip_address='192.168.1.1',
        platform='web',
        metadata={'source': 'user_upload'}
    )
    print(f"Upload event: {event1}")
    
    # Record share event
    event2 = tracker.record_event(
        image_id=image_id,
        event_type='share',
        device_fingerprint='device-xyz789',
        ip_address='192.168.1.2',
        platform='mobile_app',
        source_event_id=event1,
        metadata={'share_method': 'link'}
    )
    print(f"Share event: {event2}")
