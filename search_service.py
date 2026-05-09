"""
Vector Search Service
Implements high-performance similarity search using FAISS
"""

import faiss
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class VectorSearchService:
    """
    High-performance vector search using FAISS
    """
    
    def __init__(self, dimension: int = 512):
        self.dimension = dimension
        # FlatL2 index for high accuracy
        # In production, use IndexIVFFlat or IndexHNSWFlat for faster search at scale
        self.index = faiss.IndexFlatIP(dimension) 
        self.id_map = [] # Maps FAISS index ID to Database UUID
        
    def add_vectors(self, vectors: np.ndarray, ids: List[str]):
        """
        Add image embeddings to the search index
        """
        if len(vectors) == 0: return
        
        # Normalize for cosine similarity (since we use IndexFlatIP)
        faiss.normalize_L2(vectors)
        
        self.index.add(vectors.astype('float32'))
        self.id_map.extend(ids)
        logger.info(f"Added {len(vectors)} vectors to FAISS index. Total: {self.index.ntotal}")

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Dict]:
        """
        Search for similar images
        """
        if self.index.ntotal == 0:
            return []
            
        # Normalize query vector
        faiss.normalize_L2(query_vector)
        
        # Search
        distances, indices = self.index.search(query_vector.astype('float32'), top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1: continue
            
            results.append({
                'image_id': self.id_map[idx],
                'similarity': float(distances[0][i]),
                'index_id': int(idx)
            })
            
        return results

    def save_index(self, path: str):
        """Persist index to disk"""
        faiss.write_index(self.index, path)
        # Would also need to save id_map (e.g., as JSON)

    def load_index(self, path: str):
        """Load index from disk"""
        self.index = faiss.read_index(path)
