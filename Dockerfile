FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install core package first (shared lib)
COPY packages/core ./packages/core
RUN pip install --no-cache-dir ./packages/core

# Install app package
COPY apps/p1_diligence_analyst ./apps/p1_diligence_analyst
RUN pip install --no-cache-dir ./apps/p1_diligence_analyst

RUN python -c "from fastembed import TextEmbedding; TextEmbedding()"

COPY apps/p1_diligence_analyst/diligence_analyst ./diligence_analyst

EXPOSE 8000

CMD ["uvicorn", "diligence_analyst.main:app", "--host", "0.0.0.0", "--port", "8000"]