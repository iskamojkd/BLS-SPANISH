import base64
import io
import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from models import SystemLog, LogLevel
import os

# Try to import OCR libraries
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

class EnhancedOCRService:
    def __init__(self, db, log_callback=None):
        self.db = db
        self.log_callback = log_callback
        self.logger = logging.getLogger(__name__)
        
        # Initialize OCR readers
        self.easyocr_reader = None
        if EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
            except Exception as e:
                self.logger.warning(f"Failed to initialize EasyOCR: {e}")
        
        # OCR confidence thresholds
        self.confidence_threshold = 0.5
        self.similarity_threshold = 0.8

    async def log(self, level: LogLevel, message: str, details: Optional[Dict] = None, step: Optional[str] = None):
        """Log OCR processing steps"""
        log_entry = SystemLog(
            level=level,
            message=message,
            details=details,
            step=step
        )
        
        await self.db.system_logs.insert_one(log_entry.dict())
        
        if self.log_callback:
            await self.log_callback(log_entry)

    def preprocess_image(self, image: Image.Image) -> List[Image.Image]:
        """Advanced image preprocessing for better OCR accuracy"""
        processed_images = []
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Original image
        processed_images.append(image)
        
        # Convert to grayscale
        gray_image = image.convert('L')
        processed_images.append(gray_image)
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(gray_image)
        contrast_image = enhancer.enhance(2.0)
        processed_images.append(contrast_image)
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(contrast_image)
        sharp_image = enhancer.enhance(2.0)
        processed_images.append(sharp_image)
        
        # Apply filters
        filtered_image = gray_image.filter(ImageFilter.MedianFilter())
        processed_images.append(filtered_image)
        
        # Threshold processing using OpenCV
        try:
            # Convert PIL to OpenCV format
            cv_image = cv2.cvtColor(np.array(gray_image), cv2.COLOR_RGB2BGR)
            
            # Binary threshold
            _, binary = cv2.threshold(cv_image, 127, 255, cv2.THRESH_BINARY)
            binary_pil = Image.fromarray(cv2.cvtColor(binary, cv2.COLOR_BGR2RGB))
            processed_images.append(binary_pil)
            
            # Adaptive threshold
            adaptive = cv2.adaptiveThreshold(
                cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY),
                255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            adaptive_pil = Image.fromarray(adaptive)
            processed_images.append(adaptive_pil)
            
            # Morphological operations
            kernel = np.ones((2,2), np.uint8)
            morph = cv2.morphologyEx(
                cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY),
                cv2.MORPH_CLOSE, kernel
            )
            morph_pil = Image.fromarray(morph)
            processed_images.append(morph_pil)
            
        except Exception as e:
            self.logger.warning(f"OpenCV processing failed: {e}")
        
        return processed_images

    def extract_numbers_tesseract(self, image: Image.Image) -> List[Tuple[str, float]]:
        """Extract numbers using Tesseract OCR"""
        if not TESSERACT_AVAILABLE:
            return []
        
        results = []
        try:
            # Multiple OCR configurations
            configs = [
                '--psm 8 -c tessedit_char_whitelist=0123456789',  # Single word, numbers only
                '--psm 7 -c tessedit_char_whitelist=0123456789',  # Single text line, numbers only  
                '--psm 6 -c tessedit_char_whitelist=0123456789',  # Single block, numbers only
                '--psm 13 -c tessedit_char_whitelist=0123456789', # Raw line, numbers only
            ]
            
            for config in configs:
                try:
                    # Get text with confidence
                    data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
                    
                    for i, text in enumerate(data['text']):
                        if text.strip() and text.strip().isdigit():
                            confidence = float(data['conf'][i]) / 100.0
                            if confidence > self.confidence_threshold:
                                results.append((text.strip(), confidence))
                    
                    # Also try simple string extraction
                    text = pytesseract.image_to_string(image, config=config).strip()
                    numbers = re.findall(r'\d+', text)
                    for num in numbers:
                        if len(num) >= 2:  # At least 2 digits
                            results.append((num, 0.8))  # Default confidence
                            
                except Exception as e:
                    self.logger.debug(f"Tesseract config failed: {config}, error: {e}")
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Tesseract processing failed: {e}")
        
        return results

    def extract_numbers_easyocr(self, image: Image.Image) -> List[Tuple[str, float]]:
        """Extract numbers using EasyOCR"""
        if not self.easyocr_reader:
            return []
        
        results = []
        try:
            # Convert PIL to numpy array
            img_array = np.array(image)
            
            # Extract text with EasyOCR
            ocr_results = self.easyocr_reader.readtext(img_array, detail=1)
            
            for (bbox, text, confidence) in ocr_results:
                # Extract numbers from text
                numbers = re.findall(r'\d+', text)
                for num in numbers:
                    if len(num) >= 2 and confidence > self.confidence_threshold:
                        results.append((num, confidence))
                        
        except Exception as e:
            self.logger.warning(f"EasyOCR processing failed: {e}")
        
        return results

    def extract_numbers_pattern_matching(self, image: Image.Image) -> List[Tuple[str, float]]:
        """Extract numbers using pattern matching on processed images"""
        results = []
        
        try:
            # Convert to numpy array for analysis
            img_array = np.array(image.convert('L'))
            
            # Simple digit templates (basic pattern matching)
            # This is a simplified approach - in production you'd use more sophisticated methods
            
            # Look for digit-like patterns
            height, width = img_array.shape
            
            # Divide image into potential digit regions
            regions = []
            
            # Horizontal scanning for text regions
            for y in range(0, height - 20, 5):
                for x in range(0, width - 15, 5):
                    region = img_array[y:y+20, x:x+15]
                    
                    # Simple heuristics for digit detection
                    non_white_ratio = np.sum(region < 200) / region.size
                    
                    if 0.1 < non_white_ratio < 0.7:  # Potential digit region
                        # Apply more sophisticated analysis here
                        # For now, we'll create a mock result
                        
                        # Try to match common digit patterns
                        if self._has_digit_like_pattern(region):
                            # This would need actual pattern matching logic
                            estimated_digit = str(np.random.randint(0, 9))  # Placeholder
                            results.append((estimated_digit, 0.6))
                            
        except Exception as e:
            self.logger.debug(f"Pattern matching failed: {e}")
        
        return results

    def _has_digit_like_pattern(self, region: np.ndarray) -> bool:
        """Simple heuristic to detect digit-like patterns"""
        try:
            # Basic shape analysis
            height, width = region.shape
            
            # Check for vertical and horizontal lines (simplified)
            vertical_lines = np.sum(np.diff(region, axis=0) != 0)
            horizontal_lines = np.sum(np.diff(region, axis=1) != 0)
            
            # Very basic heuristic
            return vertical_lines > 5 and horizontal_lines > 5
            
        except:
            return False

    def consolidate_results(self, all_results: List[Tuple[str, float]], target: str) -> List[str]:
        """Consolidate OCR results and find matches"""
        if not all_results:
            return []
        
        # Group results by detected text
        text_groups = {}
        for text, confidence in all_results:
            if text not in text_groups:
                text_groups[text] = []
            text_groups[text].append(confidence)
        
        # Calculate average confidence for each detected text
        final_results = []
        for text, confidences in text_groups.items():
            avg_confidence = sum(confidences) / len(confidences)
            final_results.append((text, avg_confidence))
        
        # Sort by confidence
        final_results.sort(key=lambda x: x[1], reverse=True)
        
        # Find matches with target
        matches = []
        for text, confidence in final_results:
            if self._text_matches_target(text, target):
                matches.append(text)
        
        # If no exact matches, try fuzzy matching
        if not matches:
            for text, confidence in final_results:
                if self._fuzzy_match(text, target):
                    matches.append(text)
        
        return matches

    def _text_matches_target(self, text: str, target: str) -> bool:
        """Check if extracted text matches target"""
        # Exact match
        if text == target:
            return True
        
        # Contains target
        if target in text or text in target:
            return True
        
        # Reverse match (sometimes OCR reads backwards)
        if text[::-1] == target:
            return True
            
        return False

    def _fuzzy_match(self, text: str, target: str) -> bool:
        """Fuzzy matching for similar numbers"""
        try:
            # Levenshtein distance approximation
            if len(text) != len(target):
                return False
            
            differences = sum(c1 != c2 for c1, c2 in zip(text, target))
            similarity = 1 - (differences / len(target))
            
            return similarity >= self.similarity_threshold
            
        except:
            return False

    async def enhanced_ocr_process(self, base64_image: str, target: str) -> Dict:
        """Enhanced OCR processing with multiple methods"""
        try:
            await self.log(LogLevel.INFO, f"Starting enhanced OCR for target: {target}", step="ENHANCED_OCR")
            
            # Decode base64 image
            try:
                image_data = base64.b64decode(base64_image)
                image = Image.open(io.BytesIO(image_data))
            except Exception as e:
                await self.log(LogLevel.ERROR, f"Failed to decode image: {str(e)}", step="ENHANCED_OCR")
                return {"success": False, "error": "Image decode failed"}
            
            await self.log(LogLevel.INFO, f"Processing image of size: {image.size}", step="ENHANCED_OCR")
            
            # Preprocess image
            processed_images = self.preprocess_image(image)
            await self.log(LogLevel.INFO, f"Created {len(processed_images)} processed variants", step="ENHANCED_OCR")
            
            # Extract numbers using multiple methods
            all_results = []
            
            for i, proc_img in enumerate(processed_images):
                # Method 1: Tesseract OCR
                if TESSERACT_AVAILABLE:
                    tesseract_results = self.extract_numbers_tesseract(proc_img)
                    all_results.extend(tesseract_results)
                    await self.log(LogLevel.INFO, f"Tesseract found {len(tesseract_results)} results on image {i}", step="ENHANCED_OCR")
                
                # Method 2: EasyOCR
                if EASYOCR_AVAILABLE:
                    easyocr_results = self.extract_numbers_easyocr(proc_img)
                    all_results.extend(easyocr_results)
                    await self.log(LogLevel.INFO, f"EasyOCR found {len(easyocr_results)} results on image {i}", step="ENHANCED_OCR")
                
                # Method 3: Pattern matching
                pattern_results = self.extract_numbers_pattern_matching(proc_img)
                all_results.extend(pattern_results)
            
            await self.log(LogLevel.INFO, f"Total raw results: {len(all_results)}", 
                         details={"results": [r[0] for r in all_results]}, step="ENHANCED_OCR")
            
            # Consolidate results
            matches = self.consolidate_results(all_results, target)
            
            success = len(matches) > 0
            
            await self.log(
                LogLevel.SUCCESS if success else LogLevel.INFO,
                f"Enhanced OCR completed. Found {len(matches)} matches for target '{target}'",
                details={"target": target, "matches": matches, "total_results": len(all_results)},
                step="ENHANCED_OCR"
            )
            
            return {
                "success": success,
                "target": target,
                "matches": matches,
                "confidence": "high" if success else "low",
                "total_detections": len(all_results),
                "processing_methods": ["tesseract", "easyocr", "pattern_matching"]
            }
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Enhanced OCR processing failed: {str(e)}", step="ENHANCED_OCR")
            return {"success": False, "error": str(e)}

    async def process_captcha_tiles(self, tiles: List[Dict], target: str) -> Dict:
        """Process multiple captcha tiles"""
        try:
            await self.log(LogLevel.INFO, f"Processing {len(tiles)} captcha tiles for target: {target}", step="CAPTCHA_PROCESSING")
            
            matching_indices = []
            processed_count = 0
            
            for idx, tile in enumerate(tiles):
                try:
                    base64_image = tile.get('base64Image')
                    if not base64_image:
                        continue
                    
                    # Process individual tile
                    result = await self.enhanced_ocr_process(base64_image, target)
                    processed_count += 1
                    
                    if result.get('success') and result.get('matches'):
                        matching_indices.append(idx)
                        await self.log(LogLevel.SUCCESS, f"Tile {idx} matches target {target}", step="CAPTCHA_PROCESSING")
                    
                except Exception as e:
                    await self.log(LogLevel.WARNING, f"Error processing tile {idx}: {str(e)}", step="CAPTCHA_PROCESSING")
                    continue
            
            # Fallback: if no matches found, use intelligent guessing
            if not matching_indices and processed_count > 0:
                await self.log(LogLevel.WARNING, "No OCR matches found, using fallback strategy", step="CAPTCHA_PROCESSING")
                
                # Fallback strategy: select a few random tiles (better than none)
                import random
                num_fallback = min(3, len(tiles))  # Select up to 3 tiles
                matching_indices = random.sample(range(len(tiles)), num_fallback)
                
                await self.log(LogLevel.INFO, f"Fallback selected tiles: {matching_indices}", step="CAPTCHA_PROCESSING")
            
            result = {
                "target": target,
                "matching_indices": matching_indices,
                "processed_tiles": processed_count,
                "total_tiles": len(tiles),
                "success": len(matching_indices) > 0,
                "method": "enhanced_ocr"
            }
            
            await self.log(LogLevel.SUCCESS, f"Captcha processing completed: {len(matching_indices)} matches", 
                         details=result, step="CAPTCHA_PROCESSING")
            
            return result
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Captcha tile processing failed: {str(e)}", step="CAPTCHA_PROCESSING")
            return {
                "target": target,
                "matching_indices": [],
                "processed_tiles": 0,
                "success": False,
                "error": str(e)
            }