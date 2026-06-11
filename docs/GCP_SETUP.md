# GCP / Gemini setup

Two paths; both use the exact model id `gemini-3.5-flash` (configured via `CLEO_MODEL`).

## Path A — Google AI Studio API key (fastest; recommended for the demo)

1. https://aistudio.google.com → Get API key → create key in your GCP project (the project
   with hackathon credits).
2. `.env`:
   ```
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   GOOGLE_API_KEY=<your key>
   CLEO_MODEL=gemini-3.5-flash
   ```
3. Verify: `uv run python scripts/live_smoke.py` (checks model ping, MCP boot, GitHub MCP if
   configured, then one full triage run with a printed event trace).

## Path B — Vertex AI (uses project credits directly)

1. `gcloud auth application-default login`
2. Enable: `gcloud services enable aiplatform.googleapis.com`
3. `.env`:
   ```
   GOOGLE_GENAI_USE_VERTEXAI=TRUE
   GOOGLE_CLOUD_PROJECT=<project-id>
   GOOGLE_CLOUD_LOCATION=us-central1
   CLEO_MODEL=gemini-3.5-flash
   ```

## GitHub connector (real external MCP)

1. Create a **fine-grained PAT** scoped to ONE demo repo with Issues read/write.
2. `.env`: `GITHUB_TOKEN=<pat>`, `GITHUB_DEMO_REPO=<owner>/<repo>`.

## Deploy to Cloud Run (optional for judging; local demo is primary)

```bash
gcloud run deploy cleo --source . \
  --region us-central1 --project <project-id> \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=<project-id>,GOOGLE_CLOUD_LOCATION=us-central1,CLEO_MODEL=gemini-3.5-flash"
```
The Dockerfile builds the SPA into `web/dist` and serves everything from one container
(FastAPI :8080). SQLite state on Cloud Run is per-instance/ephemeral — fine for a demo;
re-seed on boot via `SEED_ON_BOOT=1`.

## Cost guardrails

gemini-3.5-flash is the efficiency tier; a full triage run over the 90-item corpus is a few
hundred K tokens at most. Keep `max_iterations=3` on the watch loop. Watch usage at
https://aistudio.google.com/usage or the Vertex dashboard.
