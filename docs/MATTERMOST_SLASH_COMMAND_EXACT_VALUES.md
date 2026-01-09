# Exact Values for Mattermost Slash Command

## Form Fields - Fill These In

### 1. Title
```
RPG Commands
```

### 2. Description
```
RPG LLM system commands for character and game management
```

### 3. Command Trigger Word
```
rpg
```
**Important**: Just type `rpg` - no slash, no dashes, no spaces. This means users will type `/rpg-health`, `/rpg-create-character`, etc.

### 4. Request URL
```
http://mattermost_bot:8008/webhook
```

**If that doesn't work** (Mattermost can't resolve the hostname), try:
```
http://localhost:8008/webhook
```

**Note**: The URL must be accessible from the Mattermost server. If you're running both in Docker, `mattermost_bot` should work. If not, use `localhost`.

### 5. Request Method
```
POST
```
(Already selected - keep it as POST)

### 6. Response Username
```
rpg-bot
```
This makes responses appear as coming from the bot account.

### 7. Response Icon
```
(Leave blank)
```
Optional - you can add an icon URL later if you want.

### 8. Autocomplete
```
☑ Check this box
```
Enable autocomplete so users can see `/rpg-` commands when typing.

## After Saving

1. Click **Save** button
2. Mattermost will generate a **Token** - you can ignore this (we're using bot token instead)
3. Test by typing `/rpg-health` in any channel

## Testing

After saving, try these commands in any Mattermost channel:
- `/rpg-health` - Check service status
- `/rpg-create-character TestChar` - Create a character
- `/rpg-list-characters` - List your characters

## Troubleshooting

### "Cannot reach URL" Error

If you get an error that Mattermost can't reach the URL:

1. **Check if bot service is running**:
   ```bash
   docker-compose ps mattermost_bot
   ```

2. **Try localhost instead**:
   Change Request URL to: `http://localhost:8008/webhook`

3. **Check network**:
   ```bash
   docker-compose exec mattermost curl http://mattermost_bot:8008/health
   ```

### Command Not Responding

1. **Check bot logs**:
   ```bash
   docker-compose logs mattermost_bot | tail -20
   ```

2. **Verify webhook endpoint**:
   ```bash
   curl -X POST http://localhost:8008/webhook -H "Content-Type: application/json" -d '{"command":"/rpg-health","text":"","user_id":"test"}'
   ```

3. **Check Mattermost logs**:
   ```bash
   docker-compose logs mattermost | grep -i "slash\|command\|webhook"
   ```
