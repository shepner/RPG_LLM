FROM python:3.11-slim

WORKDIR /app

# Copy service-specific files
COPY services/time_management/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/time_management/src/ ./src/

ENV PYTHONPATH=/app

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8003"]

