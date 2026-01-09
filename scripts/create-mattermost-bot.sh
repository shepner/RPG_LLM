#!/bin/bash
# Script to create a bot account in Mattermost via API

MATTERMOST_URL="${MATTERMOST_URL:-http://localhost:8065}"
ADMIN_EMAIL="${MATTERMOST_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${MATTERMOST_ADMIN_PASSWORD:-}"
BOT_USERNAME="${1:-test}"
BOT_DISPLAY_NAME="${2:-Test Bot}"
BOT_DESCRIPTION="${3:-Test bot for RPG_LLM}"

if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    echo "Error: MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD must be set"
    echo "Usage: MATTERMOST_ADMIN_EMAIL=admin@example.com MATTERMOST_ADMIN_PASSWORD=password ./scripts/create-mattermost-bot.sh [username] [display_name] [description]"
    echo ""
    echo "Example:"
    echo "  MATTERMOST_ADMIN_EMAIL=admin@example.com MATTERMOST_ADMIN_PASSWORD=password ./scripts/create-mattermost-bot.sh test 'Test Bot' 'Test bot for RPG_LLM'"
    exit 1
fi

echo "Logging in to Mattermost as admin..."
LOGIN_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/users/login" \
    -H "Content-Type: application/json" \
    -d "{\"login_id\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Error: Failed to login. Check your credentials."
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "Creating bot account '${BOT_USERNAME}'..."
BOT_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/bots" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"username\": \"${BOT_USERNAME}\",
        \"display_name\": \"${BOT_DISPLAY_NAME}\",
        \"description\": \"${BOT_DESCRIPTION}\"
    }")

BOT_ID=$(echo "$BOT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user_id', ''))" 2>/dev/null)
BOT_TOKEN=$(echo "$BOT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)

if [ -z "$BOT_ID" ]; then
    echo "Error: Failed to create bot account."
    echo "Response: $BOT_RESPONSE"
    
    # Check if bot already exists
    if echo "$BOT_RESPONSE" | grep -q "already exists\|already taken"; then
        echo ""
        echo "Bot '${BOT_USERNAME}' may already exist. Trying to get existing bot..."
        EXISTING_BOT=$(curl -s -X GET "${MATTERMOST_URL}/api/v4/bots?username=${BOT_USERNAME}" \
            -H "Authorization: Bearer ${TOKEN}")
        
        EXISTING_BOT_ID=$(echo "$EXISTING_BOT" | python3 -c "import sys, json; bots = json.load(sys.stdin); print(bots[0]['user_id'] if bots else '')" 2>/dev/null)
        
        if [ -n "$EXISTING_BOT_ID" ]; then
            echo "Found existing bot with ID: $EXISTING_BOT_ID"
            echo "To get the token, you'll need to regenerate it via the Mattermost UI:"
            echo "  System Console → Integrations → Bot Accounts → ${BOT_USERNAME} → Regenerate Token"
        fi
    fi
    exit 1
fi

echo ""
echo "✅ Bot created successfully!"
echo "Bot Username: ${BOT_USERNAME}"
echo "Bot ID: ${BOT_ID}"
echo "Bot Display Name: ${BOT_DISPLAY_NAME}"
echo ""
if [ -n "$BOT_TOKEN" ]; then
    echo "⚠️  IMPORTANT: Save this token - it won't be shown again!"
    echo "Bot Token: ${BOT_TOKEN}"
    echo ""
    echo "To use this bot, add to your .env file:"
    echo "MATTERMOST_BOT_TOKEN=${BOT_TOKEN}"
else
    echo "⚠️  Token not returned. You may need to regenerate it via the Mattermost UI:"
    echo "  System Console → Integrations → Bot Accounts → ${BOT_USERNAME} → Regenerate Token"
fi
echo ""
echo "You can now use this bot in Mattermost!"
