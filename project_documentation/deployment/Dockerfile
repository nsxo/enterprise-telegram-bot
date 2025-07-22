
# deployment/Dockerfile

# --- Stage 1: Build Stage ---
# Use an official Python runtime as a parent image
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed by Python packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Stage ---
FROM python:3.11-slim as final

# Set the working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application code
COPY src/ ./src
COPY scripts/ ./scripts

# Make sure the app runs as a non-root user for security
RUN useradd --create-home appuser
USER appuser

# Set the path to include the virtual environment's binaries
ENV PATH="/opt/venv/bin:$PATH"

# Expose the port the app runs on
EXPOSE 8000

# Command to run your application using Gunicorn
# Using multiple workers for better performance under load.
# The number of workers is typically (2 * number_of_cores) + 1.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "src.webhook_server:app"]
