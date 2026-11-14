# Dialectic

A collaborative reading platform for college courses. Students annotate course texts together and ask questions about hard passages. Answers come from their peers first, then from AI, but only in the ways the class's charter allows.

## Testing: try it, report problems, see fixes

How the team tries Dialectic and gets things changed. No setup needed beyond a GitHub account.

### 1. Open the web app

**https://dialectic-dev.yaggy.dev** runs the newest work (`main`), so it can occasionally break. Log in as anyone; there are no passwords:

| Log in as | To try |
| --- | --- |
| **Prof. Rivera** (professor) | Upload a reading, edit the charter (rules, permissible sources, AI switches), see every note |
| **Ana**, **Ben** (students) | Annotate; see classmates' notes unlock once you note or ask nearby; select a passage → **Ask** |
| **Sam** (a past student) | Notes shared from last year's class |

A good first run is the demo path: as Ben, open the reading, write a note near the locked card on page 3, then select the double-consciousness passage and ask where the idea comes from. Then, as Prof. Rivera, turn off "AI may write explanations" on the Charter page and ask again.

Use the `yaggy.dev` addresses: campus wifi blocks `dialectic.space`. Don't test on the judges' copy (`dialectic.yaggy.dev`); see [`DEPLOY.md`](DEPLOY.md) for all three copies.

### 2. Optional: get the Mac app

The Mac app (macOS 14+) lets you ask about or annotate a passage from wherever you read it (Preview, Notability), with hotkeys: **⌥⇧D** ask, **⌥⇧N** note, **⌥⇧H** show classmates' highlights.

1. Open **[Actions → Mac app](https://github.com/Ramen3ater1/tri-co_hack_2026/actions/workflows/mac-app.yml)**, click the newest run with a green tick, and download **Dialectic-dev-mac** at the bottom of the page.
2. Unzip it and move `Dialectic.app` somewhere (e.g. Applications). The first time, **right-click → Open** (it isn't signed by Apple).
3. In its menu-bar menu, pick who you are, and check **Server → Dev**. Grant **Accessibility** (and **Screen Recording**, for ⌥⇧H) when macOS asks: System Settings → Privacy & Security.

Details, and what each hotkey does: [`app/mac/README.md`](app/mac/README.md).

### 3. Report what you notice

- **Web:** the **Report a problem** button, bottom-right on the dev copy.
- **Mac:** menu-bar menu → **Report a problem…**

Both open a GitHub form with the page, who you're logged in as and your browser or Mac already filled in. Pick a type (broken / don't like it / idea / question), give it a short title, say what happened in plain words, and drag in a screenshot if it helps. **Check [open feedback](https://github.com/Ramen3ater1/tri-co_hack_2026/issues?q=is%3Aopen+label%3Afeedback) first**: if it's already there, add a comment or a 👍 instead.

### 4. How it gets fixed

1. Anyone asks their Claude, in the repo: **"work through the open feedback issues"**. `CLAUDE.md` tells it how: label each one, close duplicates, claim one, fix it on `main` with `Fixes #<n>` (which closes the issue) and comment when it's done. Product questions go to `SPEC.md` §11 for a decision instead.
2. **The dev copy updates itself** about 1–2 minutes after a push to `main`. [`/version.txt`](https://dialectic-dev.yaggy.dev/version.txt) shows which commit it's running. Reload and check the fix.
3. **Mac app changes** are rebuilt on every push (about a minute): download the new build from Actions as in step 2.
4. **The judges' copy changes only when a person promotes** `main` to `stable` after checking the demo path ([`DEPLOY.md`](DEPLOY.md)), so a broken change on dev never reaches the judges by accident.

## Project docs

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
