#!/bin/bash
# Script to delete a team in Mattermost via API

MATTERMOST_URL="${MATTERMOST_URL:-http://localhost:8065}"
ADMIN_EMAIL="${MATTERMOST_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${MATTERMOST_ADMIN_PASSWORD:-}"
TEAM_NAME="${1:-rpg-llm}"

if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    echo "Error: MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD must be set"
    echo "Usage: MATTERMOST_ADMIN_EMAIL=admin@example.com MATTERMOST_ADMIN_PASSWORD=password ./scripts/delete-mattermost-team.sh [team_name]"
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

echo "Finding team '${TEAM_NAME}'..."
# Get all teams and find the one matching the name
TEAMS_RESPONSE=$(curl -s -X GET "${MATTERMOST_URL}/api/v4/teams" \
    -H "Authorization: Bearer ${TOKEN}")

TEAM_ID=$(echo "$TEAMS_RESPONSE" | python3 -c "
import sys, json
try:
    teams = json.load(sys.stdin)
    for team in teams:
        if team.get('name') == '${TEAM_NAME}':
            print(team.get('id', ''))
            break
except:
    pass
" 2>/dev/null)

if [ -z "$TEAM_ID" ]; then
    echo "Error: Team '${TEAM_NAME}' not found."
    echo "Available teams:"
    echo "$TEAMS_RESPONSE" | python3 -c "import sys, json; [print(f\"  - {t.get('name')} (ID: {t.get('id')})\") for t in json.load(sys.stdin)]" 2>/dev/null
    exit 1
fi

echo "Found team '${TEAM_NAME}' with ID: ${TEAM_ID}"
echo "Deleting team..."
DELETE_RESPONSE=$(curl -s -w "\n%{http_code}" -X DELETE "${MATTERMOST_URL}/api/v4/teams/${TEAM_ID}" \
    -H "Authorization: Bearer ${TOKEN}")

HTTP_CODE=$(echo "$DELETE_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$DELETE_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "✅ Team '${TEAM_NAME}' deleted successfully!"
else
    echo "Error: Failed to delete team."
    echo "HTTP Code: $HTTP_CODE"
    echo "Response: $RESPONSE_BODY"
    exit 1
fi
