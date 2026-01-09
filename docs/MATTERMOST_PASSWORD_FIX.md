# Mattermost Database Password Issue

## Problem

If your `MATTERMOST_DB_PASSWORD` contains special characters (like `!`, `&`, `%`, `@`, etc.), Mattermost may fail to connect to the database with URL parsing errors.

## Solution

You have two options:

### Option 1: Use a Simple Password (Recommended)

Use a password without special characters that need URL encoding:

```bash
MATTERMOST_DB_PASSWORD=simple_password_123
```

### Option 2: URL-Encode Your Password

If you must use special characters, URL-encode them:

```python
from urllib.parse import quote
password = "your!@#password"
encoded = quote(password, safe='')
print(encoded)  # Use this in .env
```

Common encodings:
- `!` → `%21`
- `@` → `%40`
- `#` → `%23`
- `$` → `%24`
- `%` → `%25`
- `&` → `%26`

### Option 3: Use Separate Connection Components

Edit `docker-compose.yml` to use separate environment variables (requires Mattermost configuration file approach).

## Quick Fix

The easiest solution is to change your password to something without special characters:

1. Stop Mattermost:
   ```bash
   docker-compose stop mattermost mattermost_db
   ```

2. Update `.env`:
   ```bash
   MATTERMOST_DB_PASSWORD=mmuser_password_123
   ```

3. Remove old database volume (if needed):
   ```bash
   docker-compose down -v mattermost_db
   ```

4. Restart:
   ```bash
   docker-compose up -d mattermost_db mattermost
   ```

## Verification

After fixing, check Mattermost logs:
```bash
docker-compose logs mattermost | grep -i "listening\|ready\|error"
```

You should see "Server is listening" without connection errors.
