# Mattermost Bot Management

This system supports managing an indefinite number of Mattermost bot accounts without modifying the main `.env` file.

## Overview

Bot tokens are stored in a separate registry file (`RPG_LLM_DATA/bots/registry.json`) instead of the main `.env` file. This allows you to:

- Create unlimited bot accounts
- Manage bots without risking the main configuration
- Keep the primary `rpg-bot` token in `.env` for backward compatibility
- Automatically load bots from the registry

## Quick Start

### Create a New Bot

The easiest way to create a new bot is using the management script:

```bash
python3 scripts/manage-bots.py create <username> [display_name] [description]
```

Example:
```bash
python3 scripts/manage-bots.py create test-bot "Test Bot" "A test bot for development"
```

This will:
1. Create the bot in Mattermost
2. Generate a bot token
3. Add it to the bot registry automatically

### List All Bots

```bash
python3 scripts/manage-bots.py list
```

### Add an Existing Bot to Registry

If you have a bot token from Mattermost UI:

```bash
python3 scripts/manage-bots.py add <username> <token> [display_name] [description]
```

Example:
```bash
python3 scripts/manage-bots.py add my-bot abc123token "My Bot" "Description"
```

### Remove a Bot from Registry

```bash
python3 scripts/manage-bots.py remove <username>
```

Note: This only removes it from the registry, not from Mattermost.

### Update a Bot

```bash
python3 scripts/manage-bots.py update <username> [--token TOKEN] [--display-name NAME] [--description DESC] [--active/--inactive]
```

## Bot Registry

The bot registry is stored at: `RPG_LLM_DATA/bots/registry.json`

Format:
```json
{
  "username": {
    "username": "test-bot",
    "token": "bot_token_here",
    "display_name": "Test Bot",
    "description": "A test bot",
    "user_id": "mattermost_user_id",
    "created_at": "2026-01-09T12:00:00",
    "is_active": true
  }
}
```

## Integration with Services

The `mattermost_bot` service automatically loads bots from the registry. The service will:

1. First check `MATTERMOST_BOT_TOKEN` from environment (for backward compatibility)
2. Load all active bots from the registry
3. Use the primary bot (`rpg-bot` or first active bot) if no environment token is set

### Accessing Bot Tokens in Code

```python
from services.mattermost_bot.src.config import Config

# Get primary bot token
token = Config.get_bot_token()

# Get token for specific bot
token = Config.get_bot_token("test-bot")

# Get all bot tokens
all_tokens = Config.get_all_bot_tokens()
```

## Using the Bot Registry API

You can also use the registry programmatically:

```python
from shared.bot_registry import BotRegistry

registry = BotRegistry()

# Add a bot
bot = registry.add_bot(
    username="my-bot",
    token="token_here",
    display_name="My Bot",
    description="Description"
)

# Get a bot
bot = registry.get_bot("my-bot")

# Get bot token
token = registry.get_bot_token("my-bot")

# List all bots
bots = registry.list_bots(active_only=True)

# Get all tokens
tokens = registry.get_all_tokens(active_only=True)
```

## Best Practices

1. **Keep `rpg-bot` in `.env`**: The primary bot token should remain in `.env` for backward compatibility
2. **Use registry for additional bots**: All other bots should be managed through the registry
3. **Mark inactive bots**: Use `--inactive` flag instead of deleting bots you might need later
4. **Backup registry**: The registry file is in your data directory, so it's included in backups

## Troubleshooting

### Bot not found in registry

If a bot exists in Mattermost but not in the registry:
```bash
python3 scripts/manage-bots.py add <username> <token>
```

### Bot token expired

Regenerate the token in Mattermost UI, then update the registry:
```bash
python3 scripts/manage-bots.py update <username> --token <new_token>
```

### Service not loading bots from registry

Check that:
1. The registry file exists at `RPG_LLM_DATA/bots/registry.json`
2. The file is valid JSON
3. Bots are marked as `is_active: true`
4. The service has access to the data directory

## Migration from .env

If you have multiple bot tokens in `.env`, you can migrate them:

```bash
# For each bot token in .env:
python3 scripts/manage-bots.py add <username> <token> "<display_name>" "<description>"
```

Then remove the tokens from `.env` (keep only `MATTERMOST_BOT_TOKEN` for `rpg-bot`).
