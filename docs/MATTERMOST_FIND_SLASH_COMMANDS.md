# Finding Slash Commands in Mattermost

## Location

Slash commands are **NOT** in System Console. They're in the **Main Menu**.

## Steps to Find Slash Commands

### Method 1: Main Menu (Recommended)

1. **Click the hamburger menu** (☰) in the **top left** of Mattermost
   - This is the main menu, NOT the System Console menu
   
2. Look for **"Integrations"** in the menu
   - If you don't see it, you might need to enable integrations first

3. Click **"Integrations"** → **"Slash Commands"**

4. Click **"Add Slash Command"**

### Method 2: Direct URL

If you can't find it in the menu, try going directly to:
- `http://localhost:8065/YOUR_TEAM_NAME/integrations/commands`

Replace `YOUR_TEAM_NAME` with your team name (e.g., `rpg-llm`)

### Method 3: Enable Integrations First

If you don't see "Integrations" in the menu:

1. Go to **System Console** (☰ menu → System Console)
2. Navigate to: **Integrations** → **Integration Management**
3. Make sure **"Enable Custom Slash Commands"** is set to `true`
4. Save
5. Go back to Main Menu → Integrations → Slash Commands

## Alternative: Use Regular Messages

**Good news**: You don't actually need slash commands! The bot can respond to regular messages that start with `/rpg-` in any channel. Just type:

- `/rpg-health` (as a regular message, not a slash command)
- `/rpg-create-character TestChar`
- etc.

The bot will detect these and respond automatically via webhook events.

## Still Can't Find It?

If you still can't find the Slash Commands option:

1. **Check permissions**: Make sure you're logged in as a System Admin
2. **Check Mattermost version**: Some older versions have different menu structures
3. **Use the API**: We can register commands programmatically (see below)
