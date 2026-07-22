# $project_name

A TODO API built with [hayate](https://github.com/hayatepy/hayate) —
web-standards-first, zero dependencies, tested without a server.

## Test

```sh
uv run pytest
```

Tests call the app core directly (`await app.request(...)`); there is no test
client or server to boot.

## Serve

```sh
uv run uvicorn app:app --reload
```

Then:

```sh
curl -X POST localhost:8000/todos -H 'content-type: application/json' -d '{"title": "try hayate"}'
curl localhost:8000/todos
```
