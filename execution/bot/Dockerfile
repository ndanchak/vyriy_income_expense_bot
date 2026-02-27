FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser

# Copy application code
COPY . .

# Switch to non-root user
USER appuser

# Tell Railway which port to route traffic to
EXPOSE 8080

# Railway sets PORT automatically; default to 8080 if not set
CMD uvicorn main:api --host 0.0.0.0 --port ${PORT:-8080}
