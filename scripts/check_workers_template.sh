#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="${1:-workers}"
test_dir="$(mktemp -d)"
log_file="${test_dir}.${template}.workerd.log"
dry_run_log="${test_dir}.${template}.dry-run.log"
bundle_dir="${test_dir}/${template}-bundle"
port=8793
server_pid=""
ready_path="/"
hayate_wheel="${HAYATE_ECOSYSTEM_WHEEL:-}"

if [[ "${template}" != "workers" && "${template}" != "mcp" ]]; then
  echo "expected workers or mcp template, got: ${template}" >&2
  exit 2
fi
if [[ -n "${hayate_wheel}" ]]; then
  if [[ ! -f "${hayate_wheel}" || "${hayate_wheel}" != *.whl ]]; then
    echo "HAYATE_ECOSYSTEM_WHEEL must name an existing wheel: ${hayate_wheel}" >&2
    exit 2
  fi
  hayate_wheel="$(cd "$(dirname "${hayate_wheel}")" && pwd)/$(basename "${hayate_wheel}")"
fi
if [[ "${template}" == "workers" ]]; then
  ready_path="/todos"
else
  port=8794
fi

terminate_tree() {
  local parent_pid="$1"
  local child_pid
  while read -r child_pid; do
    if [[ -n "${child_pid}" ]]; then
      terminate_tree "${child_pid}"
    fi
  done < <(pgrep -P "${parent_pid}" 2>/dev/null || true)
  kill "${parent_pid}" 2>/dev/null || true
}

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    # pywrangler launches uv -> Python -> npx -> workerd descendants. Killing
    # only the wrapper shell can leave the listener alive long enough to
    # collide with the next template check in the ecosystem gate.
    terminate_tree "${server_pid}"
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

node --version >/dev/null

(
  cd "${test_dir}"
  "${repo_dir}/.venv/bin/create-hayate" demo-app --template "${template}" --no-input
  cd demo-app
  uv sync
  if [[ -n "${hayate_wheel}" ]]; then
    # Test the generated CPython app against the same unpublished core wheel.
    uv pip install \
      --python .venv/bin/python \
      --reinstall-package hayate \
      --no-deps \
      "${hayate_wheel}"
  fi
  uv run --no-sync pytest -q
  if [[ -n "${hayate_wheel}" ]]; then
    # pywrangler's pylock.toml sync cannot accept uv overrides. Complete its
    # ordinary sync first, then replace only the portable Hayate package in
    # the generated Worker bundle.
    uv run --no-sync python manage_workers.py sync
    uv pip install \
      --target python_modules \
      --reinstall \
      --no-deps \
      "${hayate_wheel}"
  fi
  if ! uv run --no-sync python manage_workers.py deploy \
    --dry-run \
    --outdir "${bundle_dir}" >"${dry_run_log}" 2>&1; then
    cat "${dry_run_log}"
    exit 1
  fi
  upload_size="$(grep -F "Total Upload:" "${dry_run_log}" | tail -1)"
  if [[ -z "${upload_size}" ]]; then
    cat "${dry_run_log}"
    echo "Wrangler dry-run did not report an upload size" >&2
    exit 1
  fi
  echo "upload[${template}]=${upload_size}"
  for excluded_path in \
    ".venv" \
    ".venv-workers" \
    "tests" \
    "manage_workers.py" \
    "node_compat.py" \
    "python_modules/asgi.py" \
    "python_modules/hayate/adapters/asgi.py" \
    "python_modules/hayate/adapters/aws.py" \
    "python_modules/workers/wsgi.py"; do
    if [[ -e "${bundle_dir}/${excluded_path}" ]]; then
      echo "excluded path reached Wrangler upload: ${excluded_path}" >&2
      exit 1
    fi
  done
  if find "${bundle_dir}" -type d -name "*.dist-info" -print -quit | grep -q .; then
    echo "package metadata reached Wrangler upload" >&2
    exit 1
  fi
  if find "${bundle_dir}" \( -type f -name "*.pyc" -o -type d -name "__pycache__" \) \
    -print -quit | grep -q .; then
    echo "Python cache reached Wrangler upload" >&2
    exit 1
  fi
  if [[ ! -f "${bundle_dir}/python_modules/uts46/_data.py" ]]; then
    echo "required UTS-46 mapping is absent from Wrangler upload" >&2
    exit 1
  fi
  uv run --no-sync python manage_workers.py dev --port "${port}"
) >"${log_file}" 2>&1 &
server_pid=$!

ready=false
for _ in {1..60}; do
  if curl --fail --silent --max-time 2 "http://127.0.0.1:${port}${ready_path}" >/dev/null; then
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

grep -F "upload[${template}]=" "${log_file}" | tail -1
canonicalized="$(curl --fail --silent --max-time 5 "http://127.0.0.1:${port}/canonicalize")"
uv run python -c \
  'import json,sys; assert json.loads(sys.argv[1]) == {"hostname":"xn--wgv71a119e.example"}' \
  "${canonicalized}"
echo "contract[${template}].canonicalize=${canonicalized}"

if [[ "${template}" == "workers" ]]; then
  created="$(
    curl --fail --silent --max-time 5 \
      -X POST "http://127.0.0.1:${port}/todos" \
      -H "content-type: application/json" \
      --data '{"title":"generated worker"}'
  )"
  uv run python -c \
    'import json,sys; todo=json.loads(sys.argv[1]); assert todo["title"] == "generated worker"' \
    "${created}"

  listed="$(curl --fail --silent --max-time 5 "http://127.0.0.1:${port}/todos")"
  uv run python -c \
    'import json,sys; assert any(todo["title"] == "generated worker" for todo in json.loads(sys.argv[1]))' \
    "${listed}"
  echo "contract[workers].create=${created}"
  echo "contract[workers].list=${listed}"
  exit 0
fi

initialized="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"generated-workerd-check","version":"1.0.0"}}}'
)"
uv run python -c \
  'import json,sys; assert json.loads(sys.argv[1])["result"]["protocolVersion"] == "2025-11-25"' \
  "${initialized}"
echo "contract[mcp].initialize=${initialized}"

called="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    -H "mcp-protocol-version: 2025-11-25" \
    -H "x-request-id: generated-workerd-1" \
    --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"greet","arguments":{"name":"Workerd"}}}'
)"
uv run python -c \
  'import json,sys; result=json.loads(sys.argv[1])["result"]; assert result["structuredContent"] == {"message":"Hello, Workerd!","request_id":"generated-workerd-1"}' \
  "${called}"
echo "contract[mcp].tools_call=${called}"
