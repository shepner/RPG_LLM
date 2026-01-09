FROM python:3.11-slim

WORKDIR /app

# Copy service-specific files
COPY services/mattermost_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mattermost_bot/src/ ./src/
COPY services/mattermost_bot/main.py .
COPY shared/ ./shared/

ENV PYTHONPATH=/app

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]
