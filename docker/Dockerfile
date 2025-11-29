FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/
COPY nodes.json .
COPY messages.json .

# Copy entrypoint script and set permissions
COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8001

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
