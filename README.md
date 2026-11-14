# Dialectic

A collaborative reading platform for college courses. Students annotate course texts together and ask questions about hard passages. Answers come from their peers first, then from AI, but only in the ways the class's charter allows.

- **What we're building and why:** [`SPEC.md`](SPEC.md)
- **How we work** (logging, commits, branches; written for agents, useful for people): [`CLAUDE.md`](CLAUDE.md)
- **What's happened so far:** [`LOG.md`](LOG.md)
- **Deploying, and the live copies:** [`DEPLOY.md`](DEPLOY.md)

## Development

### One-time setup

1. **Install uv**, which manages Python and the backend's packages. You don't need to install Python yourself: uv downloads the right version (3.12).
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`)
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

   Then open a new terminal and check that `uv --version` works.
2. **Install Node.js** (the current LTS) for the frontend, from <https://nodejs.org> or your package manager.
3. **Clone and configure:**
   ```sh
   git clone git@github.com:Ramen3ater1/tri-co_hack_2026.git
   cd tri-co_hack_2026
   cp .env.example .env    # then fill in the keys; ask in the team chat
   ```
   `.env` is gitignored. Never commit it or paste keys into code.
4. **Install the backend's packages:**
   ```sh
   cd app/backend
   uv sync
   ```

### Running it

Backend (from `app/backend`):

```sh
uv run seed.py --reset                                      # fresh demo database
uv run --env-file ../../.env uvicorn main:app --reload --port 8000
```

Frontend (from `app/frontend`, once it exists):

```sh
npm install
npm run dev
```

### Python packages

Use uv, never `pip install`:

- **Add a package:** `uv add <package>` (from `app/backend`), then commit both `pyproject.toml` and `uv.lock`.
- **After pulling** someone else's change to either file, run `uv sync`.
- **Run a script:** `uv run <script>.py`. It uses the project's environment, with no activating needed.

### Working with Claude

Open Claude Code at the repo root; it reads `CLAUDE.md` and follows the team's rules. To change the spec without writing Markdown, describe the change in plain English and Claude edits `SPEC.md`, then commits and pushes it.

### Branches

- **`main`:** everyone works here and pushes small changes often. It may be briefly broken.
- **`stable`:** the best version we could submit right now. A person promotes `main` to it after checking the demo path works. The live site and the submission come from `stable`.
