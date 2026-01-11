#!/bin/bash
# Automatically configure Mattermost outgoing webhooks for service bots

MATTERMOST_URL="${MATTERMOST_URL:-http://localhost:8065}"
BOT_TOKEN="${MATTERMOST_BOT_TOKEN:-}"
ADMIN_EMAIL="${MATTERMOST_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${MATTERMOST_ADMIN_PASSWORD:-}"
WEBHOOK_URL="${MATTERMOST_WEBHOOK_URL:-http://mattermost_bot:8008/webhook}"

echo "============================================================"
echo "Mattermost Webhook Auto-Configuration"
echo "============================================================"
echo ""

# Function to get auth token (outputs token to stdout, messages to stderr)
get_auth_token() {
    # Try bot token first
    if [ -n "$BOT_TOKEN" ]; then
        echo "Trying bot token authentication..." >&2
        USER_RESPONSE=$(curl -s -X GET "${MATTERMOST_URL}/api/v4/users/me" \
            -H "Authorization: Bearer ${BOT_TOKEN}" \
            -k)
        
        if echo "$USER_RESPONSE" | grep -q '"id"'; then
            echo "✅ Bot token authentication successful" >&2
            echo "$BOT_TOKEN"
            return 0
        fi
    fi
    
    # Fall back to admin login
    if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
        echo "Trying admin login authentication..." >&2
        LOGIN_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/users/login" \
            -H "Content-Type: application/json" \
            -d "{\"login_id\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
            -k)
        
        TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)
        
        if [ -n "$TOKEN" ]; then
            echo "✅ Admin login authentication successful" >&2
            echo "$TOKEN"
            return 0
        fi
    fi
    
    echo "❌ Error: Could not authenticate." >&2
    echo "   Please set one of:" >&2
    echo "   - MATTERMOST_BOT_TOKEN (with admin permissions)" >&2
    echo "   - MATTERMOST_ADMIN_EMAIL and MATTERMOST_ADMIN_PASSWORD" >&2
    return 1
}

# Get authentication token
TOKEN=$(get_auth_token)
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ] || [ -z "$TOKEN" ]; then
    if [ -z "$TOKEN" ]; then
        echo "❌ Error: Could not authenticate or get token"
    fi
    exit 1
fi

echo ""
echo "Getting team ID..."
TEAM_RESPONSE=$(curl -s -X GET "${MATTERMOST_URL}/api/v4/teams" \
    -H "Authorization: Bearer ${TOKEN}" \
    -k)

# Get first active (non-deleted) team
TEAM_ID=$(echo "$TEAM_RESPONSE" | python3 -c "
import sys, json
try:
    teams = json.loads(sys.stdin.read())
    for team in teams:
        if isinstance(team, dict) and team.get('delete_at', 1) == 0:
            print(team['id'])
            break
except Exception:
    pass
" 2>/dev/null)

if [ -z "$TEAM_ID" ]; then
    echo "❌ Error: Could not get team ID"
    exit 1
fi

echo "✅ Found team ID: $TEAM_ID"
echo ""

# Function to check if webhook exists
check_webhook_exists() {
    local trigger=$1
    WEBHOOKS_RESPONSE=$(curl -s -X GET "${MATTERMOST_URL}/api/v4/hooks/outgoing" \
        -H "Authorization: Bearer ${TOKEN}" \
        -G -d "team_id=${TEAM_ID}" -d "page=0" -d "per_page=100" \
        -k)
    
    echo "$WEBHOOKS_RESPONSE" | python3 -c "
import sys, json
try:
    webhooks = json.load(sys.stdin)
    for webhook in webhooks:
        if '$trigger' in webhook.get('trigger_words', []):
            print(webhook.get('id', ''))
            break
except:
    pass
" 2>/dev/null
}

# Function to create webhook
create_webhook() {
    local username=$1
    local trigger=$2
    local display_name=$3
    
    echo "Setting up webhook for ${username}..."
    
    # Check if webhook already exists
    EXISTING_ID=$(check_webhook_exists "$trigger")
    if [ -n "$EXISTING_ID" ]; then
        echo "⚠️  Webhook for ${trigger} already exists (ID: ${EXISTING_ID})"
        return 0
    fi
    
    WEBHOOK_RESPONSE=$(curl -s -X POST "${MATTERMOST_URL}/api/v4/hooks/outgoing" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"team_id\": \"${TEAM_ID}\",
            \"display_name\": \"${display_name}\",
            \"description\": \"Webhook for ${username} bot interactions\",
            \"trigger_words\": [\"${trigger}\"],
            \"trigger_when\": 1,
            \"callback_urls\": [\"${WEBHOOK_URL}\"],
            \"content_type\": \"application/json\"
        }" \
        -k)
    
    WEBHOOK_ID=$(echo "$WEBHOOK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
    
    if [ -n "$WEBHOOK_ID" ]; then
        echo "✅ Created webhook for ${trigger} (ID: ${WEBHOOK_ID})"
        return 0
    else
        echo "❌ Failed to create webhook for ${trigger}"
        echo "   Response: ${WEBHOOK_RESPONSE:0:200}"
        return 1
    fi
}

# Create webhooks for each service bot
echo "Creating webhooks..."
SUCCESS_COUNT=0

create_webhook "gaia" "@gaia" "Gaia Bot Webhook" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
echo ""
create_webhook "thoth" "@thoth" "Thoth Bot Webhook" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
echo ""
create_webhook "maat" "@maat" "Ma'at Bot Webhook" && SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
echo ""

echo "============================================================"
if [ $SUCCESS_COUNT -eq 3 ]; then
    echo "✅ All webhooks configured successfully!"
else
    echo "⚠️  Configured ${SUCCESS_COUNT}/3 webhooks"
fi
echo ""
echo "You can now mention @gaia, @thoth, or @maat in any channel."
echo "============================================================"
