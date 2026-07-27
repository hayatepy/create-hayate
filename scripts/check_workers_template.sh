#!/usr/bin/env bash
set -euo pipefail

started_at="${SECONDS}"
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
create_hayate_wheel="${CREATE_HAYATE_WHEEL:-}"
matrix_features="${MATRIX_FEATURES:-}"
matrix_auth="${MATRIX_AUTH:-none}"
matrix_entrypoint="${MATRIX_ENTRYPOINT:-class}"
matrix_python="${MATRIX_PYTHON:-}"
production_mode=false
global_mode=false
htmx_mode=false
react_mode=false
astro_mode=false
sql_mode=false
admin_mode=false

if [[ "${template}" == "production" || "${template}" == "production-admin" \
  || "${template}" == "production-global" ]]; then
  production_mode=true
fi
if [[ "${template}" == "admin" || "${template}" == "admin-global" \
  || "${template}" == "production-admin" ]]; then
  admin_mode=true
  sql_mode=true
fi
if [[ "${template}" == "production-global" || "${template}" == "admin-global" ]]; then
  global_mode=true
fi
if [[ "${template}" == "htmx" ]]; then
  htmx_mode=true
fi
if [[ "${template}" == "react" ]]; then
  react_mode=true
fi
if [[ "${template}" == "astro" ]]; then
  astro_mode=true
fi
if [[ ",${matrix_features}," == *",sql,"* ]]; then
  sql_mode=true
fi
if [[ "${template}" != "workers" && "${template}" != "mcp" \
  && "${htmx_mode}" != true && "${react_mode}" != true && "${astro_mode}" != true \
  && "${admin_mode}" != true && "${production_mode}" != true ]]; then
  echo "expected workers, mcp, admin, admin-global, htmx, react, astro, production, production-admin, or production-global; got: ${template}" >&2
  exit 2
fi
if [[ -n "${hayate_wheel}" ]]; then
  if [[ ! -f "${hayate_wheel}" || "${hayate_wheel}" != *.whl ]]; then
    echo "HAYATE_ECOSYSTEM_WHEEL must name an existing wheel: ${hayate_wheel}" >&2
    exit 2
  fi
  hayate_wheel="$(cd "$(dirname "${hayate_wheel}")" && pwd)/$(basename "${hayate_wheel}")"
fi
if [[ -n "${create_hayate_wheel}" ]]; then
  if [[ ! -f "${create_hayate_wheel}" || "${create_hayate_wheel}" != *.whl ]]; then
    echo "CREATE_HAYATE_WHEEL must name an existing wheel: ${create_hayate_wheel}" >&2
    exit 2
  fi
  create_hayate_wheel="$(
    cd "$(dirname "${create_hayate_wheel}")"
    pwd
  )/$(basename "${create_hayate_wheel}")"
fi
if [[ "${matrix_auth}" != "none" && "${matrix_auth}" != "cloudflare-access" ]]; then
  echo "MATRIX_AUTH must be none or cloudflare-access; got: ${matrix_auth}" >&2
  exit 2
fi
if [[ "${matrix_entrypoint}" != "class" && "${matrix_entrypoint}" != "global" ]]; then
  echo "MATRIX_ENTRYPOINT must be class or global; got: ${matrix_entrypoint}" >&2
  exit 2
fi
if [[ "${admin_mode}" == true ]]; then
  port=8800
  if [[ "${global_mode}" == true ]]; then
    port=8801
  fi
  ready_path="/admin"
elif [[ "${template}" == "workers" ]]; then
  ready_path="/todos"
elif [[ "${template}" == "mcp" ]]; then
  port=8794
  ready_path="/health"
elif [[ "${htmx_mode}" == true ]]; then
  port=8797
  ready_path="/app"
elif [[ "${react_mode}" == true ]]; then
  port=8798
  ready_path="/"
elif [[ "${astro_mode}" == true ]]; then
  port=8799
  ready_path="/"
else
  port=8795
  if [[ "${global_mode}" == true ]]; then
    port=8796
  fi
  ready_path="/health"
fi
auth_header=(-H "x-create-hayate-smoke: true")
identity_email="workerd@example.com"
if [[ "${production_mode}" == true || "${matrix_auth}" == "cloudflare-access" ]]; then
  auth_header=(-H "cf-access-authenticated-user-email: workerd@example.com")
fi
if [[ "${admin_mode}" == true ]]; then
  identity_email="developer@example.com"
  auth_header=(-H "cf-access-authenticated-user-email: ${identity_email}")
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
  generator=("${repo_dir}/.venv/bin/create-hayate")
  if [[ -n "${create_hayate_wheel}" ]]; then
    generator=(uvx --from "${create_hayate_wheel}" create-hayate)
  fi
  if [[ "${production_mode}" == true ]]; then
    create_args=(demo-app --template workers --preset production --no-input)
    if [[ "${admin_mode}" == true ]]; then
      create_args+=(--with admin)
    fi
    if [[ "${global_mode}" == true ]]; then
      create_args+=(--workers-entrypoint global)
    fi
    "${generator[@]}" "${create_args[@]}"
  else
    generated_template="${template}"
    frontend="none"
    if [[ "${admin_mode}" == true ]]; then
      generated_template="workers"
    fi
    if [[ "${htmx_mode}" == true || "${react_mode}" == true || "${astro_mode}" == true ]]; then
      generated_template="workers"
      frontend="${template}"
    fi
    create_args=(demo-app --template "${generated_template}" --no-input)
    if [[ "${frontend}" != "none" ]]; then
      create_args+=(--frontend "${frontend}")
    fi
    if [[ "${admin_mode}" == true ]]; then
      create_args+=(--with admin)
    fi
    if [[ -n "${matrix_features}" ]]; then
      create_args+=(--with "${matrix_features}")
    fi
    if [[ "${matrix_auth}" != "none" ]]; then
      create_args+=(--auth "${matrix_auth}")
    fi
    if [[ "${global_mode}" == true ]]; then
      create_args+=(--workers-entrypoint global)
    elif [[ "${matrix_entrypoint}" != "class" ]]; then
      create_args+=(--workers-entrypoint "${matrix_entrypoint}")
    fi
    "${generator[@]}" "${create_args[@]}"
  fi
  cd demo-app
  lock_args=(lock)
  sync_args=(sync --locked)
  if [[ -n "${matrix_python}" ]]; then
    lock_args+=(--python "${matrix_python}")
    sync_args+=(--python "${matrix_python}")
  fi
  uv "${lock_args[@]}"
  uv "${sync_args[@]}"
  if [[ "${react_mode}" == true || "${astro_mode}" == true ]]; then
    (
      cd frontend
      npm ci --ignore-scripts
      npm run build
      npm audit --audit-level=high
    )
  fi
  if [[ -n "${hayate_wheel}" ]]; then
    # Test the generated CPython app against the same unpublished core wheel.
    uv pip install \
      --python .venv/bin/python \
      --reinstall-package hayate \
      --no-deps \
      "${hayate_wheel}"
  fi
  uv run --no-sync pytest -q
  if [[ "${production_mode}" == true || "${sql_mode}" == true ]]; then
    uv run --no-sync python scripts/check_sql_contracts.py
  fi
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
  deploy_args=(deploy --dry-run --outdir "${bundle_dir}")
  if [[ "${production_mode}" == true ]]; then
    deploy_args+=(--env production)
  fi
  if ! uv run --no-sync python manage_workers.py \
    "${deploy_args[@]}" >"${dry_run_log}" 2>&1; then
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
  if [[ "${production_mode}" == true || "${sql_mode}" == true ]]; then
    if [[ ! -f "${bundle_dir}/python_modules/hayate_sql/__init__.py" ]]; then
      echo "hayate-sql is absent from the SQL-enabled Worker bundle" >&2
      exit 1
    fi
    uv run --no-sync python manage_workers.py d1 migrations apply DB --local
  fi
  if [[ "${admin_mode}" == true ]]; then
    for required_admin_path in \
      "hayate_admin/site.py" \
      "hayate_htmx/request.py"; do
      if [[ ! -f "${bundle_dir}/${required_admin_path}" ]]; then
        echo "vendored admin runtime is absent from Worker bundle: ${required_admin_path}" >&2
        exit 1
      fi
    done
  fi
  uv run --no-sync python manage_workers.py dev --port "${port}"
) >"${log_file}" 2>&1 &
server_pid=$!

ready=false
for _ in {1..60}; do
  if curl --fail --silent --max-time 2 \
    "${auth_header[@]}" \
    "http://127.0.0.1:${port}${ready_path}" >/dev/null; then
    ready=true
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    tail -n 250 "${log_file}"
    exit 1
  fi
  sleep 1
done
if [[ "${ready}" != true ]]; then
  tail -n 250 "${log_file}"
  exit 1
fi

grep -F "upload[${template}]=" "${log_file}" | tail -1
canonicalize_prefix=""
if [[ "${htmx_mode}" == true || "${react_mode}" == true || "${astro_mode}" == true ]]; then
  canonicalize_prefix="/api"
fi
canonicalize_path="${canonicalize_prefix}/canonicalize"
warmup_file="${test_dir}/canonicalize-warmup.json"
warmup_status=""
for _ in {1..20}; do
  warmup_status="$(
    curl --silent --show-error --max-time 5 \
      --output "${warmup_file}" \
      --write-out "%{http_code}" \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}${canonicalize_path}"
  )"
  if [[ "${warmup_status}" == "200" ]]; then
    break
  fi
  sleep 0.25
done
if [[ "${warmup_status}" != "200" ]]; then
  tail -n 250 "${log_file}" >&2
  cat "${warmup_file}" >&2
  echo "generated workerd warm-up returned ${warmup_status}" >&2
  exit 1
fi

canonicalized_file="${test_dir}/canonicalized.json"
canonicalized_status="$(
  curl --silent --show-error --max-time 5 \
    --output "${canonicalized_file}" \
    --write-out "%{http_code}" \
    "${auth_header[@]}" \
    -H "x-request-id: generated-workerd-smoke" \
    "http://127.0.0.1:${port}${canonicalize_path}?access_token=must-not-be-logged"
)"
if [[ "${canonicalized_status}" != "200" ]]; then
  tail -n 250 "${log_file}" >&2
  cat "${canonicalized_file}" >&2
  echo "generated workerd canonicalize returned ${canonicalized_status}" >&2
  exit 1
fi
canonicalized="$(
  cat "${canonicalized_file}"
)"
uv run python -c \
  'import json,sys; assert json.loads(sys.argv[1]) == {"hostname":"xn--wgv71a119e.example"}' \
  "${canonicalized}"
request_log_line=""
for _ in {1..20}; do
  request_log_line="$(grep -F '"request_id":"generated-workerd-smoke"' "${log_file}" | tail -1)"
  if [[ -n "${request_log_line}" ]]; then
    break
  fi
  sleep 0.25
done
if [[ -z "${request_log_line}" || "${request_log_line}" == *"must-not-be-logged"* ]]; then
  tail -n 250 "${log_file}" >&2
  echo "generated workerd request log is missing correlation or exposed the query string" >&2
  exit 1
fi
echo "contract[${template}].canonicalize=${canonicalized}"

if [[ "${admin_mode}" == true ]]; then
  admin_home_headers="${test_dir}/admin-home.headers"
  admin_home="$(
    curl --fail --silent --max-time 5 \
      --dump-header "${admin_home_headers}" \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/admin"
  )"
  if [[ "${admin_home}" != *"demo-app Operations"* \
    || "${admin_home}" != *'class="skip-link"'* \
    || "${admin_home}" != *"@media(prefers-reduced-motion:reduce)"* ]]; then
    echo "admin home did not expose the reviewed branding and accessibility contract" >&2
    exit 1
  fi
  if ! grep -qiF "style-src 'sha256-" "${admin_home_headers}"; then
    echo "admin home did not use a hashed style CSP" >&2
    exit 1
  fi
  if grep -qiF "'unsafe-inline'" "${admin_home_headers}"; then
    echo "admin home CSP allowed unsafe inline content" >&2
    exit 1
  fi
  denied_status="$(
    curl --silent --show-error --output /dev/null --write-out "%{http_code}" --max-time 5 \
      -H "cf-access-authenticated-user-email: viewer@example.com" \
      "http://127.0.0.1:${port}/admin"
  )"
  if [[ "${denied_status}" != "403" ]]; then
    echo "expected non-operator admin request to return 403; got ${denied_status}" >&2
    exit 1
  fi
  created_headers="${test_dir}/admin-created.headers"
  curl --fail --silent --max-time 5 \
    --dump-header "${created_headers}" \
    --output /dev/null \
    -X POST "http://127.0.0.1:${port}/admin/todos/create" \
    "${auth_header[@]}" \
    -H "origin: https://app.example.com" \
    -H "content-type: application/x-www-form-urlencoded" \
    --data "title=generated+admin+worker"
  if ! grep -qiE "^location: /admin/todos/object/" "${created_headers}"; then
    echo "admin create did not return an object redirect" >&2
    exit 1
  fi
  created_location="$(
    grep -iE "^location: /admin/todos/object/" "${created_headers}" \
      | head -1 \
      | cut -d" " -f2- \
      | tr -d "\r"
  )"
  admin_history="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}${created_location}/history"
  )"
  if [[ "${admin_history}" != *"Add record"* \
    || "${admin_history}" == *"generated admin worker"* ]]; then
    echo "admin history did not expose the localized, redacted audit contract" >&2
    exit 1
  fi
  admin_list="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/admin/todos?view=title-a-z&q=generated"
  )"
  if [[ "${admin_list}" != *"generated admin worker"* ]]; then
    echo "admin list did not expose the created identity-scoped record" >&2
    exit 1
  fi
  admin_csv="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/admin/todos/export.csv?view=title-a-z&q=generated"
  )"
  if [[ "${admin_csv}" != *"generated admin worker"* ]]; then
    echo "admin CSV did not expose the bounded identity-scoped record" >&2
    exit 1
  fi
  if [[ "${admin_list}" != *'aria-current="page">Title A-Z'* ]]; then
    echo "admin list did not apply the static saved view" >&2
    exit 1
  fi
  echo "contract[${template}].admin=authorized,origin-checked,audited,localized,branded,a11y,csp,saved-view,cursor,csv"
  if [[ "${production_mode}" != true ]]; then
    exit 0
  fi
fi

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

if [[ "${htmx_mode}" == true ]]; then
  page="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/app"
  )"
  if [[ "${page}" != "<!doctype html>"* ]]; then
    echo "htmx profile did not return a complete page" >&2
    exit 1
  fi
  asset="$(
    curl --fail --silent --max-time 5 \
      "http://127.0.0.1:${port}/assets/vendor/htmx-2.0.10.min.js"
  )"
  if [[ "${asset}" != "var htmx="* ]]; then
    echo "Cloudflare Static Assets did not serve the pinned htmx build" >&2
    exit 1
  fi
  asset_headers="$(
    curl --fail --silent --head --max-time 5 \
      "http://127.0.0.1:${port}/assets/vendor/htmx-2.0.10.min.js"
  )"
  if ! grep -qiF "cache-control: public, max-age=31536000, immutable" \
    <<<"${asset_headers}"; then
    echo "pinned htmx asset is missing its immutable cache contract" >&2
    exit 1
  fi
  curl --fail --silent --max-time 5 \
    -X POST "http://127.0.0.1:${port}/app/todos" \
    "${auth_header[@]}" \
    -H "origin: http://127.0.0.1:${port}" \
    -H "hx-request: true" \
    -H "content-type: application/x-www-form-urlencoded" \
    --data "title=generated+htmx+worker" >/dev/null
  listed="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/api/todos"
  )"
  uv run python -c \
    'import json,sys; assert any(todo["title"] == "generated htmx worker" for todo in json.loads(sys.argv[1]))' \
    "${listed}"
  curl --fail --silent --max-time 5 \
    "${auth_header[@]}" \
    "http://127.0.0.1:${port}/auth" >/dev/null
  stream="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/app/stream"
  )"
  if [[ "${stream}" != *"event: done"* ]]; then
    echo "htmx profile SSE stream did not complete" >&2
    exit 1
  fi
  echo "contract[htmx].list=${listed}"
  exit 0
fi

if [[ "${react_mode}" == true ]]; then
  page="$(curl --fail --silent --max-time 5 "http://127.0.0.1:${port}/")"
  if [[ "${page}" != "<!doctype html>"* || "${page}" != *"<div id=\"root\"></div>"* ]]; then
    echo "React profile did not return its built SPA shell" >&2
    exit 1
  fi
  page_headers="$(curl --fail --silent --head --max-time 5 "http://127.0.0.1:${port}/")"
  if ! grep -qiF "content-security-policy: default-src 'self'" <<<"${page_headers}"; then
    echo "React profile SPA shell is missing its static security headers" >&2
    exit 1
  fi
  deep_link="$(
    curl --fail --silent --max-time 5 \
      -H "Sec-Fetch-Mode: navigate" \
      "http://127.0.0.1:${port}/about"
  )"
  if [[ "${deep_link}" != *"<div id=\"root\"></div>"* ]]; then
    echo "React profile did not apply SPA fallback to a navigation request" >&2
    exit 1
  fi
  created="$(
    curl --fail --silent --max-time 5 \
      -X POST "http://127.0.0.1:${port}/api/todos" \
      "${auth_header[@]}" \
      -H "content-type: application/json" \
      --data '{"title":"generated React worker"}'
  )"
  uv run python -c \
    'import json,sys; assert json.loads(sys.argv[1])["title"] == "generated React worker"' \
    "${created}"
  listed="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/api/todos"
  )"
  uv run python -c \
    'import json,sys; assert any(todo["title"] == "generated React worker" for todo in json.loads(sys.argv[1]))' \
    "${listed}"
  openapi="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/openapi.json"
  )"
  uv run python -c \
    'import json,sys; document=json.loads(sys.argv[1]); assert "/api/todos" in document["paths"]' \
    "${openapi}"
  echo "contract[react].list=${listed}"
  exit 0
fi

if [[ "${astro_mode}" == true ]]; then
  page="$(curl --fail --silent --max-time 5 "http://127.0.0.1:${port}/")"
  if [[ "${page}" != "<!DOCTYPE html>"* || "${page}" != *"Build less."* ]]; then
    echo "Astro profile did not return its generated static home page" >&2
    exit 1
  fi
  if [[ "${page}" == *"/api/todos"* || "${page}" == *"data-private-record-count"* ]]; then
    echo "Astro static home page contains private runtime data" >&2
    exit 1
  fi
  page_headers="$(curl --fail --silent --head --max-time 5 "http://127.0.0.1:${port}/")"
  if ! grep -qiF "content-security-policy: default-src 'self'" <<<"${page_headers}"; then
    echo "Astro profile static page is missing its security headers" >&2
    exit 1
  fi
  principles="$(
    curl --fail --silent --max-time 5 \
      -H "Sec-Fetch-Mode: navigate" \
      "http://127.0.0.1:${port}/principles/"
  )"
  if [[ "${principles}" != *"Public is durable."* ]]; then
    echo "Astro profile did not serve its generated deep route" >&2
    exit 1
  fi
  missing_status="$(
    curl --silent --output "${test_dir}/astro-missing.html" --write-out "%{http_code}" \
      -H "Sec-Fetch-Mode: navigate" \
      "http://127.0.0.1:${port}/missing/"
  )"
  if [[ "${missing_status}" != "404" ]] \
    || ! grep -qF "This note" "${test_dir}/astro-missing.html"; then
    echo "Astro profile did not serve its generated 404 page" >&2
    exit 1
  fi
  created="$(
    curl --fail --silent --max-time 5 \
      -X POST "http://127.0.0.1:${port}/api/todos" \
      "${auth_header[@]}" \
      -H "content-type: application/json" \
      --data '{"title":"generated Astro worker"}'
  )"
  uv run python -c \
    'import json,sys; assert json.loads(sys.argv[1])["title"] == "generated Astro worker"' \
    "${created}"
  listed="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/api/todos"
  )"
  uv run python -c \
    'import json,sys; assert any(todo["title"] == "generated Astro worker" for todo in json.loads(sys.argv[1]))' \
    "${listed}"
  openapi="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/openapi.json"
  )"
  uv run python -c \
    'import json,sys; document=json.loads(sys.argv[1]); assert "/api/todos" in document["paths"]' \
    "${openapi}"
  echo "contract[astro].list=${listed}"
  exit 0
fi

if [[ "${production_mode}" == true ]]; then
  openapi="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/openapi.json"
  )"
  uv run python -c \
    'import json,sys; document=json.loads(sys.argv[1]); operation=document["paths"]["/todos/{id}"]["get"]; assert document["openapi"] == "3.1.1"; assert operation["parameters"][0]["schema"] == {"type":"string","format":"uuid"}; assert operation["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["id"] == {"type":"string","format":"uuid"}' \
    "${openapi}"
  invalid_status="$(
    curl --silent --show-error --output /dev/null --write-out "%{http_code}" --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/todos/not-a-uuid"
  )"
  if [[ "${invalid_status}" != "400" ]]; then
    echo "expected malformed typed UUID to return 400; got ${invalid_status}" >&2
    exit 1
  fi
  curl --fail --silent --max-time 5 \
    "${auth_header[@]}" \
    "http://127.0.0.1:${port}/docs" >/dev/null
  identity="$(
    curl --fail --silent --max-time 5 \
      "${auth_header[@]}" \
      "http://127.0.0.1:${port}/whoami"
  )"
  uv run python -c \
    'import json,sys; assert json.loads(sys.argv[1])["subject"] == sys.argv[2]' \
    "${identity}" "${identity_email}"
  created="$(
    curl --fail --silent --max-time 5 \
      -X POST "http://127.0.0.1:${port}/todos" \
      "${auth_header[@]}" \
      -H "content-type: application/json" \
      --data '{"title":"D1 production todo"}'
  )"
  uv run python -c \
    'import json,sys; assert json.loads(sys.argv[1])["title"] == "D1 production todo"' \
    "${created}"
fi

initialized="$(
  curl --fail --silent --max-time 10 \
    -X POST "http://127.0.0.1:${port}/mcp" \
    "${auth_header[@]}" \
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
    "${auth_header[@]}" \
    -H "accept: application/json, text/event-stream" \
    -H "content-type: application/json" \
    -H "mcp-protocol-version: 2025-11-25" \
    --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_todos","arguments":{}}}'
)"
uv run python -c \
  'import json,sys; result=json.loads(sys.argv[1])["result"]["structuredContent"]; assert result["subject"]; assert isinstance(result["todos"], list)' \
  "${called}"
echo "contract[mcp].tools_call=${called}"
if [[ "${production_mode}" == true ]]; then
  elapsed="$((SECONDS - started_at))"
  if [[ "${elapsed}" -ge 600 ]]; then
    echo "production quickstart exceeded ten minutes: ${elapsed}s" >&2
    exit 1
  fi
  echo "contract[production].quickstart_seconds=${elapsed}"
fi
