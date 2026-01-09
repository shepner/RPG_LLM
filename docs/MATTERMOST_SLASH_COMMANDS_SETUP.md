# Setting Up Mattermost Slash Commands

## Overview

The bot supports slash commands like `/rpg-health`, `/rpg-create-character`, etc. To use these, you need to configure slash commands in Mattermost.

## Setup Steps

### 1. Go to System Console

1. In Mattermost, click the ☰ menu (top left)
2. Select **System Console**
3. Navigate to: **Integrations** → **Slash Commands**

### 2. Create Slash Command

1. Click **Add Slash Command**
2. Fill in the form:
   - **Title**: `RPG Commands`
   - **Command Trigger Word**: `rpg`
   - **Request URL**: `http://mattermost_bot:8008/webhook`
     - Note: If Mattermost can't reach `mattermost_bot` hostname, use the external URL:
       - For local testing: `http://localhost:8008/webhook`
       - For Docker network: `http://mattermost_bot:8008/webhook`
   - **Request Method**: `POST`
   - **Response Username**: `rpg-bot`
   - **Response Icon**: (optional) Upload bot icon
   - **Description**: `RPG LLM system commands`
   - **Autocomplete**: Enable
   - **Autocomplete Description**: `RPG LLM commands`
   - **Autocomplete Hint**: `[command] [args]`

3. Click **Save**

### 3. Test

In any Mattermost channel, type:
- `/rpg-health` - Should return service status
- `/rpg-create-character TestChar` - Create a character
- `/rpg-list-characters` - List your characters

## Available Commands

- `/rpg-health` - Check service health
- `/rpg-create-character [name]` - Create a new character
- `/rpg-list-characters` - List your characters
- `/rpg-delete-character <id>` - Delete a character
- `/rpg-create-session [name]` - Create a game session
- `/rpg-join-session <id>` - Join a session
- `/rpg-roll <dice>` - Roll dice (e.g., `/rpg-roll 1d20`)
- `/rpg-world-event <description>` - Record world event
- `/rpg-system-status` - Get system status (GM only)

## Troubleshooting

### Command Not Working

1. **Check Request URL**:
   - If using Docker: `http://mattermost_bot:8008/webhook`
   - If Mattermost can't resolve hostname: Use `http://localhost:8008/webhook` or the container IP

2. **Check Bot Service**:
   ```bash
   docker-compose logs mattermost_bot | tail -20
   curl http://localhost:8008/health
   ```

3. **Check Mattermost Logs**:
   ```bash
   docker-compose logs mattermost | grep -i "slash\|command\|webhook"
   ```

### Network Issues

If Mattermost can't reach `mattermost_bot:8008`, you may need to:
- Use the external URL: `http://localhost:8008/webhook`
- Or configure Mattermost to use the Docker network IP

## Alternative: Character Conversations

Even without slash commands configured, the bot will work for:
- **Character DM channels**: Send messages directly to characters
- **Session channels**: Group conversations in game sessions

These work via webhook events, not slash commands.
