# Due Diligence Analyst

This is an ai-powered assistant that helps investors quickly identify **risks, red flags, and key questions** when evaluating startups.
The idea is simple, before you invest time or money in a startup, you want a quick, structured way to understand what might be missing, or risky.
---

## What problem does this solve?

Early-stage due diligence is slow and manual:

* Pitch decks make big claims but hide gaps
* Important risks are easy to miss
* Analysts spend hours just getting context

This project aims to **faster the first round of diligence** by :

* Summarizing a startup narrative
* Highlighting potential red flags
* Generating high-signal questions an investor should ask.

The goal is to start from a **strong, structured baseline**, that helps analysts to focus more on complex task without worrying about the context.

---

## Repository structure (Monorepo)

```
gen-ai-monorepo/
├── apps/
│   └── p1_diligence_agent/  
│       ├── app/               # FastAPI endpoints
│       ├── tests/             # App-level tests
│       └── main.py
│
├── packages/
│   └── core/                  # Shared, reusable logic
│       ├── core               # FastApi endpoints
│       ├── tests/
│       └── __init__.py
│
└── pyproject.toml
```

### Why we used a monorepo?

* The project contains two different shared directories core and diligence system.
* Shared core logic without duplication
* Consistent tooling, tests, and dependencies
---

## Tech stack (initial)

* Python 3
* FastAPI
* pytest
* Sqlalchemy(postgres)
* Pydantic
---

## Current status

* Current week is utilized to design the monorepo structure. 
* Writing core(basic) for diligence system
* Writing basic diligence system using fastapi
* Implementing basic test for health check.

---

# How to work locally?

These are the following steps should be followed to work locally with this project- 

* clone the repo: `git clone https://github.com/Bishtrahulsingh/gen-ai-monorepo.git`
* create a virtual environment: `python -m venv .venv`
* run the virtual environment : `source .venv/bin/activate`
* Install dependencies: `pip install -r requirements.txt`
* Install dev dependencies:`pip install -r requirements-dev.txt`
* Install the core : `pip install -e packages/core`
* Install the app(editable mode): `pip install -e apps/p1_diligence_analyst`
* Run the app: `make run-p1`
