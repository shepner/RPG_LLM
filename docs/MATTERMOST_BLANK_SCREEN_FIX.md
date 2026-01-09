# Fixing Mattermost Blank Screen Issue

## Problem
Mattermost shows a blank dark blue screen with "Preview Mode" banner and `/preparing-workspace` URL.

## Root Cause
Mattermost has users but **no teams**. Without a team, there's nothing to display.

## Solution

### Option 1: Complete Setup via Web UI (Recommended)

1. **Refresh the page**: http://localhost:8065
2. **Look for setup options**:
   - If you see a "Create Team" or "Get Started" button, click it
   - Fill out the team creation form
   - Name: `rpg-llm` or any name you prefer
   - Type: Open (public) or Private

3. **If you see a login page**:
   - Log in with your existing account (username: `shepner`)
   - After login, you should see an option to create a team
   - Or go to: System Console → Teams → Create Team

### Option 2: Use API to Create Team

If you have admin credentials, you can use the API:

```bash
# Set your admin credentials
export MATTERMOST_ADMIN_EMAIL="shepner@asyla.org"
export MATTERMOST_ADMIN_PASSWORD="your_password"

# Run the script
./scripts/create-mattermost-team.sh
```

### Option 3: Manual Team Creation via SQL (Advanced)

If the above don't work, you can manually create a team via SQL, but this is complex due to Mattermost's schema requirements.

## Verification

After creating a team, verify it exists:

```bash
docker-compose exec mattermost_db psql -U mmuser -d mattermost -c "SELECT name, displayname FROM teams WHERE deleteat = 0;"
```

You should see your team listed.

## Next Steps

Once a team is created:
1. Refresh Mattermost in your browser
2. You should see the team and channels
3. You can then create the bot account (System Console → Integrations → Bot Accounts)
