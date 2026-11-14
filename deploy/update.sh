#!/usr/bin/env bash
# Deploy the latest `stable` to the demo and sandbox copies (and `main` to dev) (or one: `ssh root@<ip> 'bash -s -- sandbox' < deploy/update.sh`), run as root:
#   ssh root@<ip> 'bash -s' < deploy/update.sh
# Rolling back: see DEPLOY.md. This never touches the databases.
set -euxo pipefail

copies="${*:-demo sandbox}"
for copy in $copies; do
  dir=/srv/dialectic-$copy
  branch=stable
  [ "$copy" = dev ] && branch=main  # dev tracks main; everything else only ever runs stable
  sudo -u dialectic bash -c "
    set -euxo pipefail
    cd $dir
    git fetch --tags origin
    git checkout -q $branch
    git pull -q --ff-only origin $branch
    cd app/backend && ~/.local/bin/uv sync -q
    cd ../frontend && npm ci --silent && npm run build
  "
  systemctl restart dialectic@$copy
done

sleep 3
for copy in $copies; do systemctl is-active dialectic@$copy; done
