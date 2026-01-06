# Security Guidelines

## Overview

This document outlines security best practices for the TTRPG LLM System. **All API keys, secrets, and sensitive credentials must NEVER be committed to the repository.**

## Required Secrets

### API Keys
- `GEMINI_API_KEY`: Google Gemini API key (GCP)
- `OPENAI_API_KEY`: OpenAI API key (optional, if using OpenAI)
- `ANTHROPIC_API_KEY`: Anthropic API key (optional, if using Anthropic)

### Authentication Secrets
- `JWT_SECRET_KEY`: Secret key for JWT token signing (MUST be changed in production)
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)
- `JWT_EXPIRATION`: Token expiration time (default: 24h)

### Service Account Files
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account JSON file (if using service account)

### Database Credentials
- Database URLs (if using PostgreSQL instead of SQLite)

## Setup Instructions

### Local Development

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your actual API keys and secrets

3. Copy the example configuration:
   ```bash
   cp config/config.yaml.example config/config.yaml
   ```

4. Edit `config/config.yaml` with your settings

### Production Deployment

- Use secret management services (GCP Secret Manager, AWS Secrets Manager, etc.)
- Use environment variables from container orchestration
- Never store secrets in code or config files
- Rotate secrets regularly

## What to Do If Secrets are Committed

If secrets are accidentally committed:

1. **Immediately** rotate all exposed secrets
2. Remove from git history: `git filter-branch` or BFG Repo-Cleaner
3. Force push (coordinate with team)
4. Update all affected services
5. Review git history for other exposed secrets

## Pre-Commit Hooks

A pre-commit hook is recommended to prevent accidental commits of secret files. See `.git/hooks/pre-commit` for an example implementation.

## Best Practices

- Never commit `.env` files
- Never commit `config/config.yaml` (only `config.yaml.example`)
- Never commit service account JSON files
- Never commit API keys in code
- Use `.env.example` and `config.yaml.example` as templates only
- Review `.gitignore` regularly to ensure all secret patterns are covered

