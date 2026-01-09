# Quick Start - Mattermost Integration

## 🚀 Fastest Path to Testing

### 1. Add to `.env` file:
```bash
MATTERMOST_DB_PASSWORD=test123
MATTERMOST_BOT_TOKEN=  # Leave empty for now
```

### 2. Start services:
```bash
docker-compose up -d mattermost_db mattermost mattermost_bot
```

### 3. Open Mattermost:
Go to http://localhost:8065 and create admin account

### 4. Create bot:
- System Console → Integrations → Bot Accounts
- Add bot: username `rpg-bot`
- **Copy the token!**

### 5. Update `.env`:
```bash
MATTERMOST_BOT_TOKEN=your_copied_token_here
```

### 6. Restart bot:
```bash
docker-compose restart mattermost_bot
```

### 7. Test:
In Mattermost, type: `/rpg-health`

## ✅ Success Indicators

- Mattermost loads at http://localhost:8065
- Bot service shows "Mattermost bot initialized" in logs
- `/rpg-health` command returns service status
- Character creation works

## 📖 Full Guide

See `TESTING_GUIDE.md` for detailed steps and troubleshooting.
