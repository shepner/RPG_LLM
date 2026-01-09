#!/bin/bash
# Test script for Mattermost integration

set -e

echo "=== Mattermost Integration Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker ps >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is running${NC}"
echo ""

# Check if services are running
echo "=== Checking Services ==="
SERVICES=("mattermost_db:PostgreSQL" "mattermost:Mattermost" "mattermost_bot:Mattermost Bot")

for service in "${SERVICES[@]}"; do
    IFS=':' read -r service_name display_name <<< "$service"
    if docker-compose ps | grep -q "$service_name.*Up"; then
        echo -e "${GREEN}✅ $display_name is running${NC}"
    else
        echo -e "${YELLOW}⚠️  $display_name is not running${NC}"
    fi
done

echo ""

# Test Mattermost bot health
echo "=== Testing Mattermost Bot Service ==="
if curl -s --connect-timeout 3 "http://localhost:8008/health" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Mattermost Bot service is responding${NC}"
    curl -s "http://localhost:8008/health" | python3 -m json.tool 2>/dev/null || echo "Health check response received"
else
    echo -e "${RED}❌ Mattermost Bot service is not responding${NC}"
    echo "   Check logs with: docker-compose logs mattermost_bot"
fi

echo ""

# Test Mattermost server
echo "=== Testing Mattermost Server ==="
if curl -s --connect-timeout 3 "http://localhost:8065/api/v4/system/ping" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Mattermost server is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Mattermost server may not be ready yet${NC}"
    echo "   Access Mattermost at: http://localhost:8065"
    echo "   Wait for initial setup to complete"
fi

echo ""

# Check environment variables
echo "=== Checking Configuration ==="
if [ -f .env ]; then
    if grep -q "MATTERMOST_BOT_TOKEN" .env; then
        echo -e "${GREEN}✅ MATTERMOST_BOT_TOKEN is set${NC}"
    else
        echo -e "${YELLOW}⚠️  MATTERMOST_BOT_TOKEN not found in .env${NC}"
        echo "   You need to:"
        echo "   1. Start Mattermost: docker-compose up -d mattermost"
        echo "   2. Create bot account in Mattermost"
        echo "   3. Add MATTERMOST_BOT_TOKEN to .env"
    fi
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
fi

echo ""

# Summary
echo "=== Test Summary ==="
echo ""
echo "Next steps:"
echo "1. Start all services: docker-compose up -d"
echo "2. Access Mattermost: http://localhost:8065"
echo "3. Create admin account (first time only)"
echo "4. Create bot account and get token"
echo "5. Add MATTERMOST_BOT_TOKEN to .env"
echo "6. Restart mattermost_bot: docker-compose restart mattermost_bot"
echo ""
echo "For detailed setup, see: docs/MATTERMOST_INTEGRATION.md"
