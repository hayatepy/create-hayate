#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project_dir="${1:-demo-production}"
if [[ "${project_dir}" != /* ]]; then
  project_dir="${repo_dir}/${project_dir}"
fi
log_file="$(mktemp)"
port=8795
server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

(
  cd "${project_dir}"
  uv run uvicorn app:app --app-dir src --host 127.0.0.1 --port "${port}"
) >"${log_file}" 2>&1 &
server_pid=$!

ready=false
for _ in {1..30}; do
  if curl --fail --silent --max-time 2 "http://127.0.0.1:${port}/health" >/dev/null; then
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

auth_header="cf-access-authenticated-user-email: asgi@example.com"
created="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/todos" \
    -H "${auth_header}" \
    -H "content-type: application/json" \
    --data '{"title":"SQLite production todo"}'
)"
uv run python -c \
  'import json,sys; assert json.loads(sys.argv[1])["title"] == "SQLite production todo"' \
  "${created}"

if [[ -f "${project_dir}/src/feature_admin.py" ]]; then
  admin_header="cf-access-authenticated-user-email: developer@example.com"
  admin_created_headers="$(mktemp)"
  curl --fail --silent --max-time 10 \
    --dump-header "${admin_created_headers}" \
    --output /dev/null \
    -X POST "http://127.0.0.1:${port}/admin/todos/create" \
    -H "${admin_header}" \
    -H "origin: https://app.example.com" \
    -H "content-type: application/x-www-form-urlencoded" \
    --data "title=SQLite+production+admin"
  grep -qiE "^location: /admin/todos/object/" "${admin_created_headers}"
  admin_list="$(
    curl --fail --silent --max-time 10 \
      -H "${admin_header}" \
      "http://127.0.0.1:${port}/admin/todos?q=production"
  )"
  if [[ "${admin_list}" != *"SQLite production admin"* ]]; then
    echo "production ASGI admin did not return its identity-scoped record" >&2
    exit 1
  fi
fi

openapi="$(
  curl --fail --silent --max-time 10 \
    -H "${auth_header}" \
    "http://127.0.0.1:${port}/openapi.json"
)"
uv run python -c \
  'import json,sys; document=json.loads(sys.argv[1]); operation=document["paths"]["/todos/{id}"]["get"]; assert document["openapi"] == "3.1.1"; assert operation["parameters"][0]["schema"] == {"type":"string","format":"uuid"}; assert operation["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"] == {"type":"string","format":"uuid"}' \
  "${openapi}"

invalid_status="$(
  curl --silent --show-error --output /dev/null --write-out "%{http_code}" --max-time 10 \
    -H "${auth_header}" \
    "http://127.0.0.1:${port}/todos/not-a-uuid"
)"
if [[ "${invalid_status}" != "400" ]]; then
  echo "expected malformed typed UUID to return 400; got ${invalid_status}" >&2
  exit 1
fi

initialized="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    -H "${auth_header}" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"production-asgi-check","version":"1.0.0"}}}'
)"
uv run python -c \
  'import json,sys; assert json.loads(sys.argv[1])["result"]["protocolVersion"] == "2025-11-25"' \
  "${initialized}"

called="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    -H "${auth_header}" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    -H "mcp-protocol-version: 2025-11-25" \
    --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_todos","arguments":{}}}'
)"
uv run python -c \
  'import json,sys; result=json.loads(sys.argv[1])["result"]["structuredContent"]; assert result["subject"] == "asgi@example.com"; assert any(todo["title"] == "SQLite production todo" for todo in result["todos"])' \
  "${called}"
