# Setting Up Autocomplete for Mattermost Slash Commands

## Overview

Mattermost supports autocomplete hints for slash commands, making it easier for users to discover and use commands.

## Current Setup

The slash command is configured with:
- **Trigger**: `rpg`
- **Autocomplete**: Enabled (checkbox checked)

## Improving Autocomplete

### Option 1: Add Autocomplete Description and Hint

1. **Edit the slash command** in Mattermost:
   - Main Menu → Integrations → Slash Commands
   - Click on your 'rpg' command

2. **Update these fields**:
   - **Autocomplete Description**: `RPG LLM system commands`
   - **Autocomplete Hint**: `[command] [args] - Type 'health', 'create-character', etc.`

3. **Save**

### Option 2: Use Multiple Slash Commands (Advanced)

For even better UX, you could create separate slash commands for each action:
- `/rpg-health` - Health check
- `/rpg-create-character` - Create character
- `/rpg-list-characters` - List characters
- etc.

Each would point to the same webhook URL, and the bot would parse the command name from the trigger word.

### Option 3: Improve Help Message

The help message (when typing just `/rpg`) has been improved to show:
- Organized categories
- Clear examples
- Better formatting

## Current Behavior

When users type `/rpg`:
- They see the trigger in autocomplete
- They can type a space and start typing the command
- If they submit just `/rpg`, they get a helpful list of commands

## Best Practice

The current setup is good, but you can enhance it by:
1. Adding a clear autocomplete hint
2. Using the improved help message (already implemented)
3. Teaching users the format: `/rpg [command]`

## Example Usage

```
/rpg health                    → Check status
/rpg create-character Gandalf  → Create character
/rpg list-characters           → List characters
/rpg roll 1d20                 → Roll dice
```
