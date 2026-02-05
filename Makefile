.PHONY: run-p1 test-core setup

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt && pip install -e packages/core

run-p1:
	uvicorn apps.p1_diligence_analyst.app.main:app --reload

test-core:
	pytest packages/core
