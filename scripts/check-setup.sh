#!/bin/bash
# Check setup completion

set -e

echo "Checking setup..."

# Check data directories
if [ ! -d "./RPG_LLM_DATA" ]; then
    echo "ERROR: RPG_LLM_DATA directory not found. Run ./scripts/setup.sh first."
    exit 1
fi

# Check .env file
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Copy .env.example to .env and fill in your secrets."
fi

# Check config
if [ ! -f "config/config.yaml" ]; then
    echo "WARNING: config/config.yaml not found. Copy config.yaml.example to config.yaml."
fi

echo "Setup check complete!"

