# TTRPG LLM System

A game-system-agnostic, LLM/AI-based Table Top Role Playing Game (TTRPG) management system.

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <repository-url>
   cd RPG_LLM
   ./scripts/setup.sh
   ```

2. **Configure Secrets**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   cp config/config.yaml.example config/config.yaml
   # Edit config.yaml with your settings
   ```

3. **Start Services**:
   ```bash
   docker-compose up -d
   ```

## Architecture

The system consists of microservices:

- **Thoth (Game Master)**: Narrative generation and story management
- **Gaia (Worlds)**: World state tracking and logical consistency
- **Atman (Being)**: Character decision-making and memory
- **Ma'at (Rules Engine)**: Rule resolution and validation
- **Auth Service**: User authentication and authorization
- **Game Session Service**: Session lifecycle management
- **Time Management Service**: Game time progression
- **Being Registry Service**: Container orchestration

## Documentation

- `docs/SETUP.md`: Detailed setup instructions
- `docs/DEPLOYMENT.md`: Production deployment guide
- `docs/DATA_MANAGEMENT.md`: Data management procedures
- `SECURITY.md`: Security guidelines

## License

[Your License Here]

