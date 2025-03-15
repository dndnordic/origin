FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Make sure scripts are executable
RUN chmod +x /app/src/api/governance_api.py \
    /app/src/governance/governance_manager.py \
    /app/src/governance/yubikey_auth.py \
    /app/src/database/immutable_db_manager.py \
    /app/src/database/event_store_manager.py \
    /app/src/database/triple_store_manager.py

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV GOVERNANCE_API_PORT=8000

# Expose port
EXPOSE 8000

# Run the governance API
CMD ["python", "-m", "src.api.governance_api"]