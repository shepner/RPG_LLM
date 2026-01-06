# Credentials Setup Guide

## GCP/Gemini API Credentials

The system uses Google's Gemini API for LLM and embedding services. You have two options for providing credentials:

### Option 1: API Key (Recommended for Development)

1. **Get your Gemini API key:**
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Copy the API key

2. **Add to `.env` file:**
   - Create a `.env` file in the project root (`RPG_LLM/.env`)
   - Add the following line:
     ```
     GEMINI_API_KEY=your-api-key-here
     ```

### Option 2: Service Account JSON (Recommended for Production)

1. **Create a service account:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to IAM & Admin > Service Accounts
   - Create a new service account or use an existing one
   - Create a JSON key for the service account
   - Download the JSON key file

2. **Place the credentials file:**
   - Place the JSON file in the project root directory: `RPG_LLM/credentials.json`
   - **OR** place it in a secure location and set the path in `.env`:
     ```
     GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json
     ```

3. **Update `.env` file:**
   - If using the default location (`credentials.json` in project root), no additional configuration needed
   - If using a custom path, add to `.env`:
     ```
     GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/credentials.json
     ```

## JWT Secret Key

For authentication, you also need a JWT secret key:

1. **Generate a secure secret:**
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Add to `.env` file:**
   ```
   JWT_SECRET_KEY=your-generated-secret-key-here
   ```

## Complete `.env` File Example

Create `RPG_LLM/.env` with:

```bash
# Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key-here

# OR use service account (if not using API key)
# GOOGLE_APPLICATION_CREDENTIALS=./credentials.json

# JWT Authentication
JWT_SECRET_KEY=your-jwt-secret-key-here

# Optional: Database paths (defaults are fine for development)
# DATABASE_URL=sqlite+aiosqlite:///./RPG_LLM_DATA/databases/auth.db

# Optional: Time settings
# JWT_EXPIRATION=24h
# JWT_ALGORITHM=HS256
```

## File Locations Summary

```
RPG_LLM/
├── .env                    # ← Create this file with your credentials
├── credentials.json        # ← Optional: Place GCP service account JSON here
├── .env.example           # Template (do not put real credentials here)
└── ...
```

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` or `credentials.json` to git
- These files are already in `.gitignore`
- Keep your API keys and credentials secure
- For production, use environment variables or a secrets management system

## Verification

After setting up credentials, verify they work:

```bash
# Check if .env file exists and has required variables
cat .env | grep -E "GEMINI_API_KEY|JWT_SECRET_KEY"

# Restart services to load new credentials
docker compose restart
```

## Troubleshooting

If you see warnings about missing credentials:
- Ensure `.env` file exists in the project root
- Check that variable names match exactly (case-sensitive)
- Restart Docker containers after updating `.env`
- For service account: ensure the JSON file path is correct and accessible

