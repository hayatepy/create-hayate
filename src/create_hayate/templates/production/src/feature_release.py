"""Response-to-release correlation for every production response."""

from hayate import Context, Hayate, Next

from release_metadata import release_metadata


async def _release_headers(c: Context, next_: Next) -> None:
    app_version, worker_version = release_metadata(c.env)
    if app_version is not None:
        c.header("x-app-version", app_version)
    if worker_version is not None:
        c.header("x-worker-version", worker_version)
    await next_()


def register(app: Hayate) -> None:
    app.use(_release_headers)
