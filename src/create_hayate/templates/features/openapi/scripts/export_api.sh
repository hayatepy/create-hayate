#!/bin/sh
set -eu

mkdir -p client
PYTHONPATH=src uv run python -m hayate_openapi \
    app:app \
    --title "$project_name" \
    --version 0.1.0 \
    --output openapi.json \
    --typescript-client client/api-client.ts \
    --typescript-types-import ./api-types.js
npx --yes openapi-typescript@7.13.0 openapi.json -o client/api-types.ts
