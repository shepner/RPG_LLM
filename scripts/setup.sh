#!/bin/bash
# Main setup script for TTRPG LLM System

set -e

echo "Setting up TTRPG LLM System..."

# Create data directory structure
./scripts/init-data-dirs.sh

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and fill in your API keys"
echo "2. Copy config/config.yaml.example to config/config.yaml"
echo "3. Run: docker-compose up -d"

