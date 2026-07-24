# $project_name

A TODO API built with [hayate](https://github.com/hayatepy/hayate), deployed
to [Cloudflare Python Workers](https://developers.cloudflare.com/workers/languages/python/).
The app core is runtime-agnostic — the same `app.py` runs on any ASGI server too.

## Test

```sh
uv run pytest
```

Tests call the app core directly (`await app.request(...)`); no server or
workerd needed.

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
