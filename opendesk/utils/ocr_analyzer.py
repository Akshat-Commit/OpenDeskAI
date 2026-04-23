import os
import threading
from datetime import datetime
from loguru import logger
from PIL import Image
import pytesseract
from opendesk.db.connection import db

import shutil

# Detect Tesseract binary at runtime:
# 1. Honour an explicit env var override
# 2. Try to locate it on PATH via shutil.which
# 3. Fall back to the standard Windows install location
_tesseract_cmd = (
    os.environ.get("TESSERACT_CMD") or
    os.environ.get("TESSERACT_PATH") or
    shutil.which("tesseract") or
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

tesseract_available = True
if not os.path.isfile(_tesseract_cmd) and not shutil.which("tesseract"):
    tesseract_available = False
    logger.warning(
        f"Tesseract not found at '{_tesseract_cmd}'. "
        "Local OCR disabled. Will use Cloud AI fallback."
    )
else:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

class OCRAnalyzer:
    
    def __init__(self):
        # Use the singleton DB — schema.sql already defines screenshot_ocr
        db.connect()
    
    def _setup_db(self):
        # Schema is managed centrally in db/schema.sql — no setup needed here
        logger.debug("OCR database ready")
    
    def extract_text(self, image_path: str) -> str:
        if tesseract_available:
            try:
                img = Image.open(image_path)
                # Extract text from image
                text = pytesseract.image_to_string(img, config='--psm 3')
                return text.strip()
            except Exception as e:
                logger.error(f"Local OCR extraction failed: {e}. Falling back to Cloud OCR.")
        
        # Cloud AI Fallback
        return self._cloud_ocr_fallback(image_path)

    def _cloud_ocr_fallback(self, image_path: str) -> str:
        logger.info("Using Cloud AI fallback for OCR extraction...")
        from opendesk.config import GEMINI_API_KEY
        if not GEMINI_API_KEY:
            logger.error("Cloud OCR failed: GEMINI_API_KEY not found.")
            return ""
        
        try:
            import base64
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage
            
            with open(image_path, "rb") as image_file:
                image_b64 = base64.b64encode(image_file.read()).decode('utf-8')
                
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", 
                google_api_key=GEMINI_API_KEY, 
                temperature=0.0
            )
            
            msg = HumanMessage(content=[
                {"type": "text", "text": "Extract all readable text from this image. Do your best to interpret names, chats, and general text. Output ONLY the extracted text with no other explanations, formatting, or markdown backticks."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ])
            
            response = llm.invoke([msg])
            text = response.content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            return text.strip()
        except Exception as e:
            logger.error(f"Cloud OCR fallback failed: {e}")
            return ""
    
    def extract_keywords(self, text: str) -> str:
        if not text:
            return ""
        
        # Remove common words
        stop_words = {
            "the", "a", "an", "is", "are",
            "was", "were", "be", "been",
            "have", "has", "had", "do",
            "does", "did", "will", "would",
            "could", "should", "may", "might",
            "and", "or", "but", "in", "on",
            "at", "to", "for", "of", "with"
        }
        
        words = text.lower().split()
        keywords = [
            w for w in words
            if len(w) > 3
            and w not in stop_words
            and w.isalpha()
        ]
        
        # Remove duplicates keep order
        seen = set()
        unique = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        
        return " ".join(unique[:50])
    
    def analyze_screenshot(self, screenshot_path: str) -> dict:
        if not os.path.exists(screenshot_path):
            logger.warning(f"Screenshot not found: {screenshot_path}")
            return {}
        
        logger.info(f"Running OCR on: {os.path.basename(screenshot_path)}")
        
        # Extract text
        text = self.extract_text(screenshot_path)
        keywords = self.extract_keywords(text)
        
        if not text:
            logger.warning("No text found in screenshot")
            return {}
        
        # Save to database via the singleton connection
        try:
            conn = db.get_cursor().connection if hasattr(db.get_cursor(), 'connection') else db.connect()
            cursor = db.get_cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO
                screenshot_ocr
                (screenshot_path, extracted_text,
                keywords, captured_at, analyzed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                screenshot_path,
                text,
                keywords,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            db.commit()
            
            logger.info(f"OCR saved! Found {len(text)} characters")
            
            return {
                "text": text,
                "keywords": keywords,
                "path": screenshot_path
            }
            
        except Exception as e:
            logger.error(f"OCR DB save error: {e}")
            return {}
    
    def analyze_in_background(self, screenshot_path: str):
        thread = threading.Thread(
            target=self.analyze_screenshot,
            args=(screenshot_path,),
            daemon=True,
            name="OCRAnalyzer"
        )
        thread.start()
        logger.info("OCR analysis started in background")
    
    def search_screenshots(self, query: str) -> list:
        cursor = db.get_cursor()
        
        results = cursor.execute("""
            SELECT screenshot_path,
                   extracted_text,
                   captured_at
            FROM screenshot_ocr
            WHERE LOWER(extracted_text) LIKE LOWER(?)
            OR LOWER(keywords) LIKE LOWER(?)
            ORDER BY captured_at DESC
            LIMIT 5
        """, (
            f"%{query}%",
            f"%{query}%"
        )).fetchall()
        
        return results
    
    def get_screenshot_text(self, screenshot_path: str) -> str:
        cursor = db.get_cursor()
        
        result = cursor.execute("""
            SELECT extracted_text
            FROM screenshot_ocr
            WHERE screenshot_path = ?
        """, (screenshot_path,)).fetchone()
        
        return result[0] if result else ""

# Global instance
ocr_analyzer = OCRAnalyzer()
