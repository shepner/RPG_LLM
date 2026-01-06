# Testing Guide

This document provides instructions for testing the TTRPG LLM System.

## Prerequisites

1. **Docker Desktop** must be running
2. **Environment variables** configured in `.env` file:
   - `JWT_SECRET_KEY` - Secret key for JWT tokens
   - `GEMINI_API_KEY` - Gemini API key (optional for basic tests)

## Quick Start Testing

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **Wait for services to initialize** (about 10-15 seconds)

3. **Run automated tests:**
   ```bash
   ./scripts/test-services.sh
   ```

## Manual Testing

### Health Checks

Test each service's health endpoint:

```bash
curl http://localhost:8000/health  # Auth
curl http://localhost:8001/health  # Game Session
curl http://localhost:8002/health  # Rules Engine
curl http://localhost:8003/health  # Time Management
curl http://localhost:8004/health  # Worlds
curl http://localhost:8005/health  # Game Master
curl http://localhost:8006/health  # Being
curl http://localhost:8007/health  # Being Registry
```

### Auth Service Tests

1. **Register a user:**
   ```bash
   curl -X POST http://localhost:8000/register \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "email": "test@example.com",
       "password": "testpass123",
       "role": "player"
     }'
   ```

2. **Login:**
   ```bash
   curl -X POST http://localhost:8000/login \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "password": "testpass123"
     }'
   ```

3. **Get current user (with token):**
   ```bash
   TOKEN="your-token-here"
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me
   ```

### Game Session Service Tests

1. **List sessions:**
   ```bash
   curl http://localhost:8001/sessions
   ```

2. **Create a session:**
   ```bash
   curl -X POST http://localhost:8001/sessions?gm_user_id=user123 \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Session",
       "description": "A test game session",
       "game_system_type": "D&D",
       "time_mode_preference": "real-time"
     }'
   ```

### Rules Engine Tests

1. **Roll dice:**
   ```bash
   curl -X POST "http://localhost:8002/roll?dice=1d20"
   curl -X POST "http://localhost:8002/roll?dice=2d6+3"
   ```

2. **Resolve action:**
   ```bash
   curl -X POST http://localhost:8002/resolve \
     -H "Content-Type: application/json" \
     -d '{
       "action": "attack",
       "context": {"attacker": "player1", "target": "goblin"}
     }'
   ```

### Worlds Service Tests

1. **Record an event:**
   ```bash
   curl -X POST http://localhost:8004/events \
     -H "Content-Type: application/json" \
     -d '{
       "event_type": "combat",
       "description": "Player attacks goblin",
       "game_time": 100.5,
       "metadata": {"damage": 10}
     }'
   ```

2. **Search history:**
   ```bash
   curl -X POST http://localhost:8004/history/search \
     -H "Content-Type: application/json" \
     -d '{
       "query": "combat",
       "n_results": 10
     }'
   ```

### Web Interface

Access the web interface at: **http://localhost:8080**

The interface provides:
- User authentication (login/register)
- Real-time event updates via WebSocket
- Narrative display
- Action input form

## Troubleshooting

### Services Not Starting

1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **Check service logs:**
   ```bash
   docker-compose logs [service_name]
   ```

3. **Check for port conflicts:**
   ```bash
   lsof -i :8000-8007
   ```

### Common Issues

1. **"Cannot connect to Docker daemon"**
   - Start Docker Desktop
   - Wait for Docker to fully initialize

2. **"Port already allocated"**
   - Stop conflicting services
   - Or change ports in `docker-compose.yml`

3. **"Module not found: shared"**
   - Rebuild the service: `docker-compose build [service_name]`
   - Ensure Dockerfile copies shared modules correctly

4. **"Email validation error"**
   - Ensure `pydantic[email]` is in requirements.txt
   - Rebuild auth service

## Service Status

Check all service statuses:

```bash
docker-compose ps
```

View logs for all services:

```bash
docker-compose logs -f
```

View logs for a specific service:

```bash
docker-compose logs -f auth
```

## Stopping Services

Stop all services:

```bash
docker-compose down
```

Stop and remove volumes:

```bash
docker-compose down -v
```

