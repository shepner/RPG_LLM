# Being Isolation Architecture

## Overview

This document describes the architecture for isolating each thinking being (character) into its own containerized service instance, similar to how ChatGPT manages separate chat sessions.

## Current Architecture (Shared Service)

**Current State:**
- All beings share a single "being" service
- All beings share the same database (different collections)
- All beings use shared LLM provider instances
- Being IDs are used to differentiate within the shared service

**Limitations:**
- No true isolation between beings
- Shared resources can cause interference
- Difficult to scale individual beings
- All beings share the same service lifecycle

## Target Architecture (Isolated Containers)

**Target State:**
- Each being gets its own isolated container/service instance
- Each being has its own database/storage
- Each being has its own LLM instance
- Each being has its own service endpoint (unique port or subdomain)
- Complete isolation - like separate ChatGPT conversations

## Architecture Components

### 1. Being Instance Service

A lightweight FastAPI service that runs one being:

```
services/being_instance/
├── Dockerfile
├── main.py
├── requirements.txt
└── src/
    ├── __init__.py
    ├── api.py          # Single-being API endpoints
    ├── being_agent.py # LLM agent for this being
    ├── memory.py       # Isolated memory manager
    ├── models.py       # Being-specific models
    └── storage.py      # Isolated storage (SQLite per being)
```

**Key Features:**
- Single being_id per instance (set via environment variable)
- Isolated SQLite database: `being_{being_id}.db`
- Isolated vector store: `vector_stores/being_{being_id}/`
- Isolated memory and prompts
- Own LLM provider instance

### 2. Container Orchestration

The `being_registry` service orchestrates containers:

**On Character Creation:**
1. Create character data
2. Spin up new container with `BEING_ID={being_id}` environment variable
3. Assign unique port (e.g., 9000 + hash(being_id))
4. Store service endpoint in registry
5. Wait for container to be healthy
6. Return being_id and endpoint

**Container Configuration:**
```yaml
# Dynamic container creation
being_{being_id}:
  image: rpg_llm_being_instance:latest
  environment:
    - BEING_ID={being_id}
    - DATABASE_URL=sqlite+aiosqlite:///./RPG_LLM_DATA/databases/being_{being_id}.db
    - VECTOR_STORE_PATH=./RPG_LLM_DATA/vector_stores/being_{being_id}
    - GEMINI_API_KEY=${GEMINI_API_KEY}
    - LLM_MODEL=${LLM_MODEL}
    - AUTH_URL=http://auth:8000
    - BEING_REGISTRY_URL=http://being_registry:8007
  ports:
    - "{dynamic_port}:8000"
  volumes:
    - ./RPG_LLM_DATA:/app/RPG_LLM_DATA
```

### 3. Service Discovery & Routing

**Being Registry as Router:**
- Maintains mapping: `being_id -> service_endpoint`
- Routes queries to correct being instance
- Handles being-to-being communication
- Manages container lifecycle

**API Flow:**
```
User -> being_registry/query/{being_id} 
     -> being_registry looks up endpoint
     -> being_registry proxies to being_{being_id}:{port}/query
     -> being instance responds
     -> being_registry returns response
```

### 4. Being Instance API

Each being instance exposes:

```python
POST /query
  - Receives query
  - Uses being's own LLM instance
  - Stores in being's own memory
  - Returns response

GET /health
  - Health check for container

GET /info
  - Returns being metadata (name, personality, etc.)

POST /update
  - Update being's character data
```

### 5. Storage Isolation

**Per-Being Storage:**
- Database: `RPG_LLM_DATA/databases/being_{being_id}.db`
- Vector Store: `RPG_LLM_DATA/vector_stores/being_{being_id}/`
- Prompts: Stored in being's own database
- Memories: Stored in being's own vector store

## Implementation Plan

### Phase 1: Create Being Instance Service
1. Create `services/being_instance/` directory structure
2. Implement single-being API
3. Add environment-based being_id configuration
4. Implement isolated storage
5. Test with single being

### Phase 2: Container Orchestration
1. Enhance `ContainerOrchestrator` to create being instances
2. Implement dynamic port assignment
3. Add health checks
4. Update `being_registry` to use orchestrator
5. Test container creation/deletion

### Phase 3: Service Discovery
1. Implement endpoint registration in registry
2. Add routing logic to being_registry
3. Update frontend to use being_registry as router
4. Test end-to-end communication

### Phase 4: Migration & Cleanup
1. Migrate existing beings to isolated containers
2. Update all being interactions to use new architecture
3. Remove shared being service (or keep as fallback)
4. Update documentation

## Benefits

1. **True Isolation**: Each being is completely isolated
2. **Independent Scaling**: Scale beings individually
3. **Resource Management**: Each being has its own resources
4. **Security**: Isolated containers improve security
5. **Debugging**: Easier to debug individual beings
6. **Lifecycle Management**: Start/stop beings independently

## Challenges

1. **Resource Usage**: More containers = more resources
2. **Port Management**: Need dynamic port assignment
3. **Service Discovery**: Need robust routing
4. **Migration**: Need to migrate existing beings
5. **Complexity**: More moving parts to manage

## Alternative: Hybrid Approach

For development/testing, could use:
- Shared service for development
- Isolated containers for production
- Configuration flag to choose mode
