#!/usr/bin/env bash
# Keeps the dev copy on the newest `main`. Run every minute by dialectic-autodeploy.timer.
# Installed as a fixed copy in /usr/local/sbin (see DEPLOY.md), never run from the checkout,
# so a push to main can't change what runs as root. Logs: journalctl -u dialectic-autodeploy
set -euo pipefail
exec 9>/run/dialectic-autodeploy.lock
flock -n 9 || exit 0  # a deploy is still running

DIR=/srv/dialectic-dev
STATE=/var/lib/dialectic-autodeploy
mkdir -p "$STATE"
as_app() { sudo -u dialectic bash -c "set -euo pipefail; cd $DIR; $1"; }

as_app "git fetch -q origin main"
old=$(as_app "git rev-parse HEAD")
new=$(as_app "git rev-parse origin/main")
[ "$old" = "$new" ] && exit 0
# Don't retry a commit that already failed to build every minute; the next push gets a new try.
[ "$(cat "$STATE/failed" 2>/dev/null)" = "$new" ] && exit 0

echo "deploying ${new:0:7} (was ${old:0:7})"
fail() { echo "FAILED at ${new:0:7}: $1; dev keeps running ${old:0:7}"; echo "$new" > "$STATE/failed"; exit 1; }

as_app "git checkout -q main && git merge -q --ff-only origin/main" || fail "git"
as_app "cd app/backend && ~/.local/bin/uv sync -q" || { as_app "git checkout -q $old"; fail "uv sync"; }
# Build beside the live files, then swap, so a failed build never leaves the site empty.
as_app "cd app/frontend && npm ci --silent && npx vite build --outDir dist-next --emptyOutDir >/dev/null && git rev-parse --short HEAD > dist-next/version.txt" \
  || { as_app "git checkout -q $old"; fail "frontend build"; }
as_app "cd app/frontend && rm -rf dist-old && { [ -d dist ] && mv dist dist-old || true; } && mv dist-next dist"

# The app only creates missing tables; a changed schema or seed needs a fresh dev database
# (seed --reset keeps web_cache and spend).
if as_app "git diff --quiet $old $new -- app/backend/db.py app/backend/seed.py"; then :; else
  echo "schema or seed changed: reseeding dev"
  as_app "cd app/backend && ~/.local/bin/uv run --env-file ../../.env seed.py --reset --with-reading" || fail "reseed"
fi

systemctl restart dialectic@dev
for i in $(seq 20); do curl -sf -o /dev/null http://127.0.0.1:8002/api/spend && break; sleep 1; done
curl -sf -o /dev/null http://127.0.0.1:8002/api/spend || fail "server didn't come back up (check journalctl -u dialectic@dev)"
rm -f "$STATE/failed"
echo "deployed ${new:0:7}"
