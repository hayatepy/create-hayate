# $project_name

A Hayate application composed from: **$feature_summary**.

The application core in `src/app.py` is unchanged between ASGI and Cloudflare
Workers. Request and response handling use WHATWG Fetch semantics.

$runtime_readme

## Quick start

The complete local path is:

```sh
$quickstart_commands
```

After `uvx create-hayate ...` completes, these commands are designed to fit
comfortably inside ten minutes on a normal development machine.

## HTTP API

- `GET /health`
- `GET /whoami`
- `GET /todos`
- `POST /todos` with `{"title": "ship it"}`
- `GET /todos/:id`
- `DELETE /todos/:id`

$sql_readme

$mcp_readme

$openapi_readme

$auth_readme

$production_readme
