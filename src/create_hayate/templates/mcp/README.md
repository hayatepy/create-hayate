# $project_name

An MCP 2025-11-25 tools server built with
[hayate](https://github.com/hayatepy/hayate) and
[hayate-mcp](https://github.com/hayatepy/hayate-mcp). The same `app.py` runs
on ASGI and Cloudflare Python Workers.

$workers_entrypoint_summary

## Test

```sh
uv run pytest
```

The tests cover initialization, discovery, tool execution, request context,
model-correctable schema errors, and UTS-46 internationalized hostnames without
opening a socket.

## Run on ASGI

```sh
uv run uvicorn app:app --app-dir src --reload
```

The MCP endpoint is `http://127.0.0.1:8000/mcp`.

## Run on local workerd

Python Workers use Python 3.13, and Pywrangler uses Node.js 24. The generated
`.node-version` and `.nvmrc` select that release in common version managers.

```sh
uv run python manage_workers.py dev
```

The MCP endpoint is `http://127.0.0.1:8787/mcp`.

## Add identity

`get_request_context()` gives each tool the active hayate `Context`. Read an
identity set by your existing middleware or managed access provider there.
`hayate-auth` is optional; add it only when this application should own the
authorization server.

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

The default class entrypoint preserves named RPC methods and class handlers.
An HTTP-only MCP transport can opt into the lower-overhead global compatibility
path at generation time:

```sh
uvx create-hayate $project_name --template mcp --workers-entrypoint global
```

That path cannot expose named RPC methods or class handlers such as `scheduled`.
