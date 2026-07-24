#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_dir="$(mktemp -d)"
log_file="${test_dir}.workerd.log"
port=8793
server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

node --experimental-wasm-stack-switching --version >/dev/null

(
  cd "${test_dir}"
  "${repo_dir}/.venv/bin/create-hayate" demo-app --template workers --no-input
  cd demo-app
  uv sync
  uv run python manage_workers.py dev --port "${port}"
) >"${log_file}" 2>&1 &
server_pid=$!

ready=false
for _ in {1..60}; do
  if curl --fail --silent --max-time 2 "http://127.0.0.1:${port}/todos" >/dev/null; then
    ready=true
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    cat "${log_file}"
    exit 1
  fi
  sleep 1
done
if [[ "${ready}" != true ]]; then
  cat "${log_file}"
  exit 1
fi

created="$(
  curl --fail --silent --max-time 5 \
    -X POST "http://127.0.0.1:${port}/todos" \
    -H "content-type: application/json" \
    --data '{"title":"generated worker"}'
)"
python -c \
  'import json,sys; todo=json.loads(sys.argv[1]); assert todo["title"] == "generated worker"' \
  "${created}"

listed="$(curl --fail --silent --max-time 5 "http://127.0.0.1:${port}/todos")"
python -c \
  'import json,sys; assert any(todo["title"] == "generated worker" for todo in json.loads(sys.argv[1]))' \
  "${listed}"
