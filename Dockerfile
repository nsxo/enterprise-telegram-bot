# Enterprise Telegram Bot - Multi-Stage Production Dockerfile
# Optimized for production deployment with security and performance

# --- Stage 1: Build Stage ---
FROM python:3.11-slim as builder

WORKDIR /app

# Install build-time dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies into a wheelhouse
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# --- Stage 2: Final Production Stage ---
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --system --create-home --no-log-init appuser

# Copy the pre-built wheels from the builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install dependencies from the local wheels without hitting the network
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy application source code with proper ownership
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser docs/ ./docs/
COPY --chown=appuser:appuser project_documentation/ ./project_documentation/
COPY --chown=appuser:appuser env.template ./env.template
COPY --chown=appuser:appuser test_app.py ./test_app.py

# Create logs directory
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port (Railway provides PORT environment variable)
EXPOSE ${PORT:-8000}

# Command to run the application using Gunicorn production server
# Use environment variables for configuration
CMD ["python", "test_app.py"] 