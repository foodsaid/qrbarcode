#!/bin/bash

# QRBarcode Local Development Script
# Builds and runs the service locally using Docker

set -e  # Exit on error

# Configuration
SERVICE_NAME="qr-service-local"
IMAGE_NAME="qr-service"
PORT="${PORT:-8080}"

echo "======================================="
echo "QRBarcode Local Development Setup"
echo "======================================="
echo ""

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to cleanup existing container
cleanup_container() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${SERVICE_NAME}$"; then
        echo "Removing existing container: ${SERVICE_NAME}..."
        docker rm -f "${SERVICE_NAME}" 2>/dev/null || true
    fi
}

# Function to build image
build_image() {
    echo "Building Docker image: ${IMAGE_NAME}..."
    if ! docker build -t "${IMAGE_NAME}" .; then
        echo "Error: Docker build failed."
        exit 1
    fi
    echo "✓ Build completed successfully"
    echo ""
}

# Function to run container
run_container() {
    echo "Starting service on port ${PORT}..."
    if ! docker run -d \
        -p "${PORT}:${PORT}" \
        -e PORT="${PORT}" \
        --name "${SERVICE_NAME}" \
        --restart unless-stopped \
        "${IMAGE_NAME}"; then
        echo "Error: Failed to start container."
        exit 1
    fi
    echo "✓ Container started successfully"
    echo ""
}

# Function to wait for service to be ready
wait_for_service() {
    echo "Waiting for service to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:${PORT}/health" > /dev/null 2>&1; then
            echo "✓ Service is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo ""
    echo "Warning: Service did not respond to health check within 30 seconds"
    echo "Check logs with: docker logs ${SERVICE_NAME}"
    return 1
}

# Function to show service info
show_info() {
    echo ""
    echo "======================================="
    echo "Service Information"
    echo "======================================="
    echo "Container name: ${SERVICE_NAME}"
    echo "Image name:     ${IMAGE_NAME}"
    echo "Port:           ${PORT}"
    echo ""
    echo "Endpoints:"
    echo "  Health:  http://localhost:${PORT}/health"
    echo "  API:     http://localhost:${PORT}/generate?content=<YOUR_CONTENT>"
    echo ""
    echo "Examples:"
    echo "  curl \"http://localhost:${PORT}/generate?content=Hello\" > qrcode.png"
    echo "  curl \"http://localhost:${PORT}/generate?content=123&type=barcode\" > barcode.png"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    docker logs -f ${SERVICE_NAME}"
    echo "  Stop:         docker stop ${SERVICE_NAME}"
    echo "  Restart:      docker restart ${SERVICE_NAME}"
    echo "  Remove:       docker rm -f ${SERVICE_NAME}"
    echo "======================================="
}

# Main execution
main() {
    check_docker
    cleanup_container
    build_image
    run_container

    if wait_for_service; then
        show_info
    else
        show_info
        exit 1
    fi
}

# Run main function
main
