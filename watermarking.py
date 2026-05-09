"""
Robust Frequency-Domain Watermarking with Reed-Solomon Error Correction
Uses DWT for embedding and Reed-Solomon for data recovery robustness
"""

import numpy as np
from PIL import Image
import cv2
import pywt
import json
import io
from reedsolo import RSCodec
from typing import Optional, Dict
from config import Config

class InvisibleWatermarker:
    """
    Embeds invisible watermarks using DWT and Reed-Solomon error correction
    """
    
    def __init__(self):
        self.alpha = Config.WATERMARK_STRENGTH
        self.marker = "PRV"
        # 10 bytes of error correction (survives 5 errors)
        self.rs = RSCodec(10)
        
    def embed_watermark(self, image: Image.Image, watermark_data: Dict) -> Image.Image:
        """Embed watermark into the frequency domain with RS protection"""
        img_array = np.array(image.convert('RGB'))
        img_yuv = cv2.cvtColor(img_array, cv2.COLOR_RGB2YCrCb)
        y, cr, cb = cv2.split(img_yuv)
        
        # 1. Prepare data with Reed-Solomon error correction
        data_str = self.marker + json.dumps(watermark_data)
        data_bytes = data_str.encode('utf-8')
        rs_encoded = self.rs.encode(data_bytes)
        data_bits = ''.join(format(b, '08b') for b in rs_encoded)
        
        # 2. Apply DWT
        coeffs = pywt.dwt2(y.astype(np.float32), 'haar')
        LL, (LH, HL, HH) = coeffs
        
        # 3. Embed in LL sub-band
        h, w = LL.shape
        np.random.seed(42)
        indices = np.random.choice(h * w, len(data_bits), replace=False)
        
        for i, bit in enumerate(data_bits):
            idx_h, idx_w = divmod(indices[i], w)
            if bit == '1':
                LL[idx_h, idx_w] = (LL[idx_h, idx_w] // self.alpha) * self.alpha + (0.75 * self.alpha)
            else:
                LL[idx_h, idx_w] = (LL[idx_h, idx_w] // self.alpha) * self.alpha + (0.25 * self.alpha)
        
        # 4. Reconstruct
        y_watermarked = pywt.idwt2((LL, (LH, HL, HH)), 'haar')
        y_watermarked = np.clip(y_watermarked, 0, 255).astype(np.uint8)
        
        img_yuv_watermarked = cv2.merge([y_watermarked, cr, cb])
        return Image.fromarray(cv2.cvtColor(img_yuv_watermarked, cv2.COLOR_YCrCb2RGB))

    def extract_watermark(self, image: Image.Image) -> Optional[Dict]:
        """Extract watermark and apply RS error correction"""
        try:
            img_array = np.array(image.convert('RGB'))
            img_yuv = cv2.cvtColor(img_array, cv2.COLOR_RGB2YCrCb)
            y, _, _ = cv2.split(img_yuv)
            
            coeffs = pywt.dwt2(y.astype(np.float32), 'haar')
            LL, _ = coeffs
            
            h, w = LL.shape
            np.random.seed(42)
            
            # Extract enough bits for marker + data + RS codes
            max_bits = 4000 
            indices = np.random.choice(h * w, max_bits, replace=False)
            
            bits = ""
            for i in range(max_bits):
                idx_h, idx_w = divmod(indices[i], w)
                val = LL[idx_h, idx_w] % self.alpha
                bits += '1' if val > (self.alpha / 2) else '0'
            
            # Convert bits to bytes
            extracted_bytes = bytearray()
            for i in range(0, len(bits), 8):
                byte = bits[i:i+8]
                if len(byte) < 8: break
                extracted_bytes.append(int(byte, 2))
            
            # 5. Apply Reed-Solomon correction
            try:
                # RS decoding will fix any corrupted bits (up to 5 bytes)
                decoded_bytes, _, _ = self.rs.decode(extracted_bytes)
                extracted_str = decoded_bytes.decode('utf-8', errors='ignore')
            except Exception:
                # If RS fails, fallback to raw (less robust)
                extracted_str = extracted_bytes.decode('utf-8', errors='ignore')
            
            marker_idx = extracted_str.find(self.marker)
            if marker_idx == -1: return None
                
            json_str = ""
            brace_count = 0
            for char in extracted_str[marker_idx + len(self.marker):]:
                json_str += char
                if char == '{': brace_count += 1
                if char == '}': brace_count -= 1
                if brace_count == 0 and json_str.strip(): break
            
            return json.loads(json_str)
            
        except Exception:
            return None
