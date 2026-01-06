# Docker Troubleshooting Guide

## Connection Issues

If you see errors like:
```
Cannot connect to the Docker daemon at unix:///Users/shepner/.docker/run/docker.sock
```

### Solutions

1. **Restart Docker Desktop**
   - Quit Docker Desktop completely
   - Reopen Docker Desktop
   - Wait for the whale icon to appear in the menu bar
   - Wait until it shows "Docker Desktop is running"

2. **Verify Docker is Running**
   ```bash
   docker ps
   ```
   This should list running containers (or show an empty list, not an error).

3. **Check Docker Context**
   ```bash
   docker context ls
   docker context use desktop-linux
   ```

4. **Verify Socket Permissions**
   ```bash
   ls -la ~/.docker/run/docker.sock
   ```
   Should show: `srwxr-xr-x` (socket, readable/writable by owner)

5. **Restart Docker Daemon**
   - In Docker Desktop: Settings → Troubleshoot → Restart Docker

## Testing Once Docker is Running

1. **Start Services**
   ```bash
   docker compose up -d
   ```

2. **Check Status**
   ```bash
   docker compose ps
   ```

3. **Run Tests**
   ```bash
   ./scripts/test-services.sh
   ```

4. **View Logs**
   ```bash
   docker compose logs -f [service_name]
   ```

## Common Issues

### Port Already Allocated
If you see "port is already allocated":
```bash
# Find what's using the port
lsof -i :8000

# Kill the process or change the port in docker-compose.yml
```

### Services Not Starting
Check logs for specific errors:
```bash
docker compose logs [service_name]
```

### Build Failures
Rebuild specific service:
```bash
docker compose build --no-cache [service_name]
```

### Environment Variables Not Set
Ensure `.env` file exists with:
```
JWT_SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-api-key
```

## Verification Checklist

- [ ] Docker Desktop is running (whale icon visible)
- [ ] `docker ps` works without errors
- [ ] `.env` file exists with required variables
- [ ] Ports 8000-8007 and 8080 are available
- [ ] `docker compose ps` shows services
- [ ] Health endpoints respond: `curl http://localhost:8000/health`

