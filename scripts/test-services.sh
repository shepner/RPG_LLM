#!/bin/bash
# Test script for TTRPG LLM System services

set -e

echo "=== TTRPG LLM System Service Tests ==="
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

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Test health endpoints
echo ""
echo "=== Health Check Tests ==="
SERVICES=("8000:Auth" "8001:Game Session" "8002:Rules Engine" "8003:Time Management" "8004:Worlds" "8005:Game Master" "8006:Being" "8007:Being Registry")

for service in "${SERVICES[@]}"; do
    IFS=':' read -r port name <<< "$service"
    if curl -s --connect-timeout 3 "http://localhost:$port/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ $name (port $port)${NC}"
    else
        echo -e "${RED}❌ $name (port $port)${NC}"
    fi
done

# Test Auth Service
echo ""
echo "=== Testing Auth Service ==="
echo "1. Registering test user..."
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/register \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","email":"test@example.com","password":"testpass123","role":"player"}')

if echo "$REGISTER_RESPONSE" | grep -q "user_id"; then
    echo -e "${GREEN}✅ User registration successful${NC}"
else
    echo -e "${RED}❌ User registration failed${NC}"
    echo "$REGISTER_RESPONSE"
fi

echo ""
echo "2. Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/login \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"testpass123"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✅ Login successful${NC}"
    echo "3. Testing authenticated endpoint..."
    ME_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/me)
    if echo "$ME_RESPONSE" | grep -q "user_id"; then
        echo -e "${GREEN}✅ Authenticated endpoint works${NC}"
    else
        echo -e "${RED}❌ Authenticated endpoint failed${NC}"
    fi
else
    echo -e "${RED}❌ Login failed${NC}"
    echo "$LOGIN_RESPONSE"
fi

# Test Game Session Service
echo ""
echo "=== Testing Game Session Service ==="
echo "Listing sessions..."
SESSION_RESPONSE=$(curl -s http://localhost:8001/sessions)
if echo "$SESSION_RESPONSE" | grep -q "\[\]"; then
    echo -e "${GREEN}✅ Session listing works (empty list)${NC}"
else
    echo "$SESSION_RESPONSE"
fi

# Test Rules Engine
echo ""
echo "=== Testing Rules Engine ==="
echo "Testing dice roll..."
DICE_RESPONSE=$(curl -s -X POST "http://localhost:8002/roll?dice=1d20")
if echo "$DICE_RESPONSE" | grep -q "result\|total"; then
    echo -e "${GREEN}✅ Dice roll works${NC}"
    echo "$DICE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DICE_RESPONSE"
else
    echo -e "${YELLOW}⚠️  Dice roll response:${NC}"
    echo "$DICE_RESPONSE"
fi

# Test Web Interface
echo ""
echo "=== Testing Web Interface ==="
WEB_RESPONSE=$(curl -s http://localhost:8080 | head -5)
if echo "$WEB_RESPONSE" | grep -q "html\|DOCTYPE"; then
    echo -e "${GREEN}✅ Web interface is accessible${NC}"
    echo "Access at: http://localhost:8080"
else
    echo -e "${RED}❌ Web interface not accessible${NC}"
fi

# Summary
echo ""
echo "=== Test Summary ==="
echo "Check service logs with: docker-compose logs [service_name]"
echo "View all services: docker-compose ps"
echo "Stop services: docker-compose down"

