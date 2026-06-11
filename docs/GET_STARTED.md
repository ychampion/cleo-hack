# Run Cleo on your company in 15 minutes

This guide points Cleo at **your** GitHub repo and **your** documents — not the demo corpus.
You end with a live agent that triages your real feedback, proposes evidence-backed bets,
escalates urgent churn risks to your repo, and writes your weekly product brief.

## 1. Prerequisites (2 min)

- **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/)
- **Node.js** (for `npx` — the filesystem MCP connector that reads your documents)
- **bun** (only for the web UI)
- A **Google AI Studio API key** ([aistudio.google.com](https://aistudio.google.com) → Get API key).
  Free-tier keys are heavily rate-limited; a paid-tier key completes a full run in under a
  minute — see [GCP_SETUP.md](GCP_SETUP.md).
- *(Optional, recommended)* A **GitHub fine-grained PAT** with Issues read/write on the one
  repo you want Cleo to operate on.

## 2. Clone + install (2 min)

```bash
git clone <this repo> cleo && cd cleo
uv sync
cd web && bun install && bun run build && cd ..   # or `bun run dev` later for live dev
```

## 3. Configure (5 min)

**Secrets go in `.env`:**

```bash
cp .env.example .env
```

Edit `.env`: set `GOOGLE_API_KEY`, and (optionally) `GITHUB_TOKEN`.
**Important:** delete or comment out the `CORPUS_DIR=seed/corpus` line — environment
variables win over the config file, and you're about to configure your own folders.

**Your workspace goes in `cleo.config.json`:**

```bash
cp cleo.config.example.json cleo.config.json
```

```json
{
  "workspace_name": "Acme",
  "github_repo": "acme/acme-app",
  "corpus_dirs": ["../acme-notes/calls", "../acme-notes/support"],
  "model": "gemini-3.5-flash"
}
```

- `github_repo` — the repo Cleo ingests open issues from and escalates urgent issues to.
- `corpus_dirs` — one or more folders of your documents. Relative paths resolve against the
  repo root; absolute paths work too. **What to drop in:** call transcripts, meeting notes,
  support summaries, NPS write-ups — plain `.md` files (any folder layout; subfolders are
  read too). If you can export chat/ticket data in the demo's JSON shapes
  (`slack-export.json` / `tickets.json`, see `seed/corpus/`), put them in a folder, set
  `CORPUS_DIR` to it, and run `uv run python -m seed.seed` to bulk-import them.

Precedence everywhere: **env vars > `cleo.config.json` > defaults** (see `app/config.py`).

*(Optional)* Kick the tires with the built-in demo first: `uv run python -m seed.seed`
loads ~90 realistic feedback items from `seed/corpus`. Skip this for a clean real workspace.

## 4. Write your first directives (2 min)

Start the app (next step), open **Directives**, and add your standing intent. Two examples:

> Triage all new feedback daily: cluster it into themes, tag urgency and sentiment, and
> **escalate** urgent churn risks as GitHub issues in `acme/acme-app` with evidence links.

> Keep the weekly product brief current; rewrite it whenever themes or priorities change
> materially.

Directives are how you steer Cleo — declarative intent, not scripts. Note: GitHub writes are
guard-railed; they only execute when an **active directive containing "escalate"** exists and
the target matches your configured repo. No directive, no writes.

## 5. Run the agent (1 min)

```bash
uv run uvicorn app.main:app --port 8080
```

Open `http://localhost:8080` (or `http://localhost:5173` with `bun run dev`), go to
**Agent**, and click **Run triage**. Headless alternative: `cleo triage` from the CLI
(see [CLI.md](CLI.md)).

## 6. What you'll see (3 min)

Watch the live trace: ingestors pull your GitHub issues and your documents **in parallel**
over MCP, then the pipeline synthesizes, prioritizes, and acts.

- **Inbox** — every raw feedback item, deduplicated, by source.
- **Themes** — clustered topics with urgency, trend, and the contradictions it caught.
- **Bets** — proposed product bets with impact / effort / confidence, each linked to the raw
  evidence that justifies it.
- **Actions** — the auditable ledger: every autonomous act (GitHub issue filed, brief
  written) with rationale and evidence ids; blocked writes show up too.
- **Brief** — your weekly product brief, kept current.

Re-running is safe: ingestion dedupes on (source, external_id), so Cleo only processes
what's new.

## 7. Other tools can connect

The feedback store is a standard MCP server — Claude Code, Cursor, Gemini CLI, or your own
agent can read and operate the same workspace with copy-paste configs:
[CONNECT_ANY_AGENT.md](CONNECT_ANY_AGENT.md).

## 8. Honest current limits

- **Sources:** live connectors exist for GitHub issues and local files. Slack, Intercom,
  Zoom, etc. don't stream in yet — they arrive as drop-in exports you place in
  `corpus_dirs` (`.md` files, or the demo JSON shapes via the seeder).
- **Single workspace, single user.** No multi-tenancy, no auth — the MCP server and API
  bind localhost and trust whoever reaches them. Don't expose them on a network.
- **Rate limits:** a free-tier Gemini key will stall a full pipeline run; use a paid-tier
  key for real workloads ([GCP_SETUP.md](GCP_SETUP.md)).
- **GitHub writes** target only your one configured repo, by design.
