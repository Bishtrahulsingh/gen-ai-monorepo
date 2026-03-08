# Diligence Analyst

An AI-powered assistant that helps investors quickly identify risks, red flags, and key questions when evaluating startups. The idea is simple: before you invest time or money in a startup, you want a quick, structured way to understand what might be missing — or risky.

---

## What problem does this solve?

Early-stage due diligence is slow and manual:

- Pitch decks make big claims but hide gaps
- Important risks are easy to miss
- Analysts spend hours just getting context

This project aims to faster the first round of diligence by:

- Summarizing a startup's narrative from its own documents
- Highlighting potential red flags grounded strictly in context
- Generating high-signal questions an investor should ask

The goal is to start from a strong, structured baseline — so analysts can focus on complex judgment calls without worrying about building context from scratch.

---

## How it works

When you send a query about a company, the system fetches the most relevant chunks from that company's uploaded documents, feeds them into a two-stage LLM pipeline, and streams the result back in real time.

The first model produces a structured JSON analysis — executive summary, risks, confidence score, open questions. A second "judge" model then reviews and refines that output before it reaches the client. The reason for two stages is simple: it catches low-confidence or poorly-grounded responses before they get surfaced to the analyst.

Everything is grounded strictly in the uploaded context. If the documents don't contain enough information to answer a query, the model says so rather than guessing.

```
User Query
    |
[ FastAPI Streaming Router ]
    |
    |-- Vector Search (Qdrant Cloud)
    |       Filter by company_id, retrieve top 20 chunks
    |
    |-- Stage 1: Analysis LLM (llama-3.1-8b-instant via Groq)
    |       Generates structured JSON: summary, risks, confidence
    |
    |-- Stage 2: Judge LLM (gpt-oss-20b via Groq)
            Reviews and refines, then streams to client via SSE
```

---

## Repository structure

This is a monorepo. The `core` package holds all shared logic — embeddings, chunking, vector DB operations — and is installed as a local editable dependency by the apps.

```
gen-ai-monorepo/
├── apps/
│   └── p1_diligence_analyst/
│       ├── diligence_analyst/
│       │   ├── main.py
│       │   ├── routers/
│       │   │   ├── streamingrouter.py    # SSE streaming endpoint
│       │   │   ├── documentrouter.py     # Document ingestion
│       │   │   └── companyrouter.py      # Company management
│       │   ├── prompts/
│       │   │   └── p1_memo/
│       │   │       ├── system_template_model1.md
│       │   │       ├── system_template_judge.md
│       │   │       └── input_template.md
│       │   └── schemas/
│       └── tests/
│
├── packages/
│   └── core/
│       └── diligence_core/
│           ├── chunkingpipeline/     # PDF reading and chunking
│           ├── embeddings/           # fastembed vector generation
│           ├── vectordb/             # Qdrant client and operations
│           ├── llm/                  # LLMWrapper with fallback chain
│           ├── schemas/              # Shared Pydantic schemas
│           ├── middlewares/          # Logging
│           └── utilities/            # Settings and config
│
├── Makefile
└── pyproject.toml
```

The project uses a monorepo because both layers — core and the analyst app — need to evolve independently but share the same foundation. It avoids duplication, keeps tooling consistent, and makes it straightforward to add a second app down the line without rewriting the embedding or retrieval logic.

---

## Tech stack

- Python 3.11
- FastAPI + Uvicorn
- Groq (llama-3.1-8b-instant, llama-3.3-70b-versatile, gpt-oss-20b, gpt-oss-120b)
- fastembed for local embeddings (no external API needed)
- Qdrant Cloud for vector storage (HNSW index, cosine similarity)
- Server-Sent Events for streaming
- Pydantic v2 for validation
- pydantic-settings for config
- pypdf + httpx for PDF parsing
- pytest for tests
- SQLAlchemy + PostgreSQL (persistence layer, in progress)

---

## RAG pipeline

### Document ingestion

Send a POST request with the document URL and metadata:

```
POST /api/v1/store/document
{
  "company_id": "<uuid>",
  "title": "Apple 10-K 2024",
  "doc_type": "sec_filing",
  "source": "https://..."
}
```

The system fetches the PDF over HTTP, extracts text page by page using pypdf, splits it into overlapping chunks (500 characters with 50 character overlap), generates dense embeddings via fastembed in batches of 100, and upserts to the Qdrant `sec_filings` collection with the `company_id` indexed as a payload field for fast filtering.

### Query and retrieval

```
POST /api/result/stream
{
  "query": "What are the key revenue risks?",
  "company_name": "Apple Inc.",
  "collection_name": "sec_filings",
  "company_id": "<uuid>"
}
```

The query is embedded using the same fastembed model, then Qdrant is searched with a strict filter on `company_id` to keep data isolated per company. The top 20 chunks are retrieved, injected into a structured prompt alongside the query, and passed through the two-stage LLM pipeline. The final output streams back as SSE.

### Streaming response format

```
event:status
data:{"request_id": "...", "state": "start"}

event:delta
data:{"request_id": "...", "text": "Based on the filing..."}

event:status
data:{"request_id": "...", "state": "complete"}
```

---

## Analysis output

The system prompt enforces a strict JSON schema with anti-hallucination rules baked in. If there is not enough context to answer, the model returns a minimal response rather than fabricating analysis.

```json
{
  "executive_summary": "2-4 line investor-grade summary answering the query directly",
  "key_risks": [
    { "risk": "Specific risk grounded in context", "severity": "low | medium | high" }
  ],
  "open_questions": ["Critical unknowns that block decision-making"],
  "confidence": 0.85,
  "summarized_query": "Short restatement of the query",
  "summarized_context_used": ["Key facts extracted from retrieved chunks"]
}
```

Confidence scoring works as follows: 0.9 to 1.0 means strong evidence, 0.6 to 0.8 means moderate support, 0.3 to 0.5 means weak support, and anything below 0.3 means the context is insufficient. When confidence is low, the model skips the `key_risks` and `open_questions` fields entirely rather than filling them with guesses.

---

## LLM fallback chain

If the primary model is unavailable, the `LLMWrapper` automatically tries the next one in the chain:

```
llama-3.1-8b-instant  ->  gpt-oss-20b  ->  llama-3.3-70b-versatile  ->  gpt-oss-120b
```

Concurrency across all LLM calls is controlled via a semaphore (max 10 concurrent requests) to stay within rate limits.

---

## How to run locally

You will need Python 3.11+, a Groq API key, and a Qdrant Cloud account.

```bash
# Clone the repo
git clone https://github.com/Bishtrahulsingh/gen-ai-monorepo.git
cd gen-ai-monorepo

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install the shared core package in editable mode
pip install -e packages/core

# Install the app in editable mode
pip install -e apps/p1_diligence_analyst

# Add your environment variables
cp .env.example .env
# Open .env and fill in your keys

# Start the server
make run-p1
```

Create a `.env` file with the following:

```
GROQ_API_KEY=your_groq_api_key_here
QDRANT_API_KEY=your_qdrant_api_key_here
```

Available make commands:

- `make run-p1` — start the app with hot reload
- `make test-core` — run all tests across core and the app
- `make setup` — create venv and install base dependencies

---

## API endpoints

- `GET /` — welcome check
- `GET /health` — health check
- `POST /api/v1/store/document` — ingest a document into the vector store
- `POST /api/result/stream` — query and stream AI analysis

Interactive docs are available at `http://localhost:8000/docs` once the app is running.

---

## Current status

The core RAG pipeline is working end to end — document ingestion, embedding, vector search, two-stage LLM analysis, and streaming are all functional. A few layers are still being built out:

- Company management and document persistence are stubbed for the demo but not yet wired to a real database
- SEC-aware chunking (parsing Part, Item, and Heading structure from 10-K filings) is planned but the commented-out code in the chunking pipeline shows where this is headed
- Authentication and multi-user support are not yet implemented

---

## Roadmap

- Wire `DocumentOut` to a real Postgres record via SQLAlchemy
- Full CRUD for company entities via the company router
- SEC-structured chunking to parse Part, Item, and Heading fields from 10-K and 10-Q filings for higher-precision retrieval
- Support for web URLs and HTML documents alongside PDFs
- Investor-facing frontend for querying and reviewing analysis

---
