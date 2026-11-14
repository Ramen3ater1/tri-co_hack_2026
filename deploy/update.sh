#!/usr/bin/env bash
# Deploy the latest `stable` to both copies (or one: `ssh root@<ip> 'bash -s -- sandbox' < deploy/update.sh`), run as root:
#   ssh root@<ip> 'bash -s' < deploy/update.sh
# Rolling back: see DEPLOY.md. This never touches the databases.
set -euxo pipefail

copies="${*:-demo sandbox}"
for copy in $copies; do
  dir=/srv/dialectic-$copy
  sudo -u dialectic bash -c "
    set -euxo pipefail
    cd $dir
    git fetch --tags origin
    git checkout -q stable
    git pull -q --ff-only origin stable
    cd app/backend && ~/.local/bin/uv sync -q
    cd ../frontend && npm ci --silent && npm run build
  "
  systemctl restart dialectic@$copy
done

sleep 3
for copy in $copies; do systemctl is-active dialectic@$copy; done
