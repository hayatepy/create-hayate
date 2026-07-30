# $project_name

> **Hayate ecosystem:** [Start here](https://hayatepy.dev/)
> · [Production golden app](https://github.com/hayatepy/golden-app)
> · [Tested compatibility](https://hayatepy.dev/evidence/compatibility/)

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

- `GET $api_prefix/health`
- `GET $api_prefix/whoami`
- `GET $api_prefix/todos`
- `POST $api_prefix/todos` with `{"title": "ship it"}`
- `GET $api_prefix/todos/:id`
- `PATCH $api_prefix/todos/:id`
- `DELETE $api_prefix/todos/:id`

## Observability

Request correlation is the first middleware boundary. A conservative incoming
`X-Request-ID` is reused; any missing, oversized, or unsafe value is replaced,
and the final value is returned on normal and handled-error responses.

Access events are one compact JSON object with `event`, `method`, `path`,
`status`, `duration_ms`, and `request_id`. The path excludes its query string,
and the default logger never records headers or bodies.

$sql_readme

$mcp_readme

$openapi_readme

$auth_readme

$admin_readme

$production_readme

$frontend_readme
