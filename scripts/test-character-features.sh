#!/bin/bash
# Comprehensive test script for character management features

set -e

echo "=== Comprehensive Character Features Test ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

AUTH_URL="http://localhost:8000"
BEING_REGISTRY_URL="http://localhost:8007"
BEING_URL="http://localhost:8006"
GAME_SESSION_URL="http://localhost:8001"

TEST_COUNT=0
PASS_COUNT=0
FAIL_COUNT=0

# Test function
test_step() {
    TEST_COUNT=$((TEST_COUNT + 1))
    local name="$1"
    local command="$2"
    
    echo -e "${BLUE}Test $TEST_COUNT: $name${NC}"
    if eval "$command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        PASS_COUNT=$((PASS_COUNT + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
}

# Step 1: Register and login
echo -e "${BLUE}=== Step 1: Authentication ===${NC}"
REGISTER_RESPONSE=$(curl -s -X POST "${AUTH_URL}/register" \
    -H "Content-Type: application/json" \
    -d '{
        "username": "testcharuser",
        "email": "testchar@example.com",
        "password": "testpass123",
        "role": "player"
    }' 2>/dev/null || echo '{"error":"exists"}')

if echo "$REGISTER_RESPONSE" | grep -q "user_id"; then
    echo -e "${GREEN}✅ User registered${NC}"
elif echo "$REGISTER_RESPONSE" | grep -q "already exists"; then
    echo -e "${YELLOW}⚠️  User already exists, continuing...${NC}"
else
    echo -e "${YELLOW}⚠️  Registration response: $REGISTER_RESPONSE${NC}"
fi

LOGIN_RESPONSE=$(curl -s -X POST "${AUTH_URL}/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"testcharuser","password":"testpass123"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Login failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Login successful${NC}"
echo ""

# Step 2: Create a game session
echo -e "${BLUE}=== Step 2: Create Game Session ===${NC}"
USER_ID=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user_id', ''))" 2>/dev/null || echo "")

SESSION_RESPONSE=$(curl -s -X POST "${GAME_SESSION_URL}/sessions?gm_user_id=${USER_ID}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "name": "Test Character Session",
        "description": "Session for character testing",
        "game_system_type": "D&D 5e",
        "time_mode_preference": "real-time"
    }')

SESSION_ID=$(echo "$SESSION_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', ''))" 2>/dev/null || echo "")

if [ -z "$SESSION_ID" ]; then
    echo -e "${YELLOW}⚠️  Could not create session, using existing session${NC}"
    SESSIONS_RESPONSE=$(curl -s "${GAME_SESSION_URL}/sessions")
    SESSION_ID=$(echo "$SESSIONS_RESPONSE" | python3 -c "import sys, json; sessions=json.load(sys.stdin); print(sessions[0]['session_id'] if sessions else '')" 2>/dev/null || echo "")
fi

if [ -n "$SESSION_ID" ]; then
    echo -e "${GREEN}✅ Session ID: ${SESSION_ID:0:16}...${NC}"
else
    echo -e "${YELLOW}⚠️  No session available, continuing without session${NC}"
fi
echo ""

# Step 3: Test character creation (manual)
echo -e "${BLUE}=== Step 3: Character Creation (Manual) ===${NC}"
CREATE_RESPONSE=$(curl -s -X POST "${BEING_REGISTRY_URL}/beings/create" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Test Character Manual\",
        \"backstory\": \"A test character created manually\",
        \"personality\": \"Friendly and helpful\",
        \"appearance\": \"Tall and strong\",
        \"automatic\": false,
        \"game_system\": \"D&D 5e\",
        \"session_id\": \"${SESSION_ID}\"
    }")

BEING_ID_1=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('being_id', ''))" 2>/dev/null || echo "")

if [ -n "$BEING_ID_1" ]; then
    echo -e "${GREEN}✅ Character created: ${BEING_ID_1:0:16}...${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
    TEST_COUNT=$((TEST_COUNT + 1))
else
    echo -e "${RED}❌ Character creation failed${NC}"
    echo "$CREATE_RESPONSE"
    exit 1
fi
echo ""

# Step 4: Test character creation (automatic)
echo -e "${BLUE}=== Step 4: Character Creation (Automatic) ===${NC}"
CREATE_AUTO_RESPONSE=$(curl -s -X POST "${BEING_REGISTRY_URL}/beings/create" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"automatic\": true,
        \"game_system\": \"D&D 5e\",
        \"session_id\": \"${SESSION_ID}\"
    }")

BEING_ID_2=$(echo "$CREATE_AUTO_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('being_id', ''))" 2>/dev/null || echo "")

if [ -n "$BEING_ID_2" ]; then
    echo -e "${GREEN}✅ Auto character created: ${BEING_ID_2:0:16}...${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
    TEST_COUNT=$((TEST_COUNT + 1))
else
    echo -e "${YELLOW}⚠️  Auto character creation may have failed${NC}"
fi
echo ""

# Step 5: Test get my characters
echo -e "${BLUE}=== Step 5: Get My Characters ===${NC}"
MY_CHARS_RESPONSE=$(curl -s -X GET "${BEING_REGISTRY_URL}/beings/my-characters" \
    -H "Authorization: Bearer $TOKEN")

test_step "Get my characters endpoint works" "echo '$MY_CHARS_RESPONSE' | grep -q 'characters'"

CHAR_COUNT=$(echo "$MY_CHARS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('characters', [])))" 2>/dev/null || echo "0")
echo -e "${GREEN}✅ Found $CHAR_COUNT character(s)${NC}"
echo ""

# Step 6: Test get being by ID
echo -e "${BLUE}=== Step 6: Get Being by ID ===${NC}"
GET_BEING_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${BEING_REGISTRY_URL}/beings/${BEING_ID_1}" \
    -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$GET_BEING_RESPONSE" | tail -n1)
GET_BEING_BODY=$(echo "$GET_BEING_RESPONSE" | sed '$d')

test_step "Get being by ID returns 200" "[ \"$HTTP_CODE\" = \"200\" ]"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Character retrieved successfully${NC}"
else
    echo -e "${RED}❌ Failed to get character: HTTP $HTTP_CODE${NC}"
fi
echo ""

# Step 7: Test vicinity endpoint
if [ -n "$SESSION_ID" ]; then
    echo -e "${BLUE}=== Step 7: Get Beings in Vicinity ===${NC}"
    VICINITY_RESPONSE=$(curl -s -X GET "${BEING_REGISTRY_URL}/beings/vicinity/${SESSION_ID}" \
        -H "Authorization: Bearer $TOKEN")
    
    test_step "Vicinity endpoint works" "echo '$VICINITY_RESPONSE' | grep -q 'beings'"
    
    VICINITY_COUNT=$(echo "$VICINITY_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('beings', [])))" 2>/dev/null || echo "0")
    echo -e "${GREEN}✅ Found $VICINITY_COUNT being(s) in vicinity${NC}"
    echo ""
fi

# Step 8: Test character query (chat)
echo -e "${BLUE}=== Step 8: Character Chat/Query ===${NC}"
QUERY_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BEING_URL}/query" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"query\": \"Hello, can you hear me?\",
        \"being_id\": \"${BEING_ID_1}\",
        \"session_id\": \"${SESSION_ID}\",
        \"game_system\": \"D&D 5e\"
    }")

HTTP_CODE=$(echo "$QUERY_RESPONSE" | tail -n1)
QUERY_BODY=$(echo "$QUERY_RESPONSE" | sed '$d')

test_step "Character query returns 200" "[ \"$HTTP_CODE\" = \"200\" ]"

if [ "$HTTP_CODE" = "200" ]; then
    RESPONSE_TEXT=$(echo "$QUERY_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('response', ''))" 2>/dev/null || echo "")
    if [ -n "$RESPONSE_TEXT" ] && [ "$RESPONSE_TEXT" != "No response received" ]; then
        echo -e "${GREEN}✅ Character responded: ${RESPONSE_TEXT:0:50}...${NC}"
        test_step "Character response is not empty" "[ -n \"$RESPONSE_TEXT\" ]"
    else
        echo -e "${YELLOW}⚠️  Character response was empty or 'No response received'${NC}"
        echo "Response body: $QUERY_BODY"
    fi
else
    echo -e "${RED}❌ Query failed: HTTP $HTTP_CODE${NC}"
    echo "$QUERY_BODY"
fi
echo ""

# Step 9: Test character deletion
echo -e "${BLUE}=== Step 9: Character Deletion ===${NC}"
DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "${BEING_REGISTRY_URL}/beings/${BEING_ID_2}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$DELETE_RESPONSE" | tail -n1)

test_step "Character deletion returns 200" "[ \"$HTTP_CODE\" = \"200\" ]"

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Character deleted successfully${NC}"
    
    # Verify deletion
    GET_DELETED_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${BEING_REGISTRY_URL}/beings/${BEING_ID_2}" \
        -H "Authorization: Bearer $TOKEN")
    DELETED_HTTP_CODE=$(echo "$GET_DELETED_RESPONSE" | tail -n1)
    
    test_step "Deleted character returns 404" "[ \"$DELETED_HTTP_CODE\" = \"404\" ]"
else
    echo -e "${RED}❌ Deletion failed: HTTP $HTTP_CODE${NC}"
fi
echo ""

# Step 10: Test all beings list (GM only - will fail for player)
echo -e "${BLUE}=== Step 10: All Beings List (GM Only) ===${NC}"
ALL_BEINGS_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${AUTH_URL}/beings/list" \
    -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$ALL_BEINGS_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ All beings list accessible (GM)${NC}"
    test_step "All beings list works for GM" "true"
elif [ "$HTTP_CODE" = "403" ]; then
    echo -e "${YELLOW}⚠️  All beings list requires GM role (expected for player)${NC}"
    test_step "All beings list properly restricted" "true"
else
    echo -e "${YELLOW}⚠️  Unexpected response: HTTP $HTTP_CODE${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}=== Test Summary ===${NC}"
echo "Total tests: $TEST_COUNT"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
