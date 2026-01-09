# ✅ Mattermost Integration - Ready for Testing

## Current Status

✅ **All services are running:**
- Mattermost database (PostgreSQL) - Healthy
- Mattermost Bot service - Running and responding
- ⚠️ Mattermost server - May have password encoding issue

## ⚠️ Important: Database Password Issue

If your `MATTERMOST_DB_PASSWORD` contains special characters (`!`, `@`, `#`, `%`, `&`, etc.), Mattermost may fail to start.

**Quick Fix:**
1. Use a simpler password without special characters, OR
2. URL-encode your password using: `./scripts/fix-mattermost-password.sh "your_password"`
3. Update `.env` with the encoded password
4. Restart: `docker-compose restart mattermost mattermost_db`

See `docs/MATTERMOST_PASSWORD_FIX.md` for details.

## What's Working

1. ✅ Bot service is built and running
2. ✅ Health endpoint responds correctly
3. ✅ Configuration is loaded from environment
4. ✅ Services can communicate

## Next Steps to Complete Setup

### 1. Wait for Mattermost to Initialize

Mattermost is still starting up. Wait 30-60 seconds, then:

```bash
# Check if Mattermost is ready
curl http://localhost:8065/api/v4/system/ping
```

If it returns `{"status":"OK"}`, Mattermost is ready.

### 2. Access Mattermost Web Interface

Open in your browser: **http://localhost:8065**

### 3. Complete First-Time Setup

1. Create your admin account
2. Complete the initial configuration
3. You'll be logged into Mattermost

### 4. Verify Bot Connection

After Mattermost is ready, check bot logs:

```bash
docker-compose logs mattermost_bot | grep -i "connected\|initialized"
```

You should see: `Connected to Mattermost as rpg-bot`

### 5. Test the Integration

Once Mattermost is ready and bot is connected:

1. **Test health command** (if slash commands are configured):
   - In Mattermost, type: `/rpg-health`
   - Should return service status

2. **Or test via API**:
   ```bash
   curl http://localhost:8008/health
   ```

3. **Create a character**:
   - Use `/rpg-create-character TestChar` in Mattermost
   - Or create via web interface
   - Check if DM channel was created

## Troubleshooting

### Bot Can't Connect to Mattermost

This is normal during initial startup. The bot will retry when Mattermost is ready.

**Check Mattermost status:**
```bash
docker-compose logs mattermost | tail -20
```

**Wait for Mattermost to be ready:**
- Look for "Server is listening" in logs
- Or check: `curl http://localhost:8065/api/v4/system/ping`

### Bot Token Issues

If you see token errors:
1. Verify token in `.env`: `grep MATTERMOST_BOT_TOKEN .env`
2. Restart bot: `docker-compose restart mattermost_bot`

### Services Not Communicating

Check network:
```bash
docker-compose exec mattermost_bot ping -c 1 mattermost
```

## Quick Verification Commands

```bash
# Check all services
docker-compose ps

# Check bot health
curl http://localhost:8008/health

# Check Mattermost
curl http://localhost:8065/api/v4/system/ping

# View bot logs
docker-compose logs mattermost_bot --tail 20

# View Mattermost logs
docker-compose logs mattermost --tail 20
```

## Expected Behavior

Once everything is ready:
- ✅ Bot connects to Mattermost automatically
- ✅ Bot responds to commands
- ✅ Character creation triggers channel creation
- ✅ Session creation triggers channel creation
- ✅ Messages route to appropriate services

## Ready to Test!

The integration is implemented and services are running. Complete the Mattermost setup steps above, then you can start testing character conversations and administrative commands!
