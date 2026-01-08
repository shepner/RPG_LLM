#!/bin/bash
# Test script for session management features

set -e

echo "=== Session Management Tests ==="
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
SESSION_URL="http://localhost:8001"
REGISTRY_URL="http://localhost:8007"

# Test 1: Register and login
echo "=== Test 1: Authentication ==="
echo "Registering test user..."
REGISTER_RESPONSE=$(curl -s -X POST ${AUTH_URL}/register \
    -H "Content-Type: application/json" \
    -d '{"username":"sessiontest","email":"sessiontest@example.com","password":"testpass123","role":"player"}')

TOKEN=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('access_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Trying login instead..."
    LOGIN_RESPONSE=$(curl -s -X POST ${AUTH_URL}/login \
        -H "Content-Type: application/json" \
        -d '{"username":"sessiontest","password":"testpass123"}')
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
    -d '{"name":"Test Session","description":"Test session for session management","game_system_type":"D&D 5e"}')

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
JOIN_RESPONSE=$(curl -s -X POST "${SESSION_URL}/sessions/${SESSION_ID}/join?user_id=${USER_ID}" \
    -H "Authorization: Bearer $TOKEN")

if echo "$JOIN_RESPONSE" | grep -q "message\|success"; then
    echo -e "${GREEN}✅ Successfully joined session${NC}"
else
    echo -e "${YELLOW}⚠️  Join response: $JOIN_RESPONSE${NC}"
fi
echo ""

# Test 5: List sessions
echo "=== Test 5: List Sessions ==="
SESSIONS_RESPONSE=$(curl -s "${SESSION_URL}/sessions")
SESSION_COUNT=$(echo "$SESSIONS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" 2>/dev/null)

if [ "$SESSION_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Found $SESSION_COUNT session(s)${NC}"
else
    echo -e "${YELLOW}⚠️  No sessions found${NC}"
fi
echo ""

# Test 6: Leave session
echo "=== Test 6: Leave Session ==="
LEAVE_RESPONSE=$(curl -s -X POST "${SESSION_URL}/sessions/${SESSION_ID}/leave?user_id=${USER_ID}" \
    -H "Authorization: Bearer $TOKEN")

if echo "$LEAVE_RESPONSE" | grep -q "message\|success\|Left"; then
    echo -e "${GREEN}✅ Successfully left session${NC}"
else
    echo -e "${YELLOW}⚠️  Leave response: $LEAVE_RESPONSE${NC}"
fi
echo ""

# Test 7: Create character in session
echo "=== Test 7: Create Character in Session ==="
# Re-join session first
curl -s -X POST "${SESSION_URL}/sessions/${SESSION_ID}/join?user_id=${USER_ID}" \
    -H "Authorization: Bearer $TOKEN" > /dev/null

CHAR_CREATE_RESPONSE=$(curl -s -X POST "${REGISTRY_URL}/beings/create" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"Test Character\",\"session_id\":\"${SESSION_ID}\",\"game_system\":\"D&D 5e\",\"automatic\":true}")

CHAR_BEING_ID=$(echo "$CHAR_CREATE_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('being_id', ''))" 2>/dev/null)

if [ -n "$CHAR_BEING_ID" ]; then
    echo -e "${GREEN}✅ Character created: $CHAR_BEING_ID${NC}"
else
    echo -e "${YELLOW}⚠️  Character creation response: $CHAR_CREATE_RESPONSE${NC}"
fi
echo ""

# Test 8: Get vicinity (beings in session)
echo "=== Test 8: Get Beings in Session ==="
VICINITY_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "${REGISTRY_URL}/beings/vicinity/${SESSION_ID}")
VICINITY_COUNT=$(echo "$VICINITY_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); beings=data.get('beings', []); print(len(beings))" 2>/dev/null)

if [ "$VICINITY_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Found $VICINITY_COUNT being(s) in session${NC}"
else
    echo -e "${YELLOW}⚠️  No beings found in session${NC}"
fi
echo ""

# Summary
echo "=== Test Summary ==="
echo -e "${GREEN}✅ Session management tests completed${NC}"
echo ""
echo "Session ID: $SESSION_ID"
echo "Character ID: $CHAR_BEING_ID"
echo ""
echo "You can now test in the web interface at http://localhost:8080"
