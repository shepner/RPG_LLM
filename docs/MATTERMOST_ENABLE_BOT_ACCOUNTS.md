# Enable Bot Account Creation in Mattermost

## Issue
When trying to create a bot account, you see: "Enable bot account creation in the System Console."

## Solution

### Method 1: Via System Console UI (Recommended)

1. **Log in** to Mattermost as a System Administrator
2. **Open System Console**: Click the ☰ menu → System Console
3. **Navigate to**: Integrations → Bot Accounts
4. **Enable the setting**: 
   - Look for "Enable Bot Account Creation" toggle
   - Set it to `true` or `ON`
   - Click **Save**

### Method 2: Via Database (Already Done)

If the UI setting doesn't work, the setting has been enabled directly in the database:

```sql
INSERT INTO systems (name, value) 
VALUES ('EnableBotAccountCreation', 'true')
ON CONFLICT (name) DO UPDATE SET value = 'true';
```

This has already been applied to your instance.

### Method 3: Via Configuration File

You can also set this in the Mattermost configuration file (`config/config.json`):

```json
{
  "ServiceSettings": {
    "EnableBotAccountCreation": true
  }
}
```

## Verification

After enabling, you should be able to:
1. Go to System Console → Integrations → Bot Accounts
2. See the "Add Bot Account" button
3. Create bot accounts without the error message

## Next Steps

Once enabled:
1. Create your bot account (username: `rpg-bot`)
2. Copy the access token
3. Add it to your `.env` file as `MATTERMOST_BOT_TOKEN`
4. Restart the bot service: `docker-compose restart mattermost_bot`

## Troubleshooting

If you still can't create bot accounts:
1. **Check permissions**: Ensure you're logged in as a System Administrator
2. **Refresh browser**: Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
3. **Check logs**: `docker-compose logs mattermost | grep -i bot`
4. **Verify setting**: Check the database:
   ```bash
   docker-compose exec mattermost_db psql -U mmuser -d mattermost -c "SELECT value FROM systems WHERE name = 'EnableBotAccountCreation';"
   ```
   Should return: `true`
