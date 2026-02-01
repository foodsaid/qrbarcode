.PHONY: help install install-dev test coverage lint format type-check security clean docker-build docker-run docker-stop docs run

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: install ## Install development dependencies
	pip install -r requirements-dev.txt
	pre-commit install

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
	safety check

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

update-deps: ## Update dependencies to latest versions
	pip list --outdated
	@echo "Run 'pip install --upgrade <package>' to update specific packages"

freeze: ## Freeze current dependencies
	pip freeze > requirements-frozen.txt
	@echo "✓ Dependencies frozen to requirements-frozen.txt"

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
