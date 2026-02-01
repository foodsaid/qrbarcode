# Multi-stage build for optimized image size
FROM python:3.13-slim AS builder

# Install dependencies in builder stage
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final production image
FROM python:3.13-slim

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser main.py .

# Set PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8080}/health').read()" || exit 1

# Run application with gunicorn
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 30 --access-logfile - --error-logfile - main:app
