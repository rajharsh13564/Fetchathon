.PHONY: help install test run-backend run-frontend run-agents clean lint typecheck

help:
	@echo "FinancePilot AI - Available commands:"
	@echo "  make install       - Install Python dependencies"
	@echo "  make test          - Run test suite"
	@echo "  make run-backend   - Start FastAPI backend"
	@echo "  make run-frontend  - Start React frontend"
	@echo "  make run-agents    - Start all uAgents (requires 4 terminals)"
	@echo "  make run-all       - Start backend and frontend"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make lint          - Run ruff linter"
	@echo "  make typecheck     - Run mypy type checker"

install:
	pip install -r requirements.txt
	cd frontend && npm install

test:
	pytest tests/ -v

run-backend:
	python -m backend.main

run-frontend:
	cd frontend && npm run dev

run-orchestrator:
	python -m agents.orchestrator.agent

run-quant-screener:
	python -m agents.quant_screener.agent

run-risk-manager:
	python -m agents.risk_manager.agent

run-deep-researcher:
	python -m agents.deep_researcher.agent

run-agents:
	@echo "Start each agent in a separate terminal:"
	@echo "  make run-orchestrator"
	@echo "  make run-quant-screener"
	@echo "  make run-risk-manager"
	@echo "  make run-deep-researcher"

run-all:
	@echo "Starting backend and frontend..."
	@echo "Run 'make run-backend' in one terminal and 'make run-frontend' in another"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage dist build *.egg-info
	cd frontend && rm -rf node_modules dist 2>/dev/null || true

lint:
	ruff check .

typecheck:
	mypy .