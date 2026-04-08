.PHONY: help install install-dev run-p1 test lint format docker-build docker-run clean

PYTHON      = python3
VENV        = .venv
PIP         = $(VENV)/bin/pip
UVICORN     = $(VENV)/bin/uvicorn
PYTEST      = $(VENV)/bin/pytest
RUFF        = $(VENV)/bin/ruff

APP_MODULE  = diligence_analyst.main:app
APP_DIR     = apps/p1_diligence_analyst
CORE_DIR    = packages/core
IMAGE_NAME  = diligence-analyst


help:
	@echo ""
	@echo "  install       Create venv and install core + app packages"
	@echo "  install-dev   Same as install + dev/test dependencies"
	@echo "  run-p1        Run the FastAPI app locally with hot-reload"
	@echo "  test          Run all tests"
	@echo "  lint          Lint with ruff"
	@echo "  format        Format with ruff"
	@echo "  docker-build  Build the Docker image"
	@echo "  docker-run    Run the Docker image locally"
	@echo "  clean         Remove venv, caches, build artifacts"
	@echo ""


$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/activate
	$(PIP) install --upgrade pip
	$(PIP) install -e $(CORE_DIR)
	$(PIP) install -e $(APP_DIR)
	$(PIP) install python-dotenv ruff

install-dev: install
	$(PIP) install pytest pytest-cov pytest-asyncio httpx


run-p1: install
	cd $(APP_DIR) && ../../$(UVICORN) $(APP_MODULE) \
		--reload \
		--host 0.0.0.0 \
		--port 8000


test: install-dev
	$(PYTEST) $(APP_DIR)/tests $(CORE_DIR)/tests -v --tb=short


lint: install
	$(RUFF) check apps/ packages/ scripts/

format: install
	$(RUFF) format apps/ packages/ scripts/


docker-build:
	docker build -t $(IMAGE_NAME) .

docker-run:
	docker run --env-file apps/p1_diligence_analyst/.env \
		-p 8000:8000 $(IMAGE_NAME)


clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info"  -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleaned."