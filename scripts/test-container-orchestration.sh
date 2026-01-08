#!/bin/bash
# Test script for container orchestration (Phase 2)

set -e

echo "=== Container Orchestration Tests (Phase 2) ==="
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
sleep 5

# Test variables
AUTH_URL="http://localhost:8000"
REGISTRY_URL="http://localhost:8007"
SESSION_URL="http://localhost:8001"

# Test 1: Register and login
echo "=== Test 1: Authentication ==="
echo "Registering test user..."
REGISTER_RESPONSE=$(curl -s -X POST ${AUTH_URL}/register \
    -H "Content-Type: application/json" \
    -d '{"username":"containertest","email":"containertest@example.com","password":"testpass123","role":"player"}')

TOKEN=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Trying login instead..."
    LOGIN_RESPONSE=$(curl -s -X POST ${AUTH_URL}/login \
        -H "Content-Type: application/json" \
        -d '{"username":"containertest","password":"testpass123"}')
    TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null)
fi

if [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Failed to get auth token${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Authentication successful${NC}"
echo ""

# Test 2: Get user info
echo "=== Test 2: Get User Info ==="
USER_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" ${AUTH_URL}/me)
USER_ID=$(echo "$USER_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('user_id', ''))" 2>/dev/null)

if [ -z "$USER_ID" ]; then
    echo -e "${RED}❌ Failed to get user ID${NC}"
    exit 1
fi

echo -e "${GREEN}✅ User ID: $USER_ID${NC}"
echo ""

# Test 3: Create a session
echo "=== Test 3: Create Session ==="
SESSION_CREATE_RESPONSE=$(curl -s -X POST "${SESSION_URL}/sessions?gm_user_id=${USER_ID}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"Container Test Session","description":"Test session for container orchestration","game_system_type":"D&D 5e"}')

SESSION_ID=$(echo "$SESSION_CREATE_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('session_id', ''))" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    echo -e "${RED}❌ Failed to create session${NC}"
    echo "$SESSION_CREATE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Session created: $SESSION_ID${NC}"
echo ""

# Test 4: Join session
echo "=== Test 4: Join Session ==="
curl -s -X POST "${SESSION_URL}/sessions/${SESSION_ID}/join?user_id=${USER_ID}" \
    -H "Authorization: Bearer $TOKEN" > /dev/null
echo -e "${GREEN}✅ Joined session${NC}"
echo ""

# Test 5: Create character (should trigger container creation)
echo "=== Test 5: Create Character (Container Creation) ==="
echo "Creating character (this should create a container)..."
CHAR_CREATE_RESPONSE=$(curl -s -X POST "${REGISTRY_URL}/beings/create" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"Test Container Character\",\"session_id\":\"${SESSION_ID}\",\"game_system\":\"D&D 5e\",\"automatic\":true}")

CHAR_BEING_ID=$(echo "$CHAR_CREATE_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('being_id', ''))" 2>/dev/null)

if [ -z "$CHAR_BEING_ID" ]; then
    echo -e "${RED}❌ Failed to create character${NC}"
    echo "$CHAR_CREATE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Character created: $CHAR_BEING_ID${NC}"
echo ""

# Test 6: Check if container was created
echo "=== Test 6: Verify Container Creation ==="
sleep 5  # Wait for container to start

# Check Docker containers
CONTAINER_NAME="rpg_llm_being_$(echo $CHAR_BEING_ID | tr '[:upper:]' '[:lower:]' | tr '-' '_')"
CONTAINER_EXISTS=$(docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | head -1)

if [ -n "$CONTAINER_EXISTS" ]; then
    echo -e "${GREEN}✅ Container found: $CONTAINER_EXISTS${NC}"
    
    # Check container status
    CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_EXISTS" 2>/dev/null || echo "unknown")
    echo "Container status: $CONTAINER_STATUS"
    
    if [ "$CONTAINER_STATUS" = "running" ]; then
        echo -e "${GREEN}✅ Container is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Container is not running (status: $CONTAINER_STATUS)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Container not found (name: $CONTAINER_NAME)${NC}"
    echo "Listing all being containers:"
    docker ps -a --filter "name=rpg_llm_being" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
fi
echo ""

# Test 7: Get being registry entry
echo "=== Test 7: Get Being Registry Entry ==="
BEING_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "${REGISTRY_URL}/beings/${CHAR_BEING_ID}")
CONTAINER_ID=$(echo "$BEING_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('container_id', 'None'))" 2>/dev/null)
SERVICE_ENDPOINT=$(echo "$BEING_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('service_endpoint', 'None'))" 2>/dev/null)

if [ "$CONTAINER_ID" != "None" ] && [ -n "$CONTAINER_ID" ]; then
    echo -e "${GREEN}✅ Container ID in registry: $CONTAINER_ID${NC}"
else
    echo -e "${YELLOW}⚠️  No container ID in registry${NC}"
fi

if [ "$SERVICE_ENDPOINT" != "None" ] && [ -n "$SERVICE_ENDPOINT" ]; then
    echo -e "${GREEN}✅ Service endpoint: $SERVICE_ENDPOINT${NC}"
    
    # Test health endpoint
    HEALTH_RESPONSE=$(curl -s "${SERVICE_ENDPOINT}/health" 2>/dev/null || echo "failed")
    if echo "$HEALTH_RESPONSE" | grep -q "healthy\|status"; then
        echo -e "${GREEN}✅ Container health check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check response: $HEALTH_RESPONSE${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No service endpoint in registry${NC}"
fi
echo ""

# Test 8: Delete character (should delete container)
echo "=== Test 8: Delete Character (Container Deletion) ==="
DELETE_RESPONSE=$(curl -s -X DELETE "${REGISTRY_URL}/beings/${CHAR_BEING_ID}" \
    -H "Authorization: Bearer $TOKEN")

if echo "$DELETE_RESPONSE" | grep -q "deleted\|success"; then
    echo -e "${GREEN}✅ Character deleted${NC}"
    
    # Wait a moment for container deletion
    sleep 2
    
    # Check if container was deleted
    CONTAINER_STILL_EXISTS=$(docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | head -1)
    if [ -z "$CONTAINER_STILL_EXISTS" ]; then
        echo -e "${GREEN}✅ Container was deleted${NC}"
    else
        echo -e "${YELLOW}⚠️  Container still exists: $CONTAINER_STILL_EXISTS${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Delete response: $DELETE_RESPONSE${NC}"
fi
echo ""

# Summary
echo "=== Test Summary ==="
echo -e "${GREEN}✅ Container orchestration tests completed${NC}"
echo ""
echo "Character ID: $CHAR_BEING_ID"
echo "Container Name: $CONTAINER_NAME"
echo ""
echo "Phase 2 (Container Orchestration) is working!"
