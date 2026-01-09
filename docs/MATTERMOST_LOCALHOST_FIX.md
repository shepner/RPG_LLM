# Fixing Mattermost localhost Connection Issue

## Problem

When using `http://localhost:8008/webhook` as the slash command URL, you get:
```
dial tcp [::1]:8008: connect: connection refused
```

## Why This Happens

From inside a Docker container, `localhost` refers to the container itself, not the host machine. So when Mattermost tries to connect to `localhost:8008`, it's looking inside its own container, not on the host where the bot service is running.

## Solutions

### Solution 1: Use Docker Service Name (Recommended)

1. **Edit the slash command** in Mattermost:
   - Main Menu → Integrations → Slash Commands
   - Edit your 'rpg' command
   - Change URL to: `http://mattermost_bot:8008/webhook`
   - Save

2. **Verify AllowedUntrustedInternalConnections** is set:
   - This should already be configured in `docker-compose.yml`
   - If it still doesn't work, check System Console → Environment → Web Server

### Solution 2: Use host.docker.internal (Mac/Windows)

If you're on Mac or Windows:
1. Edit slash command URL to: `http://host.docker.internal:8008/webhook`
2. This special hostname resolves to the host machine from inside Docker

### Solution 3: Use Host Machine IP

1. Find your host IP:
   ```bash
   # On Mac/Linux
   ifconfig | grep "inet " | grep -v 127.0.0.1
   
   # Or use Docker gateway
   docker network inspect rpg_llm_default | grep Gateway
   ```

2. Use that IP: `http://[HOST_IP]:8008/webhook`

## Verification

After changing the URL:

1. Wait a few seconds
2. Try `/rpg health` in Mattermost
3. Check logs: `docker-compose logs mattermost_bot | tail -10`
4. Should see: `"POST /webhook HTTP/1.1" 200 OK`

## Recommended: Use Service Name

The best solution is to use `http://mattermost_bot:8008/webhook` because:
- It works within the Docker network
- No need to know host IPs
- More reliable in Docker Compose setups

Make sure `AllowedUntrustedInternalConnections` includes `mattermost_bot` (already configured in docker-compose.yml).
