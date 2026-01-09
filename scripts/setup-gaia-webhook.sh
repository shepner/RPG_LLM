#!/bin/bash
# Script to configure Mattermost outgoing webhook for Gaia bot

MATTERMOST_URL="${MATTERMOST_URL:-http://localhost:8065}"
ADMIN_EMAIL="${MATTERMOST_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${MATTERMOST_ADMIN_PASSWORD:-}"

if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    echo "Error: MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD must be set"
    echo "Usage: MATTERMOST_ADMIN_EMAIL=admin@example.com MATTERMOST_ADMIN_PASSWORD=password ./scripts/setup-gaia-webhook.sh"
    exit 1
fi

echo "Logging in to Mattermost..."
LOGIN_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/users/login" \
    -H "Content-Type: application/json" \
    -d "{\"login_id\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Error: Failed to login. Check your credentials."
    exit 1
fi

echo "Getting team ID..."
TEAM_RESPONSE=$(curl -s -X GET "${MATTERMOST_URL}/api/v4/teams" \
    -H "Authorization: Bearer ${TOKEN}")

TEAM_ID=$(echo "$TEAM_RESPONSE" | python3 -c "import sys, json; teams = json.load(sys.stdin); print(teams[0]['id'] if teams else '')" 2>/dev/null)

if [ -z "$TEAM_ID" ]; then
    echo "Error: Could not find team"
    exit 1
fi

echo "Creating outgoing webhook for Gaia bot..."
WEBHOOK_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/hooks/outgoing" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"team_id\": \"${TEAM_ID}\",
        \"display_name\": \"Gaia Bot Webhook\",
        \"description\": \"Webhook for Gaia bot interactions\",
        \"trigger_words\": [\"@gaia\"],
        \"trigger_when\": 1,
        \"callback_urls\": [\"http://mattermost_bot:8008/webhook\"],
        \"content_type\": \"application/json\"
    }")

WEBHOOK_ID=$(echo "$WEBHOOK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -n "$WEBHOOK_ID" ]; then
    echo "✅ Outgoing webhook created successfully!"
    echo "Webhook ID: $WEBHOOK_ID"
    echo ""
    echo "You can now mention @gaia in any channel to interact with the Worlds service."
else
    echo "⚠️  Webhook creation response: $WEBHOOK_RESPONSE"
    echo "The webhook may already exist or there was an error."
fi
