# --- stage 1: build the SPA ---
FROM oven/bun:1 AS webbuild
WORKDIR /build/web
COPY web/package.json ./
COPY web/bun.lock* ./
RUN bun install
COPY web/ .
RUN bun run build

# --- stage 2: runtime (python + node for stdio MCP servers spawned via npx) ---
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
COPY --from=webbuild /build/web/dist ./web/dist
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8080
# Cloud Run state is ephemeral; optionally re-seed the demo corpus on boot
CMD ["sh", "-c", "if [ \"$SEED_ON_BOOT\" = \"1\" ]; then python -m seed.seed; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
