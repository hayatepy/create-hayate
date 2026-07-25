# $project_name

An MCP 2025-11-25 tools server built with
[hayate](https://github.com/hayatepy/hayate) and
[hayate-mcp](https://github.com/hayatepy/hayate-mcp). The same `app.py` runs
on ASGI and Cloudflare Python Workers.

## Test

```sh
uv run pytest
```

The tests cover initialization, discovery, tool execution, request context,
and model-correctable schema errors without opening a socket.

## Run on ASGI

```sh
uv run uvicorn app:app --reload
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
