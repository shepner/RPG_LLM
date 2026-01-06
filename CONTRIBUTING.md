# Contributing to TTRPG LLM System

Thank you for your interest in contributing!

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/RPG_LLM.git`
3. Run setup: `./scripts/setup.sh`
4. Copy `.env.example` to `.env` and configure
5. Start services: `docker-compose up -d`

## Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small

## Security

**CRITICAL**: Never commit:
- `.env` files
- `config/config.yaml` (only `config.yaml.example`)
- API keys or secrets
- Service account JSON files
- Any game data files

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all tests pass
4. Update documentation if needed
5. Submit a pull request with a clear description

## Questions?

Open an issue for questions or discussions.

