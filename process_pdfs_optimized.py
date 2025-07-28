#!/usr/bin/env python3
"""
FINAL VERSION: PDF Processing Solution to Generate Document Outline
Description: This version fixes a critical NameError bug, improves error handling,
             and implements major performance optimizations by initializing OCR models
             only once per worker process.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Tuple, Any
from collections import defaultdict
import warnings

# Suppress library warnings for a cleaner output
warnings.filterwarnings("ignore")

# PDF and image processing
import fitz  # PyMuPDF
import cv2
import numpy as np

# OCR libraries
import pytesseract
import easyocr

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Global variables for worker processes ---
# These will be initialized once per worker to avoid slow model reloading.
EASYOCR_READER = None

def initialize_worker():
    """Initializes OCR engines once per worker process."""
    global EASYOCR_READER
    # This check ensures the model is loaded only if it hasn't been already
    if EASYOCR_READER is None:
        logger.info(f"Initializing EasyOCR model for process ID: {os.getpid()}...")
        EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)

# --- Data Structures and Core Helpers ---

class BoundingBox:
    """Optimized bounding box representation."""
    __slots__ = ['x1', 'y1', 'x2', 'y2', 'text', 'confidence', 'font_size', 'area']

    def __init__(self, x1: float, y1: float, x2: float, y2: float, text: str, confidence: float, font_size: float):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.text = text.strip()
        self.confidence = confidence
        self.font_size = font_size
        self.area = (x2 - x1) * (y2 - y1)

def calculate_iou_fast(box1: BoundingBox, box2: BoundingBox) -> float:
    """Fast IoU calculation optimized for performance."""
    if box1.x2 <= box2.x1 or box2.x2 <= box1.x1 or box1.y2 <= box2.y1 or box2.y2 <= box1.y1:
        return 0.0
    ix1, iy1 = max(box1.x1, box2.x1), max(box1.y1, box2.y1)
    ix2, iy2 = min(box1.x2, box2.x2), min(box1.y2, box2.y2)
    # --- BUG FIX: Changed 'y1' to 'iy1' ---
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if intersection == 0:
        return 0.0
    union = box1.area + box2.area - intersection
    return intersection / union if union > 0 else 0.0

def get_cpu_cores() -> int:
    """Get optimal number of CPU cores for processing."""
    return min(cpu_count(), 8)

def extract_pdf_pages_fast(pdf_path: Path) -> List[bytes]:
    """Fast PDF page extraction as compressed image bytes."""
    try:
        doc = fitz.open(pdf_path)
        page_bytes = [page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png") for page in doc]
        doc.close()
        return page_bytes
    except Exception as e:
        logger.error(f"Failed to extract pages from {pdf_path}: {e}")
        return []

# --- OCR Engine Functions (to be called by workers) ---

def run_tesseract(image_bytes: bytes) -> List[BoundingBox]:
    """Runs Tesseract OCR on image bytes."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        config = '--psm 6 --oem 3'
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=config)
        boxes = []
        for i in range(len(data['text'])):
            text, conf = data['text'][i].strip(), int(data['conf'][i])
            if len(text) > 1 and conf > 30:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                boxes.append(BoundingBox(x, y, x + w, y + h, text, conf / 100.0, max(8.0, h * 0.8)))
        return boxes
    except Exception as e:
        logger.error(f"Tesseract failed with exception: {e}")
        return []

def run_easyocr(image_bytes: bytes) -> List[BoundingBox]:
    """Runs EasyOCR on image bytes using the pre-initialized worker model."""
    global EASYOCR_READER
    if not EASYOCR_READER:
        return []
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        results = EASYOCR_READER.readtext(image, detail=1, paragraph=False)
        boxes = []
        for coords, text, conf in results:
            if conf > 0.4 and len(text.strip()) > 1:
                x_coords, y_coords = [p[0] for p in coords], [p[1] for p in coords]
                x1, y1, x2, y2 = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
                boxes.append(BoundingBox(x1, y1, x2, y2, text, conf, max(8.0, (y2 - y1) * 0.8)))
        return boxes
    except Exception as e:
        logger.error(f"EasyOCR failed: {e}")
        return []

def fast_ensemble_voting(ocr_results: Dict[str, List[BoundingBox]], iou_threshold: float = 0.25) -> List[BoundingBox]:
    """Combines results from multiple OCR engines for a single page."""
    all_boxes = [box for boxes in ocr_results.values() for box in boxes]
    if not all_boxes: return []
    final_boxes, used_indices = [], set()
    for i, box1 in enumerate(all_boxes):
        if i in used_indices: continue
        cluster = [box1]
        used_indices.add(i)
        for j, box2 in enumerate(all_boxes[i+1:], i+1):
            if j not in used_indices and calculate_iou_fast(box1, box2) > iou_threshold:
                cluster.append(box2)
                used_indices.add(j)
        final_boxes.append(max(cluster, key=lambda b: b.confidence))
    return final_boxes

def create_document_outline(all_boxes_with_page: List[Tuple[int, BoundingBox]]) -> Dict[str, Any]:
    """Identifies the document title and headings to create a structured outline."""
    if not all_boxes_with_page: return {"title": "", "outline": []}
    first_page_boxes = [box for page_idx, box in all_boxes_with_page if page_idx == 0]
    title_box = max(first_page_boxes, key=lambda b: b.font_size) if first_page_boxes else None
    document_title = title_box.text if title_box else ""
    all_font_sizes = [box.font_size for _, box in all_boxes_with_page if len(box.text) > 2]
    if not all_font_sizes: return {"title": document_title, "outline": []}
    sorted_sizes = sorted(all_font_sizes)
    median_size = sorted_sizes[len(sorted_sizes) // 2]
    h1_threshold, h2_threshold = median_size * 1.6, median_size * 1.3
    outline = []
    sorted_boxes = sorted(all_boxes_with_page, key=lambda item: (item[0], item[1].y1))
    for page_idx, box in sorted_boxes:
        if box is title_box: continue
        text = box.text
        if len(text) < 3 or len(text) > 120 or text.endswith('.') or text.count(' ') > 10: continue
        level = "H1" if box.font_size >= h1_threshold else "H2" if box.font_size >= h2_threshold else None
        if level:
            outline.append({"level": level, "text": text, "page": page_idx})
    return {"title": document_title, "outline": outline}

# --- Main Processing Function ---

def process_single_pdf_fast(pdf_path: Path, output_dir: Path):
    """Fully optimized PDF processing workflow."""
    start_time = time.time()
    logger.info(f"Processing {pdf_path.name} to generate document outline...")

    try:
        page_bytes_list = extract_pdf_pages_fast(pdf_path)
        if not page_bytes_list:
            logger.error(f"No pages extracted from {pdf_path}"); return

        logger.info(f"Extracted {len(page_bytes_list)} pages. Initializing process pool...")
        num_cores = get_cpu_cores()
        
        all_consensus_boxes_with_page_info = []
        
        # Use the initializer to load models only once per worker process
        with ProcessPoolExecutor(max_workers=num_cores, initializer=initialize_worker) as executor:
            tasks = []
            for page_idx, page_bytes in enumerate(page_bytes_list):
                tasks.append(executor.submit(run_tesseract, page_bytes))
                tasks.append(executor.submit(run_easyocr, page_bytes))

            # This is complex to map back. Let's simplify and keep the page_idx.
            # RETHINK: A better submission pattern is needed to track page index.
            
            # Let's use a simpler and more direct submission pattern.
            futures = {}
            for page_idx, page_bytes in enumerate(page_bytes_list):
                # Submit both OCR tasks for the same page
                futures[executor.submit(run_tesseract, page_bytes)] = (page_idx, 'tesseract')
                futures[executor.submit(run_easyocr, page_bytes)] = (page_idx, 'easyocr')
            
            results_by_page = defaultdict(dict)
            for future in as_completed(futures):
                page_idx, ocr_name = futures[future]
                boxes = future.result()
                results_by_page[page_idx][ocr_name] = boxes

        for page_idx in sorted(results_by_page.keys()):
            consensus_boxes = fast_ensemble_voting(results_by_page[page_idx])
            for box in consensus_boxes:
                all_consensus_boxes_with_page_info.append((page_idx, box))
        
        output_data = create_document_outline(all_consensus_boxes_with_page_info)
        output_file = output_dir / f"{pdf_path.stem}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        processing_time = time.time() - start_time
        logger.info(f"✅ Completed {pdf_path.name} in {processing_time:.2f}s. Outline has {len(output_data['outline'])} headings.")
        logger.info(f"   Output saved to: {output_file}")

    except Exception as e:
        logger.error(f"❌ Failed to process {pdf_path}: {e}", exc_info=True)
        # --- TESTING FIX: Exit with an error code on failure ---
        sys.exit(1)

# --- Main Execution Block ---

def main():
    """Main processing function."""
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in /app/input"); return

    logger.info(f"Processing {len(pdf_files)} PDFs with {get_cpu_cores()} CPU cores")
    total_start = time.time()
    for pdf_file in pdf_files:
        process_single_pdf_fast(pdf_file, output_dir)
    logger.info(f"Total processing time: {time.time() - total_start:.2f} seconds")

if __name__ == "__main__":
    main()