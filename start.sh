#!/bin/sh
set -eu

if [ -d /home/admin/app/focas_api ]; then
  cd /home/admin/app
elif [ -d /home/admin/app/app/focas_api ]; then
  cd /home/admin/app/app
elif [ -d ./focas_api ]; then
  :
elif [ -d ./app/focas_api ]; then
  cd ./app
else
  echo "Cannot locate focas_api. Current directory: $(pwd)"
  find /home/admin -maxdepth 4 -type d -name focas_api -print 2>/dev/null || true
  exit 1
fi

export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
exec python -m focas_api.server
