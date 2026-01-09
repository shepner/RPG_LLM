# Gaia Bot Setup and Testing

## Status

✅ **Gaia bot created** in Mattermost  
✅ **Service handler integrated** and working  
✅ **Worlds service connection** verified  
⚠️ **Mattermost webhook configuration** needed

## How to Use

### Option 1: @Mention in Any Channel (Recommended)

1. Go to any channel in Mattermost
2. Type: `@gaia What is your role?`
3. The bot will respond with information from the Worlds service

### Option 2: Direct Message

For DMs to work, you need to configure Mattermost to send webhook events.

## Configure Mattermost Outgoing Webhook

To enable @gaia mentions to work, configure an outgoing webhook in Mattermost:

### Via System Console (Recommended)

1. Log in to Mattermost as admin
2. Go to **System Console** → **Integrations** → **Outgoing Webhooks**
3. Click **Add Outgoing Webhook**
4. Configure:
   - **Title**: `Gaia Bot Webhook`
   - **Description**: `Webhook for Gaia bot interactions`
   - **Channel**: Select a channel (or leave blank for all channels)
   - **Trigger Words**: `@gaia`
   - **Callback URLs**: `http://mattermost_bot:8008/webhook`
   - **Content Type**: `application/json`
5. Click **Save**

### Via API (Automated)

You can use the provided script:

```bash
MATTERMOST_ADMIN_EMAIL=your_email@example.com \
MATTERMOST_ADMIN_PASSWORD=your_password \
./scripts/setup-gaia-webhook.sh
```

## Testing

After configuring the webhook:

1. Go to any Mattermost channel
2. Type: `@gaia What is your role?`
3. You should receive a response from the Worlds service

## Troubleshooting

### Bot Not Responding

1. **Check webhook is configured**:
   - System Console → Integrations → Outgoing Webhooks
   - Verify webhook exists and is enabled

2. **Check bot service logs**:
   ```bash
   docker-compose logs mattermost_bot | grep -i gaia
   ```

3. **Test webhook manually**:
   ```bash
   curl -X POST http://localhost:8008/webhook \
     -H "Content-Type: application/json" \
     -d '{
       "event": "posted",
       "data": {
         "post": {
           "id": "test",
           "channel_id": "test",
           "user_id": "test",
           "message": "@gaia What is your role?"
         }
       }
     }'
   ```

4. **Verify Worlds service is running**:
   ```bash
   curl http://localhost:8004/health
   ```

### "Invalid or expired session" Error

This is a warning about websocket connections, but doesn't affect webhook functionality. The bot can still receive and process webhook events.

### No Response from Gaia

1. Check that the webhook URL is correct: `http://mattermost_bot:8008/webhook`
2. Verify the trigger word is exactly `@gaia` (case-sensitive)
3. Check bot logs for errors: `docker-compose logs mattermost_bot --tail 50`

## What's Working

- ✅ Bot creation and registration
- ✅ Service handler routing
- ✅ Worlds service API connection
- ✅ Message parsing and @mention detection
- ✅ Response generation

## What Needs Configuration

- ⚠️ Mattermost outgoing webhook (for @mentions to trigger events)
- ⚠️ Mattermost webhook events for DMs (requires additional configuration)

## Next Steps

Once the webhook is configured, you can:
- Ask Gaia questions about world state
- Query world events
- Get information about the Worlds service
- Test LLM interactions through Mattermost
