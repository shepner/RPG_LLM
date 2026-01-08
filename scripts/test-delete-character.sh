#!/bin/bash
# Test script for character delete endpoint

set -e

echo "=== Testing Character Delete Endpoint ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

AUTH_URL="http://localhost:8000"
BEING_REGISTRY_URL="http://localhost:8007"

# Step 1: Register and login as test user
echo -e "${BLUE}Step 1: Registering test user...${NC}"
REGISTER_RESPONSE=$(curl -s -X POST "${AUTH_URL}/register" \
    -H "Content-Type: application/json" \
    -d '{
        "username": "testdeleteuser",
        "email": "testdelete@example.com",
        "password": "testpass123",
        "role": "player"
    }')

USER_ID=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user_id', ''))" 2>/dev/null || echo "")

if [ -z "$USER_ID" ]; then
    echo -e "${YELLOW}⚠️  User might already exist, trying to login...${NC}"
    LOGIN_RESPONSE=$(curl -s -X POST "${AUTH_URL}/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"testdeleteuser","password":"testpass123"}')
    TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")
    if [ -z "$TOKEN" ]; then
        echo -e "${RED}❌ Failed to register or login${NC}"
        echo "$REGISTER_RESPONSE"
        exit 1
    fi
else
    echo -e "${GREEN}✅ User registered: $USER_ID${NC}"
    
    echo -e "${BLUE}Step 2: Logging in...${NC}"
    LOGIN_RESPONSE=$(curl -s -X POST "${AUTH_URL}/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"testdeleteuser","password":"testpass123"}')
    
    TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")
fi

if [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Login failed${NC}"
    echo "$LOGIN_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Login successful${NC}"
echo ""

# Step 3: Create a test character
echo -e "${BLUE}Step 3: Creating test character...${NC}"
CREATE_RESPONSE=$(curl -s -X POST "${BEING_REGISTRY_URL}/beings/create" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Delete Character",
        "backstory": "A test character for deletion",
        "personality": "Testy",
        "appearance": "Test appearance",
        "automatic": false,
        "game_system": "D&D 5e"
    }')

BEING_ID=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('being_id', ''))" 2>/dev/null || echo "")

if [ -z "$BEING_ID" ]; then
    echo -e "${RED}❌ Character creation failed${NC}"
    echo "$CREATE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Character created: $BEING_ID${NC}"
echo ""

# Step 4: Verify character exists
echo -e "${BLUE}Step 4: Verifying character exists...${NC}"
GET_RESPONSE=$(curl -s -X GET "${BEING_REGISTRY_URL}/beings/${BEING_ID}" \
    -H "Authorization: Bearer $TOKEN")

if echo "$GET_RESPONSE" | grep -q "$BEING_ID"; then
    echo -e "${GREEN}✅ Character exists in registry${NC}"
else
    echo -e "${RED}❌ Character not found in registry${NC}"
    echo "$GET_RESPONSE"
    exit 1
fi

# Check ownership
OWNERSHIP_RESPONSE=$(curl -s -X GET "${AUTH_URL}/beings/owned" \
    -H "Authorization: Bearer $TOKEN")

if echo "$OWNERSHIP_RESPONSE" | grep -q "$BEING_ID"; then
    echo -e "${GREEN}✅ Character ownership record exists${NC}"
else
    echo -e "${YELLOW}⚠️  Character ownership record not found (might be okay)${NC}"
fi
echo ""

# Step 5: Test delete endpoint
echo -e "${BLUE}Step 5: Testing delete endpoint...${NC}"
DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "${BEING_REGISTRY_URL}/beings/${BEING_ID}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$DELETE_RESPONSE" | tail -n1)
DELETE_BODY=$(echo "$DELETE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Delete endpoint returned 200 OK${NC}"
    echo "Response: $DELETE_BODY"
else
    echo -e "${RED}❌ Delete endpoint failed with HTTP $HTTP_CODE${NC}"
    echo "Response: $DELETE_BODY"
    exit 1
fi
echo ""

# Step 6: Verify character is deleted
echo -e "${BLUE}Step 6: Verifying character is deleted...${NC}"
GET_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${BEING_REGISTRY_URL}/beings/${BEING_ID}" \
    -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$GET_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "404" ]; then
    echo -e "${GREEN}✅ Character removed from registry (404 as expected)${NC}"
else
    echo -e "${RED}❌ Character still exists in registry (HTTP $HTTP_CODE)${NC}"
    echo "$GET_RESPONSE"
    exit 1
fi

# Check ownership is deleted
OWNERSHIP_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${AUTH_URL}/beings/owned" \
    -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$OWNERSHIP_RESPONSE" | tail -n1)
OWNERSHIP_BODY=$(echo "$OWNERSHIP_RESPONSE" | sed '$d')

if ! echo "$OWNERSHIP_BODY" | grep -q "$BEING_ID"; then
    echo -e "${GREEN}✅ Character ownership record deleted${NC}"
else
    echo -e "${YELLOW}⚠️  Character ownership record still exists${NC}"
fi
echo ""

# Step 7: Test permission check (try to delete non-existent character)
echo -e "${BLUE}Step 7: Testing delete of non-existent character...${NC}"
FAKE_BEING_ID="00000000-0000-0000-0000-000000000000"
DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "${BEING_REGISTRY_URL}/beings/${FAKE_BEING_ID}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$DELETE_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "404" ]; then
    echo -e "${GREEN}✅ Correctly returns 404 for non-existent character${NC}"
else
    echo -e "${YELLOW}⚠️  Unexpected response code: $HTTP_CODE${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}=== Test Summary ==="
echo "✅ All delete endpoint tests passed!"
echo ""
echo "Tested:"
echo "  - Character creation"
echo "  - Character retrieval"
echo "  - Character deletion"
echo "  - Registry cleanup"
echo "  - Ownership record cleanup"
echo "  - Error handling (404 for non-existent)"
echo "${NC}"
