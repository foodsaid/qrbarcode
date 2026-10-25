# Multi-stage build for optimized image size
FROM python:3.13-slim AS builder

# Install dependencies in builder stage
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final production image
FROM python:3.13-slim

# Python runtime optimizations: unbuffered logs, no .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Upgrade base image pip (security fixes) and create non-root user
RUN pip install --no-cache-dir --upgrade "pip>=26.2" && \
    useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code and gunicorn config
COPY --chown=appuser:appuser main.py gunicorn.conf.py ./
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
