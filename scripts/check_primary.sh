#!/usr/bin/env bash
set -euo pipefail

pi_host="${PI_HOST:-pi4b8g.local}"
pi_user="${PI_USER:-pi}"

echo "Checking SSH target: ${pi_user}@${pi_host}"
ssh -o ConnectTimeout=8 "${pi_user}@${pi_host}" \
  'hostname; uname -m; python3 --version; test -r /proc/device-tree/model && tr -d "\000" </proc/device-tree/model; vcgencmd get_throttled'

