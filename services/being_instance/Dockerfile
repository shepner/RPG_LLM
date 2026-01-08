FROM python:3.11-slim

WORKDIR /app

# Copy shared modules first
COPY shared/ ./shared/

# Copy service-specific files
COPY services/being_instance/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/being_instance/src/ ./src/

ENV PYTHONPATH=/app

# Being instance runs on port 8000 (will be mapped to dynamic port by orchestrator)
CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
