# Being Instance Service

## Overview

The Being Instance Service is an isolated container service that runs a single thinking being (character). Each being gets its own container with:

- Isolated database (`being_{being_id}.db`)
- Isolated vector store (`vector_stores/being_{being_id}/`)
- Isolated LLM instance
- Isolated memory and prompts
- Own service endpoint

## Architecture

This service is designed to be instantiated per-being by the Being Registry orchestrator. Each container:

1. Receives `BEING_ID` via environment variable
2. Initializes isolated storage for that being
3. Runs a lightweight FastAPI service
4. Handles all interactions for that single being

## Environment Variables

- `BEING_ID` (required): The unique ID of the being this instance represents
- `DATABASE_URL`: SQLite database path (defaults to `being_{BEING_ID}.db`)
- `VECTOR_STORE_PATH`: Vector store path (defaults to `vector_stores/being_{BEING_ID}/`)
- `GEMINI_API_KEY`: Gemini API key for LLM
- `LLM_MODEL`: LLM model name (default: `gemini-2.5-flash`)
- `AUTH_URL`: Auth service URL
- `BEING_REGISTRY_URL`: Being registry service URL
- `PORT`: Service port (default: 8000)

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "being_id": "abc123...",
  "service": "being_instance"
}
```

### `GET /info`
Get being information (fetches from registry).

**Response:**
```json
{
  "being_id": "abc123...",
  "name": "Character Name",
  "owner_id": "user123...",
  "session_id": "session123...",
  "container_status": "running",
  "service_endpoint": "http://being_abc123:8000"
}
```

### `POST /query`
Main interaction endpoint - query the being.

**Request:**
```json
{
  "query": "Hello, how are you?",
  "context": {"location": "tavern"},
  "session_id": "session123",
  "game_system": "D&D 5e",
  "source_user_id": "user123"
}
```

**Response:**
```json
{
  "service": "Being Instance",
  "query": "Hello, how are you?",
  "response": "I'm doing well, thank you!",
  "being_id": "abc123...",
  "metadata": {
    "context_provided": true,
    "stored_in_memory": true
  }
}
```

### `POST /think`
Generate internal thoughts (private to the being).

**Request:**
```
context: "The tavern is getting crowded"
game_time: 1234.5
```

**Response:**
```json
{
  "thought_id": "thought123...",
  "being_id": "abc123...",
  "text": "I should find a quieter spot...",
  "game_time": 1234.5,
  "metadata": {}
}
```

### `POST /decide`
Make a decision and generate action.

**Request:**
```
context: "I need to find information about the quest"
game_time: 1234.5
```

**Response:**
```json
{
  "action_id": "action123...",
  "being_id": "abc123...",
  "action_type": "general",
  "description": "I'll ask the bartender",
  "game_time": 1234.5,
  "metadata": {}
}
```

### `POST /memory/event`
Add a memory event.

**Request:**
```json
{
  "event_type": "incoming_message",
  "visibility": "public",
  "content": "Hello!",
  "session_id": "session123",
  "source_being_id": "other_being123",
  "metadata": {"emotion": "friendly"}
}
```

### `POST /memory/search`
Search memories.

**Request:**
```
query: "conversations about the quest"
n_results: 10
event_types: ["incoming_message", "outgoing_response"]
include_private: false
```

## Building

```bash
docker build -f services/being_instance/Dockerfile -t rpg_llm_being_instance:latest .
```

## Running Manually (for testing)

```bash
# Set environment variables
export BEING_ID=test-being-123
export GEMINI_API_KEY=your-key-here
export DATABASE_URL=sqlite+aiosqlite:///./RPG_LLM_DATA/databases/being_test-being-123.db
export VECTOR_STORE_PATH=./RPG_LLM_DATA/vector_stores/being_test-being-123

# Run the service
cd services/being_instance
python main.py
```

## Integration with Being Registry

The Being Registry orchestrator will:
1. Create character data
2. Spin up a container with `BEING_ID={being_id}` environment variable
3. Assign unique port
4. Store service endpoint in registry
5. Route queries to the correct being instance

## Storage Isolation

Each being instance has completely isolated storage:

- **Database**: `RPG_LLM_DATA/databases/being_{being_id}.db`
  - System prompts
  - Being-specific configuration
  
- **Vector Store**: `RPG_LLM_DATA/vector_stores/being_{being_id}/`
  - All memories
  - Conversations
  - Thoughts
  - Actions
  - State changes

## Memory System

The being instance uses the comprehensive memory event system:
- All incoming messages are stored
- All outgoing responses are stored
- Internal thoughts are stored (private)
- Actions are stored
- State changes are stored
- Metadata distinguishes internal vs external
