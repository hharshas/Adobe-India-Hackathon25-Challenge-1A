#!/bin/bash

# Adobe India Hackathon 2025 - Challenge 1a
# Build and test script for Multi-OCR PDF Processing Solution

set -e  # Exit on any error

echo "🚀 Adobe India Hackathon 2025 - PDF Processing Solution"
echo "======================================================"

# Configuration
IMAGE_NAME="pdf-processor"
TAG="latest"
CONTAINER_NAME="pdf-processor-test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if Docker is installed and running
check_docker() {
    print_status "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker service."
    fi
    print_success "Docker is ready"
}

# Build the Docker image
build_image() {
    print_status "Building Docker image: ${IMAGE_NAME}:${TAG}"
    # Use the optimized version as the main script
    if [ ! -f "process_pdfs_optimized.py" ]; then
        print_error "Optimized script 'process_pdfs_optimized.py' not found."
    fi
    cp process_pdfs_optimized.py process_pdfs.py
    docker build --platform linux/amd64 -t ${IMAGE_NAME}:${TAG} . || print_error "Docker build failed"
    print_success "Docker image built successfully"
}

# Create test directories
setup_test_env() {
    print_status "Setting up test environment..."
    mkdir -p test/input
    mkdir -p test/output
    # Create a simple test PDF if none exists and pandoc is available
    if [ ! "$(ls -A test/input/)" ] && command -v pandoc &> /dev/null; then
        print_status "No PDFs found in test/input. Creating a sample PDF with pandoc..."
        echo "This is a test document. # Main Title. ## Section 1. ### Subsection 1.1" | pandoc -o test/input/sample.pdf &>/dev/null || {
            print_warning "Could not create test PDF. Please place test PDFs in test/input/ directory."
        }
    elif [ ! "$(ls -A test/input/)" ]; then
        print_warning "No PDFs found in 'test/input' and pandoc is not installed. Please add a PDF to test/input."
    fi
    print_success "Test environment ready"
}

# Run the container
run_test() {
    print_status "Running PDF processing test..."
    docker rm -f ${CONTAINER_NAME} 2>/dev/null || true
    start_time=$(date +%s)
    docker run --name ${CONTAINER_NAME} --rm \
        -v "$(pwd)/test/input:/app/input:ro" \
        -v "$(pwd)/test/output:/app/output" \
        --network none \
        ${IMAGE_NAME}:${TAG} || print_error "Container execution failed"
    end_time=$(date +%s)
    execution_time=$((end_time - start_time))
    print_success "Container execution completed in ${execution_time} seconds"
}

# Validate output
validate_output() {
    print_status "Validating output..."
    if [ ! "$(ls -A test/output/)" ]; then
        print_error "No JSON output files found in test/output."
    fi
    print_success "Found $(find test/output -name "*.json" | wc -l) JSON output file(s)"

    # Validate JSON structure for the new format
    for json_file in test/output/*.json; do
        if [ -f "$json_file" ]; then
            print_status "Validating $json_file"
            if ! python3 -m json.tool "$json_file" > /dev/null 2>&1; then
                print_error "Invalid JSON format in $json_file"
            fi
            # --- CORRECTED: Check for 'title' and 'outline' fields ---
            if ! python3 -c "
import json, sys
with open('$json_file') as f: data = json.load(f)
required_fields = ['title', 'outline']
missing = [f for f in required_fields if f not in data]
if missing:
    print(f'Missing required fields: {missing}')
    sys.exit(1)
"
            then
                print_error "JSON structure validation failed for $json_file"
            fi
            print_success "JSON validation passed for $json_file"
        fi
    done
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."
    docker rm -f ${CONTAINER_NAME} 2>/dev/null || true
    rm -f process_pdfs.py  # Remove the copied file
}

# Main execution
main() {
    trap cleanup EXIT
    check_docker
    build_image
    setup_test_env
    run_test
    validate_output
    echo
    print_success "All tests passed! 🎉 Your solution is ready for submission!"
}

main
