# FireLens app container (Render). Slim runtime; the read-only DuckDB serving DB is
# REBUILT from committed data/ in the build step (the .duckdb binary is gitignored).
FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching.
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

# App + data + pipeline builder + docs (agent reads docs/AGENT.md at runtime).
COPY . .

# Generate firelens.duckdb from data/*.parquet (reproducible from committed inputs alone).
RUN python prep/build_duckdb.py

EXPOSE 8000
# Render injects $PORT; default 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
