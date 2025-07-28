# Project Files Summary
## Adobe India Hackathon 2025 - Challenge 1a: Multi-OCR PDF Processing Solution

### Core Implementation Files

1. **process_pdfs.py** (Original implementation)
   - Main PDF processing script with full multi-OCR ensemble approach
   - Comprehensive error handling and logging
   - Suitable for development and testing

2. **process_pdfs_optimized.py** (Production-ready)
   - Optimized version targeting 10-second constraint for 50-page PDFs
   - Streamlined processing pipeline
   - Memory and performance optimizations
   - This is the version used in the Docker container

### Configuration Files

3. **Dockerfile**
   - Multi-stage Docker build configuration
   - Based on Python 3.10-slim for minimal size
   - Includes all necessary system dependencies (Tesseract, Poppler, etc.)
   - Optimized for AMD64 architecture

4. **requirements.txt**
   - Python package dependencies
   - Pinned versions for reproducibility
   - Includes PyMuPDF, OCR libraries, and image processing tools

### Documentation

5. **README_project.md**
   - Comprehensive project documentation
   - Technical architecture explanation
   - Performance specifications and optimization techniques
   - Usage instructions and troubleshooting guide

6. **output_schema.json**
   - JSON Schema definition for output validation
   - Defines structure of extracted content
   - Used for automated validation of results

### Testing and Deployment

7. **build_and_test.sh**
   - Automated build and test script
   - Docker image building
   - Output validation
   - Performance checking
   - Executable bash script with colored output

8. **sample_output.json**
   - Example of expected JSON output format
   - Demonstrates heading classification (h1, h2, h3)
   - Shows bounding box coordinates and confidence scores

### Key Features Implemented

✅ **Multi-OCR Ensemble**: Tesseract + EasyOCR + PaddleOCR (optional)
✅ **Parallel Processing**: Multiple OCR engines on different CPU cores
✅ **Page-level Parallelization**: Different PDF pages processed simultaneously
✅ **IoU-based Overlap Detection**: Bounding box overlap with configurable threshold
✅ **Font-size Heading Classification**: Hardcoded thresholds for h1, h2, h3
✅ **10-Second Time Constraint**: Optimized for 50-page PDF processing
✅ **Docker Containerization**: Full Docker support with AMD64 architecture
✅ **JSON Schema Compliance**: Validated output format
✅ **Performance Monitoring**: Processing time tracking and optimization

### Usage Instructions

1. **Quick Start**:
   ```bash
   ./build_and_test.sh
   ```

2. **Manual Docker Build**:
   ```bash
   docker build --platform linux/amd64 -t pdf-processor .
   ```

3. **Run Container**:
   ```bash
   docker run --rm \
     -v $(pwd)/input:/app/input:ro \
     -v $(pwd)/output:/app/output \
     --network none \
     pdf-processor
   ```

### Performance Targets

- **Processing Time**: ≤ 10 seconds for 50-page PDF
- **Memory Usage**: ≤ 16 GB RAM
- **CPU Utilization**: All 8 available cores
- **Model Size**: ≤ 200 MB
- **Architecture**: AMD64 compatible

### Technical Approach

The solution uses a **multi-level parallel processing** approach:

1. **PDF Page Extraction**: Fast page-to-image conversion using PyMuPDF
2. **Parallel OCR Processing**: Multiple OCR engines running on different CPU cores
3. **Ensemble Voting**: IoU-based consensus mechanism for overlapping detections
4. **Heading Classification**: Statistical font size analysis with hardcoded thresholds
5. **JSON Output**: Structured format with confidence scores and metadata

This implementation successfully meets all the challenge requirements while maintaining high accuracy through the ensemble approach and meeting the strict time constraints through aggressive optimization.
