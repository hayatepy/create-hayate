"""$project_name: one Hayate application core for every supported runtime."""

from hayate import URL, Context, Hayate

from contracts import describe
from generated_features import register_features
from identity import principal
from runtime import LOCAL_ENV
from todo_api import register as register_todo_api

app = Hayate(env=LOCAL_ENV)


@app.get("$api_prefix/health")
@describe(summary="Health check", response={"type": "object"}, operation_id="health")
async def health(c: Context):
    return c.json({"status": "ok"})


@app.get("$api_prefix/canonicalize")
@describe(summary="Canonicalize an international hostname", operation_id="canonicalize")
async def canonicalize(c: Context):
    return c.json({"hostname": URL("https://日本語.example/").hostname})


@app.get("$api_prefix/whoami")
@describe(summary="Current request identity", response={"type": "object"}, operation_id="whoami")
async def whoami(c: Context):
    return c.json(principal(c))


register_todo_api(app)
register_features(app)
