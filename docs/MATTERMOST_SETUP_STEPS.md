# Mattermost Setup Steps

## Quick Setup Guide

Follow these steps to get Mattermost integration working:

### Step 1: Add Environment Variables

Add these to your `.env` file:

```bash
# Mattermost Configuration
MATTERMOST_URL=http://localhost:8065
MATTERMOST_BOT_TOKEN=  # Will be set after Step 3
MATTERMOST_BOT_USERNAME=rpg-bot
MATTERMOST_DB_PASSWORD=your_secure_password_here
MATTERMOST_SITE_URL=http://localhost:8065
```

### Step 2: Start Mattermost Services

```bash
docker-compose up -d mattermost_db mattermost
```

Wait 30-60 seconds for Mattermost to initialize.

### Step 3: Create Mattermost Admin Account

1. Open http://localhost:8065 in your browser
2. Complete the first-time setup:
   - Create admin account
   - Set team name
   - Complete initial configuration

### Step 4: Create Bot Account

1. In Mattermost, go to **System Console** (hamburger menu → System Console)
2. Navigate to **Integrations** → **Bot Accounts**
3. Click **Add Bot Account**
4. Fill in:
   - **Username**: `rpg-bot`
   - **Display Name**: `RPG Bot`
   - **Description**: `RPG_LLM System Bot`
5. Click **Save**
6. **Copy the Access Token** (you'll need this)

### Step 5: Configure Bot Token

1. Add the bot token to your `.env` file:
   ```bash
   MATTERMOST_BOT_TOKEN=your_copied_token_here
   ```

2. Start the bot service:
   ```bash
   docker-compose up -d mattermost_bot
   ```

### Step 6: Verify Setup

Run the test script:
```bash
./scripts/test-mattermost-integration.sh
```

### Step 7: Configure Slash Commands (Optional)

1. In Mattermost System Console, go to **Integrations** → **Slash Commands**
2. Click **Add Slash Command**
3. Configure:
   - **Title**: `RPG Command`
   - **Command Trigger Word**: `rpg`
   - **Request URL**: `http://mattermost_bot:8008/webhook`
   - **Request Method**: `POST`
   - **Response Username**: `rpg-bot`
4. Save

### Step 8: Test

1. In Mattermost, try a command: `/rpg-health`
2. Create a character via web interface or `/rpg-create-character`
3. Check that a DM channel was created for the character

## Troubleshooting

### Bot Not Responding

1. Check bot logs:
   ```bash
   docker-compose logs mattermost_bot
   ```

2. Verify token is correct:
   ```bash
   grep MATTERMOST_BOT_TOKEN .env
   ```

3. Restart bot:
   ```bash
   docker-compose restart mattermost_bot
   ```

### Mattermost Not Starting

1. Check database:
   ```bash
   docker-compose logs mattermost_db
   ```

2. Check Mattermost logs:
   ```bash
   docker-compose logs mattermost
   ```

3. Verify environment variables are set correctly

### Channels Not Created

1. Check bot has permissions (should be automatic)
2. Verify being_registry service can reach mattermost_bot
3. Check logs for errors:
   ```bash
   docker-compose logs being_registry | grep -i mattermost
   ```

## Next Steps

Once setup is complete:
- Create characters and verify DM channels are created
- Create sessions and verify group channels are created
- Test character conversations
- Test administrative commands

See `docs/MATTERMOST_INTEGRATION.md` for full documentation.
