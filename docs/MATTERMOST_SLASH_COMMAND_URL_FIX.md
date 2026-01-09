# Fixing Mattermost Slash Command "Address Forbidden" Error

## Problem

When using `/rpg` commands, you see:
```
Command with a trigger of 'rpg' failed.
```

The error in logs shows:
```
address forbidden, you may need to set AllowedUntrustedInternalConnections
```

## Solution 1: Use localhost URL (Recommended)

Instead of using the Docker hostname, use `localhost`:

1. **Go to Mattermost**: Main Menu → Integrations → Slash Commands
2. **Edit your 'rpg' command**
3. **Change Request URL** from:
   ```
   http://mattermost_bot:8008/webhook
   ```
   To:
   ```
   http://localhost:8008/webhook
   ```
4. **Save**

This works because Mattermost can reach `localhost:8008` which is exposed on the host.

## Solution 2: Configure via System Console

If localhost doesn't work, configure via System Console:

1. **System Console** → **Environment** → **Web Server**
2. Find **"Allowed Untrusted Internal Connections"**
3. Add: `mattermost_bot,localhost,127.0.0.1,172.20.0.0/16`
4. **Save**
5. Restart Mattermost: `docker-compose restart mattermost`

## Solution 3: Update config.json Directly

If environment variables don't work, update the config file:

1. Find the config file:
   ```bash
   docker-compose exec mattermost ls -la /mattermost/config/
   ```

2. Edit `config.json` and add:
   ```json
   {
     "ServiceSettings": {
       "AllowedUntrustedInternalConnections": "mattermost_bot,localhost,127.0.0.1,172.20.0.0/16"
     }
   }
   ```

3. Restart Mattermost

## Verification

After applying the fix:

1. Wait 10-15 seconds for Mattermost to restart (if needed)
2. Try: `/rpg health` in any channel
3. Check bot logs: `docker-compose logs mattermost_bot | tail -10`
4. Should see: `"POST /webhook HTTP/1.1" 200 OK`

## Why This Happens

Mattermost blocks connections to internal/private IP addresses by default for security. The `AllowedUntrustedInternalConnections` setting tells Mattermost which internal addresses to trust.
