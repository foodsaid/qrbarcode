.PHONY: help install install-dev lock audit test coverage lint format type-check security clean docker-build docker-run docker-stop docs run docker-network docker-deploy docker-redeploy docker-rollback docker-status docker-images docker-prune-dangling

# Default target
.DEFAULT_GOAL := help

# Lock files only take releases at least this old (supply-chain cooldown).
LOCK_COOLDOWN ?= 14 days
# Packages whose only non-vulnerable release is newer than the cooldown.
# Remove an entry once that release is older than LOCK_COOLDOWN.
LOCK_SECURITY_EXCEPTIONS ?= pillow virtualenv filelock certifi
# Locks target Linux (CI, Docker, and Dependabot all resolve for Linux), oldest supported Python.
UV_LOCK = uv pip compile --quiet --python-platform linux --python-version 3.12 --generate-hashes \
	--exclude-newer "$(LOCK_COOLDOWN)" \
	$(foreach p,$(LOCK_SECURITY_EXCEPTIONS),--exclude-newer-package "$(p)=false") \
	--custom-compile-command "make lock"

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies (hash-pinned)
	pip install --require-hashes -r requirements.txt

install-dev: ## Install development dependencies (hash-pinned)
	pip install --require-hashes -r requirements-dev.txt
	pre-commit install

lock: ## Regenerate hash-pinned requirements*.txt from requirements*.in (needs uv)
	$(UV_LOCK) requirements.in -o requirements.txt
	$(UV_LOCK) requirements-dev.in -o requirements-dev.txt

audit: ## Check locked dependencies for known vulnerabilities
	pip-audit --strict --require-hashes --disable-pip -r requirements.txt
	pip-audit --strict --require-hashes --disable-pip -r requirements-dev.txt

test: ## Run tests
	pytest

test-verbose: ## Run tests with verbose output
	pytest -v

coverage: ## Run tests with coverage report
	pytest --cov=main --cov-report=term --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

lint: ## Run linting checks
	flake8 main.py tests/
	@echo "✓ Linting passed"

format: ## Format code with black
	black main.py tests/
	isort main.py tests/
	@echo "✓ Code formatted"

format-check: ## Check code formatting without modifying
	black --check main.py tests/
	isort --check main.py tests/

type-check: ## Run type checking with mypy
	mypy main.py --ignore-missing-imports

security: ## Run security checks
	bandit -r main.py
	$(MAKE) audit

qa: lint type-check security test ## Run all quality assurance checks

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	@echo "✓ Cleaned up generated files"

docker-build: ## Build Docker image
	docker build -t qr-service:latest .
	@echo "✓ Docker image built successfully"

docker-run: ## Run Docker container
	./run_local.sh

docker-stop: ## Stop Docker container
	docker stop qr-service-local 2>/dev/null || true
	docker rm qr-service-local 2>/dev/null || true
	@echo "✓ Docker container stopped"

docker-compose-up: ## Start services with docker-compose
	docker-compose up -d
	@echo "✓ Services started with docker-compose"

docker-compose-down: ## Stop services with docker-compose
	docker-compose down
	@echo "✓ Services stopped with docker-compose"

docker-logs: ## View Docker container logs
	docker logs -f qr-service-local

docker-network: ## Ensure external docker network exists (qrnetwork)
	docker network inspect qrnetwork >/dev/null 2>&1 || docker network create qrnetwork
	@echo "✓ Docker network qrnetwork is ready"

docker-deploy: docker-network ## Build versioned image, tag stable, and deploy with compose
	./scripts/deploy_local.sh deploy

docker-redeploy: docker-network ## Recreate container from current stable image
	./scripts/deploy_local.sh redeploy

docker-rollback: docker-network ## Rollback to specific image tag (usage: make docker-rollback TAG=20260406-120000)
	@if [ -z "$(TAG)" ]; then echo "Error: TAG is required. Example: make docker-rollback TAG=20260406-120000"; exit 1; fi
	./scripts/deploy_local.sh rollback $(TAG)

docker-status: ## Show running container and image/tag status
	./scripts/deploy_local.sh status

docker-images: ## List service images by creation time
	./scripts/deploy_local.sh images

docker-prune-dangling: ## Remove only dangling images (safe cleanup)
	./scripts/deploy_local.sh cleanup-dangling

docs: ## Open API documentation in browser
	@echo "Starting service and opening documentation..."
	@echo "API docs will be available at http://localhost:8080/docs"
	python main.py

run: ## Run the application locally
	python main.py

run-dev: ## Run the application in development mode
	DEBUG=true python main.py

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

update-deps: ## List outdated packages (bump them in requirements*.in, then run `make lock`)
	pip list --outdated

venv: ## Create virtual environment
	python3 -m venv venv
	@echo "✓ Virtual environment created. Activate with 'source venv/bin/activate'"

init: venv install-dev ## Initialize development environment
	@echo "✓ Development environment initialized"
	@echo "Activate with: source venv/bin/activate"

ci: format-check lint type-check security test ## Run CI pipeline locally
	@echo "✓ All CI checks passed"

release: qa docker-build ## Prepare for release (QA + Docker build)
	@echo "✓ Release preparation complete"

all: clean install-dev qa docker-build ## Run everything (clean, install, qa, docker build)
	@echo "✓ All tasks completed successfully"
