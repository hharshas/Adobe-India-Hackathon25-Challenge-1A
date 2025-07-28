FROM --platform=linux/amd64 python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .

# --- MODIFIED: Resolve all dependency conflicts and pre-download models ---
RUN \
    # 1. Remove conflicting paddle packages that are not used by the final script
    sed -i '/paddlepaddle/d' requirements.txt && \
    sed -i '/paddleocr/d' requirements.txt && \
    \
    # 2. Force a compatible Pillow version for EasyOCR to fix the ANTIALIAS error
    sed -i 's/Pillow==.*/Pillow==9.5.0/' requirements.txt && \
    \
    # 3. Install the resolved dependencies
    pip install --no-cache-dir -r requirements.txt && \
    \
    # 4. Pre-download EasyOCR models so the container can run offline
    python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# Copy the main processing script
COPY process_pdfs.py .

# Set environment variables for better performance
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

# Run the processing script
CMD ["python", "process_pdfs.py"]
