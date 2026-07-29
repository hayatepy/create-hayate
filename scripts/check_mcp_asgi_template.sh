#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project_dir="${1:-demo-app}"
if [[ "${project_dir}" != /* ]]; then
  project_dir="${repo_dir}/${project_dir}"
fi
log_file="$(mktemp)"
port=8794
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

created="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/todos" \
    -H "content-type: application/json" \
    --data '{"title":"visible over ASGI MCP"}'
)"
uv run python -c \
  'import json,sys; assert json.loads(sys.argv[1])["title"] == "visible over ASGI MCP"' \
  "${created}"

discovered="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    -H "mcp-protocol-version: 2026-07-28" \
    -H "mcp-method: server/discover" \
    --data '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"generated-asgi-check","version":"1.0.0"}}}}'
)"
uv run python -c \
  'import json,sys; result=json.loads(sys.argv[1])["result"]; assert result["supportedVersions"] == ["2026-07-28"]; assert result["resultType"] == "complete"; assert "tools" in result["capabilities"]' \
  "${discovered}"

called="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    -H "mcp-protocol-version: 2026-07-28" \
    -H "mcp-method: tools/call" \
    -H "mcp-name: list_todos" \
    --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"generated-asgi-check","version":"1.0.0"}},"name":"list_todos","arguments":{}}}'
)"
uv run python -c \
  'import json,sys; envelope=json.loads(sys.argv[1])["result"]; assert envelope["resultType"] == "complete"; result=envelope["structuredContent"]; assert result["subject"] == "anonymous"; assert any(todo["title"] == "visible over ASGI MCP" for todo in result["todos"])' \
  "${called}"
