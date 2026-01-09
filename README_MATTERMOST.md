# Mattermost Integration - Quick Start

The RPG_LLM system now uses Mattermost as the central interface for character conversations and system administration.

## What's New

- **Character Conversations**: Each character has its own DM channel in Mattermost
- **Session Channels**: Game sessions use group channels for collaborative play
- **Administrative Commands**: Full system administration via slash commands
- **Unified Interface**: All interactions happen in Mattermost

## Quick Setup

### 1. Add Environment Variables

Add to your `.env` file:
```bash
MATTERMOST_BOT_TOKEN=  # Set after creating bot in Mattermost
MATTERMOST_DB_PASSWORD=your_secure_password
MATTERMOST_SITE_URL=http://localhost:8065
```

### 2. Start Services

```bash
docker-compose up -d mattermost_db mattermost mattermost_bot
```

### 3. Configure Mattermost

1. Open http://localhost:8065
2. Create admin account (first time only)
3. Create bot account: System Console → Integrations → Bot Accounts
4. Copy bot token and add to `.env`
5. Restart bot: `docker-compose restart mattermost_bot`

### 4. Test

Run the test script:
```bash
./scripts/test-mattermost-integration.sh
```

## Available Commands

All commands start with `/rpg-`:

- `/rpg-create-character [name]` - Create new character
- `/rpg-list-characters` - List your characters
- `/rpg-delete-character <id>` - Delete character
- `/rpg-create-session [name]` - Create game session
- `/rpg-join-session <id>` - Join session
- `/rpg-health` - Check service health
- `/rpg-roll <dice>` - Roll dice (e.g., `/rpg-roll 1d20`)
- `/rpg-world-event <description>` - Record world event
- `/rpg-system-status` - Get system status (GM only)

## Documentation

- **Setup Guide**: `docs/MATTERMOST_SETUP_STEPS.md`
- **Full Documentation**: `docs/MATTERMOST_INTEGRATION.md`

## Migration

If you have existing chat history, see the migration script:
```bash
python scripts/migrate-chat-to-mattermost.py <local_storage.json>
```

## Troubleshooting

Check service logs:
```bash
docker-compose logs mattermost_bot
docker-compose logs mattermost
```

See `docs/MATTERMOST_INTEGRATION.md` for detailed troubleshooting.
