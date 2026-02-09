.PHONY: run-p1 test-core setup

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt && pip install -e packages/core

run-p1:
	uvicorn apps.p1_diligence_analyst.diligence_analyst.main:app --reload

test-core:
	python -m pytest packages/core apps/p1_diligence_analyst

