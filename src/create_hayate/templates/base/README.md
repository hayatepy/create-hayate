# $project_name

> **Hayate ecosystem:** [Start here](https://github.com/hayatepy/.github/blob/main/docs/START.md)
> · [Production golden app](https://github.com/hayatepy/golden-app)
> · [Tested compatibility](https://github.com/hayatepy/.github/blob/main/docs/COMPATIBILITY.md)

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
