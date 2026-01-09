# Mattermost Integration - Testing Guide

Follow these steps to test the Mattermost integration.

## Step 1: Add Environment Variables

Add these to your `.env` file (create it if it doesn't exist):

```bash
# Mattermost Configuration
MATTERMOST_URL=http://localhost:8065
MATTERMOST_BOT_USERNAME=rpg-bot
MATTERMOST_DB_PASSWORD=change_me_secure_password
MATTERMOST_SITE_URL=http://localhost:8065

# Bot token will be added after Step 4
MATTERMOST_BOT_TOKEN=
```

## Step 2: Start Mattermost Services

```bash
docker-compose up -d mattermost_db mattermost
```

Wait 30-60 seconds for Mattermost to initialize.

## Step 3: Access Mattermost and Create Admin Account

1. Open your browser and go to: **http://localhost:8065**

2. You'll see the Mattermost setup page. Create your admin account:
   - Enter your email
   - Create a username
   - Set a password
   - Complete the setup

3. You'll be logged into Mattermost

## Step 4: Create the Bot Account

1. In Mattermost, click the **hamburger menu** (☰) in the top left
2. Select **System Console**
3. In the left sidebar, go to **Integrations** → **Bot Accounts**
4. Click **Add Bot Account** button
5. Fill in:
   - **Username**: `rpg-bot`
   - **Display Name**: `RPG Bot`
   - **Description**: `RPG_LLM System Bot`
6. Click **Save**
7. **IMPORTANT**: Copy the **Access Token** that appears (you'll need this!)

## Step 5: Configure Bot Token

1. Edit your `.env` file and add the bot token:
   ```bash
   MATTERMOST_BOT_TOKEN=paste_your_token_here
   ```

2. Start the bot service:
   ```bash
   docker-compose up -d mattermost_bot
   ```

3. Check that the bot started successfully:
   ```bash
   docker-compose logs mattermost_bot | tail -20
   ```
   
   You should see "Mattermost bot initialized" (or a warning if token isn't set yet)

## Step 6: Verify Services Are Running

Run the test script:
```bash
./scripts/test-mattermost-integration.sh
```

This will check:
- Docker is running
- Services are up
- Bot service is responding
- Mattermost server is accessible

## Step 7: Test Basic Functionality

### Test 1: Health Check Command

1. In Mattermost, go to any channel
2. Type: `/rpg-health`
3. You should see a response with service health status

**Note**: If slash commands don't work, you may need to configure them (see Step 8)

### Test 2: Create a Character

1. In Mattermost, type: `/rpg-create-character TestCharacter`
2. The bot should create a character and respond
3. Check if a DM channel was created for the character

### Test 3: List Characters

1. Type: `/rpg-list-characters`
2. You should see your characters listed

## Step 8: Configure Slash Commands (Optional but Recommended)

For slash commands to work properly:

1. In Mattermost System Console, go to **Integrations** → **Slash Commands**
2. Click **Add Slash Command**
3. Configure:
   - **Title**: `RPG Command`
   - **Command Trigger Word**: `rpg`
   - **Request URL**: `http://mattermost_bot:8008/webhook`
   - **Request Method**: `POST`
   - **Response Username**: `rpg-bot`
   - **Response Icon**: (optional)
4. Click **Save**

Now `/rpg-*` commands should work!

## Step 9: Test Character Conversations

1. Create a character if you haven't: `/rpg-create-character MyCharacter`
2. Look for a new DM channel with the character name
3. Open that DM channel
4. Send a message like "Hello, who are you?"
5. The character should respond!

## Step 10: Test Session Channels

1. Create a session: `/rpg-create-session TestSession`
2. Check if a new channel was created for the session
3. You can use @mentions in session channels for being-to-being conversations

## Troubleshooting

### Bot Not Responding

```bash
# Check bot logs
docker-compose logs mattermost_bot

# Restart bot
docker-compose restart mattermost_bot
```

### Mattermost Not Starting

```bash
# Check Mattermost logs
docker-compose logs mattermost

# Check database
docker-compose logs mattermost_db
```

### Commands Not Working

- Make sure you configured the slash command (Step 8)
- Or try sending messages directly to the bot in a DM
- Check bot logs for errors

### Channels Not Created

- Check being_registry logs: `docker-compose logs being_registry | grep -i mattermost`
- Verify bot service is accessible from other services
- Check that character/session creation succeeded

## Quick Test Checklist

- [ ] Mattermost accessible at http://localhost:8065
- [ ] Admin account created
- [ ] Bot account created and token copied
- [ ] Bot token added to .env
- [ ] Bot service started and running
- [ ] `/rpg-health` command works
- [ ] Character can be created
- [ ] Character DM channel exists
- [ ] Can send messages to character
- [ ] Character responds

## Need Help?

- Check `docs/MATTERMOST_INTEGRATION.md` for detailed documentation
- Check `docs/MATTERMOST_SETUP_STEPS.md` for setup details
- Review service logs for errors
- Ensure all environment variables are set correctly
