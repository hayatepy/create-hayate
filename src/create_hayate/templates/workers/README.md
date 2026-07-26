# $project_name

A TODO API built with [hayate](https://github.com/hayatepy/hayate), deployed
to [Cloudflare Python Workers](https://developers.cloudflare.com/workers/languages/python/).
The app core is runtime-agnostic — the same `app.py` runs on any ASGI server too.

$workers_entrypoint_summary

## Test

```sh
uv run pytest
```

Tests call the app core directly (`await app.request(...)`); no server or
workerd needed. The contract includes an internationalized hostname so the
lazy `uts46` dependency cannot accidentally disappear from the Worker bundle.

For the ASGI path:

```sh
uv run uvicorn app:app --app-dir src --reload
```

## Develop locally

The Workers runtime currently uses Python 3.13 and Pywrangler requires
Node.js 24. The generated `.node-version` and `.nvmrc` files let common
version managers select the supported Node release.

```sh
uv run python manage_workers.py dev
```

Then:

```sh
curl -X POST localhost:8787/todos -H 'content-type: application/json' -d '{"title": "try hayate"}'
curl localhost:8787/todos
```

## Deploy

```sh
uv run python manage_workers.py deploy
```

The generated `wrangler.toml` omits bytecode caches, package metadata, ASGI
and AWS adapters, and the Workers WSGI bridge. It deliberately retains
`uts46`. Because `*.dist-info` is excluded, `importlib.metadata` cannot inspect
installed distributions at runtime; remove that exclusion if your application
needs package metadata. Application code lives under `src/`, which keeps local
virtual environments, tests, and deployment-management scripts outside
Wrangler's module root while allowing new `src/` modules to be discovered.

The default class entrypoint is feature-complete. For a strictly HTTP-only
service where warm throughput has priority, generate the explicit compatibility
path with:

```sh
uvx create-hayate $project_name --template workers --workers-entrypoint global
```

The global path does not expose named RPC methods or class handlers such as
`scheduled`.
