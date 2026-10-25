# Multi-stage build for optimized image size.
# Base image is pinned by digest; Dependabot proposes digest updates.
FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS builder

# Install dependencies in builder stage
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user --require-hashes -r requirements.txt

# Final production image
FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962

# Python runtime optimizations: unbuffered logs, no .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user (no network installs here: everything comes from the hash-pinned builder)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code, gunicorn config and OpenAPI spec
COPY --chown=appuser:appuser main.py gunicorn.conf.py openapi.json ./
COPY --chown=appuser:appuser static ./static

# Set PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check (internal port is always 8080; matched by compose PORT env)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()"]

# Run application — gunicorn reads bind/workers/timeout from gunicorn.conf.py
CMD ["gunicorn", "--config", "gunicorn.conf.py", "main:app"]
