import os
import sqlite3
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

if not os.path.isfile(_tesseract_cmd) and not shutil.which("tesseract"):
    logger.warning(
        f"Tesseract not found at '{_tesseract_cmd}'. "
        "OCR features will be disabled. "
        "Install Tesseract or set TESSERACT_CMD env var."
    )

pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

class OCRAnalyzer:
    
    def __init__(self):
        # Use the singleton DB — schema.sql already defines screenshot_ocr
        db.connect()
    
    def _setup_db(self):
        # Schema is managed centrally in db/schema.sql — no setup needed here
        logger.debug("OCR database ready")
    
    def extract_text(self, image_path: str) -> str:
        try:
            img = Image.open(image_path)
            
            # Extract text from image
            text = pytesseract.image_to_string(
                img,
                config='--psm 3'
            )
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
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
