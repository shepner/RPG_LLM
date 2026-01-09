# Mattermost Integration Guide

## Overview

The RPG_LLM system uses Mattermost as the central interface for character conversations and system administration. Each character/being has its own DM channel, and game sessions use group channels for collaborative play.

## Architecture

- **Mattermost Server**: Self-hosted Mattermost Team Edition
- **Mattermost Bot Service**: Bridges Mattermost with RPG_LLM services
- **Character DMs**: Private channels for each character/being
- **Session Channels**: Group channels for game sessions

## Setup Instructions

### 1. Prerequisites

- Docker and Docker Compose installed
- Mattermost bot token (created after Mattermost setup)
- RPG_LLM services running

### 2. Environment Variables

Add the following to your `.env` file:

```bash
# Mattermost Configuration
MATTERMOST_URL=http://localhost:8065
MATTERMOST_BOT_TOKEN=your_bot_token_here
MATTERMOST_BOT_USERNAME=rpg-bot
MATTERMOST_DB_PASSWORD=your_secure_password
MATTERMOST_SITE_URL=http://localhost:8065
```

### 3. Start Services

```bash
docker-compose up -d mattermost_db mattermost mattermost_bot
```

Wait for services to initialize (about 30-60 seconds).

### 4. Configure Mattermost

1. **Access Mattermost**: Open http://localhost:8065 in your browser
2. **Create Admin Account**: First-time setup will prompt for admin account
3. **Create Bot User**:
   - Go to System Console → Integrations → Bot Accounts
   - Create a new bot account named `rpg-bot`
   - Copy the bot token
   - Update `MATTERMOST_BOT_TOKEN` in `.env` and restart `mattermost_bot` service

4. **Configure Webhook** (Optional, for advanced features):
   - Go to Integrations → Incoming Webhooks
   - Create webhook pointing to `http://mattermost_bot:8008/webhook`

### 5. Restart Bot Service

After setting the bot token:

```bash
docker-compose restart mattermost_bot
```

## Channel Structure

### Character DM Channels

- **Format**: `character-{being_id}` or character name
- **Type**: Direct Message (Group DM with bot)
- **Members**: Character owner, GM (if applicable), bot
- **Purpose**: Private conversations with individual characters

### Session Channels

- **Format**: `session-{session_id}` or session name
- **Type**: Private group channel
- **Members**: All players in session, GM, bot
- **Purpose**: Group conversations, being-to-being interactions via @mentions

## Using Mattermost

### Character Conversations

1. **Access Character DM**: Each character automatically gets a DM channel
2. **Send Messages**: Type messages directly in the character's DM
3. **Receive Responses**: Character responses appear in the same channel

### Being-to-Being Conversations

1. **In Session Channel**: Use @mentions to reference other characters
2. **Format**: `@character-name your message here`
3. **Response**: The mentioned character will respond in the channel

### Administrative Commands

All commands start with `/rpg-`:

- `/rpg-create-character [name]` - Create a new character
- `/rpg-list-characters` - List your characters
- `/rpg-delete-character <being_id>` - Delete a character
- `/rpg-create-session [name]` - Create a game session
- `/rpg-join-session <session_id>` - Join a session
- `/rpg-health` - Check service health status
- `/rpg-roll <dice>` - Roll dice (e.g., `/rpg-roll 1d20`)
- `/rpg-world-event <description>` - Record a world event
- `/rpg-system-status` - Get comprehensive system status (GM only)

## Authentication

The bot service bridges Mattermost user authentication with RPG_LLM authentication:

1. **User Mapping**: Mattermost users are mapped to RPG users by email/username
2. **JWT Tokens**: Bot service manages JWT tokens for API calls
3. **Role Management**: GM vs player roles are enforced based on RPG user roles

### Setting Up User Mapping

For production, you'll want to:
1. Sync Mattermost users with RPG_LLM users
2. Ensure email addresses match between systems
3. Or implement a mapping service

## Troubleshooting

### Bot Not Responding

1. **Check Bot Service Logs**:
   ```bash
   docker-compose logs mattermost_bot
   ```

2. **Verify Bot Token**: Ensure `MATTERMOST_BOT_TOKEN` is set correctly
3. **Check Mattermost Connection**: Verify bot can connect to Mattermost API

### Channels Not Created

1. **Check Bot Permissions**: Bot needs permission to create channels
2. **Verify Service Endpoints**: Ensure RPG services are accessible
3. **Check Logs**: Look for errors in bot service logs

### Authentication Errors

1. **Verify JWT Secret**: Ensure `JWT_SECRET_KEY` matches auth service
2. **Check User Mapping**: Verify Mattermost users can be mapped to RPG users
3. **Review Auth Service**: Ensure auth service is running and accessible

### Character Not Responding

1. **Check Being Service**: Verify being service is running
2. **Verify Character Exists**: Ensure character is registered
3. **Check Permissions**: Verify user has access to the character
4. **Review Logs**: Check being service logs for errors

## Advanced Configuration

### Custom Channel Names

You can customize channel naming in `services/mattermost_bot/src/config.py`:

```python
CHARACTER_DM_PREFIX: str = "character-"
SESSION_CHANNEL_PREFIX: str = "session-"
```

### Webhook Configuration

For real-time updates, configure Mattermost webhooks:

1. **Outgoing Webhook**: Send events from Mattermost to bot
2. **Incoming Webhook**: Send messages from bot to Mattermost (handled automatically)

### Integration with Character Creation

When characters are created via the web interface or API, the bot service automatically:
1. Creates a DM channel for the character
2. Adds the owner and GM to the channel
3. Sets up the channel for conversations

## Migration from Web Interface

If you have existing chat history in the web interface:

1. **Export localStorage Data**:
   - Open browser console on web interface
   - Run: `JSON.stringify(localStorage)`
   - Save to a JSON file

2. **Run Migration Script**:
   ```bash
   python scripts/migrate-chat-to-mattermost.py <local_storage.json>
   ```

3. **Follow Prompts**: Script will ask for Mattermost user IDs for each character owner

## Security Considerations

1. **Bot Token**: Keep `MATTERMOST_BOT_TOKEN` secure
2. **Database Password**: Use strong password for Mattermost database
3. **Network**: Consider using internal Docker network for service communication
4. **HTTPS**: For production, configure HTTPS for Mattermost

## Support

For issues or questions:
1. Check service logs: `docker-compose logs [service_name]`
2. Review this documentation
3. Check Mattermost system console for configuration issues
