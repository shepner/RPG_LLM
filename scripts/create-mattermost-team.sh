#!/bin/bash
# Script to create a default team in Mattermost via API

MATTERMOST_URL="${MATTERMOST_URL:-http://localhost:8065}"
ADMIN_EMAIL="${MATTERMOST_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${MATTERMOST_ADMIN_PASSWORD:-}"

if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    echo "Error: MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD must be set"
    echo "Usage: MATTERMOST_ADMIN_EMAIL=admin@example.com MATTERMOST_ADMIN_PASSWORD=password ./scripts/create-mattermost-team.sh"
    exit 1
fi

echo "Logging in to Mattermost..."
LOGIN_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/users/login" \
    -H "Content-Type: application/json" \
    -d "{\"login_id\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Error: Failed to login. Check your credentials."
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "Creating default team..."
TEAM_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/teams" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "rpg-llm",
        "display_name": "RPG LLM",
        "type": "O",
        "description": "RPG LLM Game Server"
    }')

TEAM_ID=$(echo "$TEAM_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$TEAM_ID" ]; then
    echo "Error: Failed to create team."
    echo "Response: $TEAM_RESPONSE"
    exit 1
fi

echo "✅ Team created successfully!"
echo "Team ID: $TEAM_ID"
echo "Team Name: rpg-llm"
echo ""
echo "You can now access Mattermost at: ${MATTERMOST_URL}"
