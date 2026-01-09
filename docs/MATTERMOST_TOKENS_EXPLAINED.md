# Mattermost Tokens Explained

## Two Different Tokens

There are **two different tokens** used in the Mattermost integration:

### 1. MATTERMOST_BOT_TOKEN

**Purpose**: Allows the bot to authenticate with Mattermost's API

**Used for**:
- Posting messages
- Creating channels
- Reading user information
- All bot API operations

**Location**: Set in `.env` file as `MATTERMOST_BOT_TOKEN`

**How to get it**:
1. System Console → Integrations → Bot Accounts
2. Find or create the `rpg-bot` account
3. Copy the **Access Token**

### 2. MATTERMOST_SLASH_COMMAND_TOKEN

**Purpose**: Verifies that slash command requests come from Mattermost

**Used for**:
- Validating incoming slash command requests
- Security - prevents unauthorized requests

**Location**: Set in `.env` file as `MATTERMOST_SLASH_COMMAND_TOKEN`

**How to get it**:
1. Main Menu → Integrations → Slash Commands
2. Create or edit the `/rpg` command
3. Copy the **Token** shown after saving

## Configuration

Add both tokens to your `.env` file:

```bash
# Bot authentication token
MATTERMOST_BOT_TOKEN=wmqi33yq6ff8ik1ibnhigu1mtc

# Slash command validation token
MATTERMOST_SLASH_COMMAND_TOKEN=your_slash_command_token_here
```

## Security

- **Bot Token**: Required for bot functionality
- **Slash Command Token**: Optional but recommended for security
  - If not set, slash commands will work but won't validate the token
  - If set, requests with invalid tokens will be rejected

## After Adding Token

Restart the bot service:
```bash
docker-compose restart mattermost_bot
```

## Troubleshooting

### "Invalid token" error

If you get "Invalid token" errors:
1. Check that `MATTERMOST_SLASH_COMMAND_TOKEN` matches the token from Mattermost
2. Make sure there are no extra spaces or quotes in `.env`
3. Restart the bot service after updating `.env`

### Slash commands not working

1. Verify `MATTERMOST_BOT_TOKEN` is set correctly
2. Check bot logs: `docker-compose logs mattermost_bot`
3. Test bot health: `curl http://localhost:8008/health`
