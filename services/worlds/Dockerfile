FROM python:3.11-slim

WORKDIR /app

# Copy shared modules first
COPY shared/ ./shared/

# Copy service-specific files
COPY services/worlds/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/worlds/src/ ./src/

ENV PYTHONPATH=/app

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8004"]

