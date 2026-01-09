# Gaia Bot Troubleshooting

## Current Status

✅ **Bot created** and registered  
✅ **Service handler** working  
✅ **Webhook endpoint** responding  
⚠️ **Bot token** may need regeneration  
⚠️ **Gemini API key** needs to be fixed  

## Issues Found

### 1. Bot Token Invalid/Expired

**Symptom**: Logs show "Invalid or expired session, please login again"

**Fix**:
1. Go to Mattermost: http://localhost:8065
2. System Console → Integrations → Bot Accounts
3. Find `rpg-bot`
4. Click "Regenerate Token"
5. Copy the new token
6. Update `.env` file: `MATTERMOST_BOT_TOKEN=<new_token>`
7. Restart: `docker-compose restart mattermost_bot`

### 2. Gemini API Key Error

**Symptom**: Response shows "403 Your API key was reported as leaked"

**Fix**:
1. Get a new Gemini API key from Google AI Studio
2. Update `.env` file: `GEMINI_API_KEY=<new_key>`
3. Restart Worlds service: `docker-compose restart worlds`

### 3. Mattermost Webhook Not Configured

**Symptom**: @gaia mentions don't trigger webhook events

**Fix**:
1. System Console → Integrations → Outgoing Webhooks
2. Add webhook:
   - **Trigger Words**: `@gaia`
   - **Callback URLs**: `http://mattermost_bot:8008/webhook`
   - **Content Type**: `application/json`

Or use the script:
```bash
MATTERMOST_ADMIN_EMAIL=your_email@example.com \
MATTERMOST_ADMIN_PASSWORD=your_password \
./scripts/setup-gaia-webhook.sh
```

## Testing

After fixing the issues:

1. **Test webhook manually**:
```bash
curl -X POST http://localhost:8008/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "posted",
    "data": {
      "post": {
        "id": "test",
        "channel_id": "test_channel",
        "user_id": "test_user",
        "message": "@gaia What is your role?"
      }
    }
  }'
```

2. **Check logs**:
```bash
docker-compose logs mattermost_bot --tail 20 | grep -i gaia
```

3. **Test in Mattermost**:
   - Go to any channel
   - Type: `@gaia What is your role?`
   - Should receive a response

## What's Working

- ✅ Bot creation and registration
- ✅ Service handler routing
- ✅ Error message extraction
- ✅ Webhook endpoint receiving events
- ✅ Worlds service API connection

## What Needs Fixing

- ⚠️ Bot token (regenerate in Mattermost)
- ⚠️ Gemini API key (get new key from Google)
- ⚠️ Mattermost webhook configuration (for @mentions)
