# Deploying Dialectic

How the live copies are set up, and the commands for everything we do to them. The plan and reasoning are in `SPEC.md` §9; this file is the how-to. The scripts and config live in `deploy/`.

## What's running

One DigitalOcean droplet (2 GB, Ubuntu 24.04) just for the hackathon, separate from Owen's other server. Ask Owen for its IP; SSH is `ssh root@<droplet-ip>` with his key. It runs **three copies** of the app, each with its own database, uploads, `.env` and budget. Demo and sandbox run the `stable` branch; dev runs `main`:

| Copy | URL | Who it's for | Checkout | Port | Service | Limits (`.env`) |
| --- | --- | --- | --- | --- | --- | --- |
| **demo** | `https://dialectic.yaggy.dev` | Spare: a clean copy we keep reset, and switch the public link to if the sandbox breaks | `/srv/dialectic-demo` | 8000 | `dialectic@demo` | AI $10, search $3, no device limit |
| **sandbox** | `https://dialectic-sandbox.yaggy.dev` (also `dialectic.space`) | Everyone: judges and participants, via the slide's link `yag.gy/dia` | `/srv/dialectic-sandbox` | 8001 | `dialectic@sandbox` | AI $12, search $4, 10 paid Asks/device/hour |
| **dev** | `https://dialectic-dev.yaggy.dev` (also `dev.dialectic.space`) | Teammates trying the newest work and reporting problems; may be briefly broken | `/srv/dialectic-dev` | 8002 | `dialectic@dev` | AI $3, search $1, no device limit |

How a request gets there: browser → **Cloudflare** (DNS for both domains is proxied, and Cloudflare serves the public HTTPS certificate) → **Caddy** on the droplet (`/etc/caddy/Caddyfile`, from `deploy/Caddyfile`) → the copy's **uvicorn** process on `127.0.0.1:<port>`, run by systemd from `deploy/dialectic@.service` as the `dialectic` user. FastAPI serves both the API and the built frontend (`app/frontend/dist`).

The `.env` files on the droplet hold the API keys and each copy's limits. They are never in git; `.env.example` lists the variables.

## The dev copy deploys itself

Every minute, a timer on the droplet (`dialectic-autodeploy.timer`) checks GitHub. When `main` has new commits, it updates the dev copy: `uv sync`, builds the frontend beside the live one and swaps it in, reseeds the dev database if `db.py` or `seed.py` changed (keeping `web_cache` and `spend`), restarts `dialectic@dev` and checks it answers. **Push to `main`, and about a minute later (plus ~30 s to build) it's on `https://dialectic-dev.yaggy.dev`.**

- **Which commit is live:** `https://dialectic-dev.yaggy.dev/version.txt`.
- **If a deploy fails** (a dependency or the build breaks), dev keeps running the previous version, and that commit isn't retried until the next push. See why: `ssh root@IP "journalctl -u dialectic-autodeploy -n 30 --no-pager -o cat"`.
- **Pause it:** `ssh root@IP "systemctl stop dialectic-autodeploy.timer"` (`start` to resume).
- **Change it:** the script is a fixed copy in `/usr/local/sbin/dialectic-autodeploy-dev`, not run from the checkout, so pushes can't change what runs as root. After editing `deploy/autodeploy-dev.sh` or its unit files: `scp deploy/autodeploy-dev.sh deploy/dialectic-autodeploy.* root@IP:/tmp/`, then `ssh root@IP "install -m 755 /tmp/autodeploy-dev.sh /usr/local/sbin/dialectic-autodeploy-dev && cp /tmp/dialectic-autodeploy.* /etc/systemd/system/ && systemctl daemon-reload"`.

## The public link: `yag.gy/dia`

Judges and the audience see the same presentation: one slide with the video and one link, **`https://yag.gy/dia`**. It's a **302** redirect (Cloudflare redirect rule on `yag.gy`, above the catch-all) to the **sandbox**, `https://dialectic-sandbox.yaggy.dev`. The clean, curated demo is the video; the live link is for poking around, so other people's notes in it are fine.

- **302, not 301**, so browsers don't remember it and we can repoint it.
- **If the sandbox breaks or gets messed up:** change the rule's target to `https://dialectic.yaggy.dev` (the demo copy, kept reset). The slide doesn't change.
- Don't put `dialectic.space` on the slide: campus wifi blocks it (`LOG.md`, 10:56 Sat).

Only dev does this. The demo and sandbox copies change only when a person promotes `main` to `stable` and runs `update.sh`.

## Everyday tasks

Run these from the repo root on your machine. `IP` stands for the droplet's IP.

### Deploy a new version

The droplet only ever runs `stable`, so first promote (a person's call, after clicking through the demo path; see `CLAUDE.md`, *Branches*):

```sh
git push origin main:stable
git tag good-$(date +%H%M) main && git push origin --tags
ssh root@IP 'bash -s' < deploy/update.sh            # both copies
ssh root@IP 'bash -s -- sandbox' < deploy/update.sh  # just one
```

To put the newest `main` on the dev copy (no promotion needed): `ssh root@IP 'bash -s -- dev' < deploy/update.sh`.

`update.sh` pulls `stable` (or `main`, for dev), runs `uv sync`, rebuilds the frontend, restarts the service and prints `active` for each copy. It never touches the databases.

### Roll back

Never rewrite `stable`. To run an earlier known-good version on the droplet:

```sh
ssh root@IP "sudo -u dialectic git -C /srv/dialectic-demo checkout good-0531 && systemctl restart dialectic@demo"
```

(Rebuild the frontend too if it changed: run the `npm ci && npm run build` step from `update.sh` by hand.) Then fix on `main`, promote, and run `update.sh`, which puts the copy back on `stable`.

### Reset a copy to the demo starting state

```sh
ssh root@IP "sudo -u dialectic bash -c 'cd /srv/dialectic-demo/app/backend && ~/.local/bin/uv run --env-file ../../.env seed.py --reset --with-reading' && systemctl restart dialectic@demo"
```

`--reset` keeps `web_cache` (rehearsed answers) and the `spend` table (so budgets aren't reset). Leave out `--with-reading` to start with no reading, if the professor will upload it live in demo step 1.

### Before submitting

1. **Reset the sandbox** (the command above with `sandbox` in place of `demo` in both places) and check its budget (*Check spending*): it's what `yag.gy/dia` opens.
2. Check `https://yag.gy/dia` lands on the sandbox.

### Keeping the spare ready (demo copy)

1. Reset it (above).
2. **Rehearse each demo question once** on `https://dialectic.yaggy.dev` and read the answer: what plays on stage is the cached one (`TODO.md`).
3. Back up the database: `ssh root@IP "cp /srv/dialectic-demo/app/backend/dialectic.db /root/demo-$(date +%H%M).db"`.
4. **Laptop backup:** run `stable` locally with a copy of that database (`scp root@IP:/srv/dialectic-demo/app/backend/dialectic.db app/backend/`), then follow `README.md` *Running it*, in case the venue wifi or the droplet fails during our slot.

### Check spending

```sh
curl -s https://dialectic-sandbox.yaggy.dev/api/spend   # dialectic.space is blocked on campus
curl -s https://dialectic.yaggy.dev/api/spend
```

Each shows money spent per service against that copy's budget. Past its budget a copy blocks AI with a notice; classmates' answers and the library keep working.

### Emergency stop (no more AI spending on a copy)

```sh
ssh root@IP "sed -i 's/^AI_OFF=.*/AI_OFF=1/' /srv/dialectic-sandbox/.env && systemctl restart dialectic@sandbox"
```

Set it back to `0` the same way. Change budgets or the device limit by editing the same `.env` and restarting.

### Logs and status

```sh
ssh root@IP "journalctl -u dialectic@sandbox -f"            # live log
ssh root@IP "systemctl status dialectic@demo dialectic@sandbox caddy --no-pager"
```

### Change the Caddy config or the service file

Edit `deploy/Caddyfile` or `deploy/dialectic@.service`, commit, then:

```sh
scp deploy/Caddyfile deploy/dialectic@.service root@IP:/tmp/
ssh root@IP "cp /tmp/Caddyfile /etc/caddy/ && cp /tmp/dialectic@.service /etc/systemd/system/ && systemctl daemon-reload && systemctl reload caddy && systemctl restart dialectic@demo dialectic@sandbox"
```

## Cloudflare

**Swarthmore's campus DNS blocks `dialectic.space`** (it answers with `malware.swarthmore.edu`, probably because the domain is newly registered), so on campus wifi only the `yaggy.dev` names work. Share those; the `dialectic.space` names stay as aliases for when the block lifts.

Both hostnames are proxied by Cloudflare (orange cloud). Cloudflare serves the public certificate; Caddy accepts both plain HTTP and HTTPS with its own internal certificate, so it works with Cloudflare SSL mode **Flexible** or **Full**.

- **`yaggy.dev` is in Full (strict)**, so `dialectic.yaggy.dev` has its own **Configuration Rule** (Rules → Configuration Rules, "dialectic full ssl": hostname is one of `dialectic.yaggy.dev`, `dialectic-sandbox.yaggy.dev`, `dialectic-dev.yaggy.dev` → SSL **Full**). Delete the rule when the droplet goes. `dialectic.space` needs nothing.
- **Error 526** means the zone is in **Full (strict)**, which rejects Caddy's internal certificate. Either add a Cloudflare **Configuration Rule** for that hostname setting SSL to **Full**, or switch the record to **DNS only** (grey cloud) and replace that host's block in the Caddyfile with a plain `dialectic.yaggy.dev { reverse_proxy 127.0.0.1:8000 }` so Caddy gets a real Let's Encrypt certificate.
- The Ask streams its answer (server-sent events); it was checked through Cloudflare and arrives stage by stage. Cloudflare cuts requests at 100 s; a fresh Ask takes 20–35 s.

## Setting up a droplet from scratch

Only needed for a new droplet (2 GB Ubuntu 24.04, your SSH key, A records for both hosts pointing at it):

```sh
scp deploy/Caddyfile deploy/dialectic@.service root@IP:/tmp/
ssh root@IP 'bash -s' < deploy/setup-droplet.sh
```

That adds swap, installs Node 22, Caddy and uv, opens the firewall for SSH/HTTP/HTTPS, creates the `dialectic` user, clones `stable` into both checkouts and enables the services. Then install each copy's `.env` (keys plus its limits from the table above, mode 600, owned by `dialectic`) at `/srv/dialectic-<copy>/.env`, run `update.sh`, and reset both copies with `--with-reading`.
