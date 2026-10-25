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

# Drop pip and the ensurepip wheels: unused at runtime, and their vendored packages
# (urllib3, msgpack, setuptools) are the image's only scanner findings.
# Then create the non-root user. No network access: dependencies come from the builder.
RUN python -m pip uninstall --yes --no-input pip && \
    rm -rf /usr/local/lib/python3.13/ensurepip && \
    useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code, gunicorn config and OpenAPI spec
COPY --chown=appuser:appuser main.py codes.py gs1.py gunicorn.conf.py openapi.json ./
COPY --chown=appuser:appuser static ./static
COPY --chown=appuser:appuser LICENSE THIRD_PARTY_NOTICES.md ./

# Set PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user (appuser; numeric so platforms can verify it is not root)
USER 1000:1000

# Expose port
EXPOSE 8080

# Health check (internal port is always 8080; matched by compose PORT env)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()"]

# Run application — gunicorn reads bind/workers/timeout from gunicorn.conf.py
CMD ["gunicorn", "--config", "gunicorn.conf.py", "main:app"]
