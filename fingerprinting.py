"""
Multi-Model Image Fingerprinting
Uses CLIP and DinoV2 for robust semantic awareness
"""

import torch
from torchvision import transforms
from PIL import Image
from transformers import AutoImageProcessor, AutoModel
import numpy as np
import hashlib
import imagehash
from typing import Dict, Optional
from config import Config

class ImageFingerprinter:
    """
    Generates dual semantic embeddings (CLIP + DinoV2) and perceptual hashes
    """
    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load CLIP (standard semantic matching)
        from transformers import CLIPProcessor, CLIPModel
        self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # Load DinoV2 (Analog Hole defense)
        self.dino_processor = AutoImageProcessor.from_pretrained(Config.DINOV2_MODEL)
        self.dino_model = AutoModel.from_pretrained(Config.DINOV2_MODEL).to(self.device)
        
        self.clip_model.eval()
        self.dino_model.eval()

    def fingerprint_image(self, image: Image.Image, image_bytes: bytes) -> Dict:
        """Generate comprehensive fingerprints for an image"""
        # 1. Cryptographic Hash (Exact Match)
        sha256 = hashlib.sha256(image_bytes).hexdigest()
        
        # 2. Perceptual Hashes (Robust to edits)
        phash = str(imagehash.phash(image))
        dhash = str(imagehash.dhash(image))
        
        # 3. Dual Semantic Embeddings
        with torch.no_grad():
            # CLIP Embedding
            clip_inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
            clip_emb = self.clip_model.get_image_features(**clip_inputs)
            clip_emb = clip_emb / clip_emb.norm(p=2, dim=-1, keepdim=True)
            
            # DinoV2 Embedding
            dino_inputs = self.dino_processor(images=image, return_tensors="pt").to(self.device)
            dino_outputs = self.dino_model(**dino_inputs)
            dino_emb = dino_outputs.last_hidden_state.mean(dim=1)
            dino_emb = dino_emb / dino_emb.norm(p=2, dim=-1, keepdim=True)
            
        return {
            'sha256_hash': sha256,
            'perceptual_hash': phash,
            'dhash': dhash,
            'clip_embedding': clip_emb.cpu().numpy()[0],
            'dinov2_embedding': dino_emb.cpu().numpy()[0],
            'width': image.width,
            'height': image.height
        }

    def compare_perceptual_hashes(self, hash1: str, hash2: str) -> float:
        """Compare two phashes (returns 0 to 1)"""
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        diff = h1 - h2
        # max diff for 64-bit hash is 64
        return 1.0 - (diff / 64.0)
