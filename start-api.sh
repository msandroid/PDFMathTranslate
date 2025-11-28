#!/bin/bash
# Start PDFMathTranslate API server using Docker Compose

set -e

echo "Starting PDFMathTranslate API server..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo "Error: Docker and docker-compose are required but not installed."
    exit 1
fi

# Use docker compose (v2) if available, otherwise use docker-compose (v1)
if command -v docker &> /dev/null && docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Start services
echo "Building and starting services..."
$COMPOSE_CMD -f docker-compose.api.yml up -d --build

echo ""
echo "API server is starting..."
echo "Waiting for services to be ready..."

# Wait for API server to be ready
sleep 5

# Check if API is responding
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:11008/v1/translate > /dev/null 2>&1 || \
       curl -s -X POST http://localhost:11008/v1/translate > /dev/null 2>&1; then
        echo ""
        echo "✓ API server is ready!"
        echo ""
        echo "API Endpoints:"
        echo "  - POST   http://localhost:11008/v1/translate"
        echo "  - GET    http://localhost:11008/v1/translate/<id>"
        echo "  - GET    http://localhost:11008/v1/translate/<id>/mono"
        echo "  - GET    http://localhost:11008/v1/translate/<id>/dual"
        echo "  - DELETE http://localhost:11008/v1/translate/<id>"
        echo ""
        echo "To view logs: $COMPOSE_CMD -f docker-compose.api.yml logs -f"
        echo "To stop: $COMPOSE_CMD -f docker-compose.api.yml down"
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo ""
echo "⚠ Warning: API server may still be starting up."
echo "Check logs with: $COMPOSE_CMD -f docker-compose.api.yml logs -f api"
echo ""
echo "API Endpoints:"
echo "  - POST   http://localhost:11008/v1/translate"
echo "  - GET    http://localhost:11008/v1/translate/<id>"
echo "  - GET    http://localhost:11008/v1/translate/<id>/mono"
echo "  - GET    http://localhost:11008/v1/translate/<id>/dual"
echo "  - DELETE http://localhost:11008/v1/translate/<id>"


