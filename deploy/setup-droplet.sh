#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 droplet, run as root from your machine:
#   scp deploy/Caddyfile deploy/dialectic@.service root@<ip>:/tmp/
#   ssh root@<ip> 'bash -s' < deploy/setup-droplet.sh
# Then install each copy's .env and run update.sh (see DEPLOY.md).
set -euxo pipefail

REPO=https://github.com/Ramen3ater1/tri-co_hack_2026.git

# Swap: a 2 GB droplet can run short while npm builds the frontend.
if ! swapon --show | grep -q swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update
apt-get install -y git curl debian-keyring debian-archive-keyring apt-transport-https gnupg
# OCR for scanned uploads (SPEC: Scanned PDFs).
apt-get install -y ocrmypdf tesseract-ocr-eng

# Node 22 LTS (NodeSource) for building the frontend.
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

# Caddy (official apt repo).
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
apt-get update
apt-get install -y caddy

# Firewall: SSH and web only.
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# The app runs as its own user, with uv installed for it.
id dialectic >/dev/null 2>&1 || useradd --create-home --shell /bin/bash dialectic
sudo -u dialectic bash -c 'command -v ~/.local/bin/uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh'

# Two copies, each a checkout of `stable` with its own database, uploads and .env.
mkdir -p /etc/dialectic
echo PORT=8000 > /etc/dialectic/demo.port
echo PORT=8001 > /etc/dialectic/sandbox.port
for copy in demo sandbox; do
  dir=/srv/dialectic-$copy
  [ -d "$dir/.git" ] || git clone -b stable "$REPO" "$dir"
  chown -R dialectic:dialectic "$dir"
done

# systemd unit and Caddy config, copied up from your machine (see the top of this file).
cp /tmp/dialectic@.service /etc/systemd/system/
cp /tmp/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable dialectic@demo dialectic@sandbox
systemctl reload caddy || systemctl restart caddy
echo "Setup done. Next: install each copy's .env, then run update.sh (DEPLOY.md)."
