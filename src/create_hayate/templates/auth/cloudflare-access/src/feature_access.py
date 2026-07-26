"""Cloudflare Access middleware registration."""

from hayate import Hayate

from cloudflare_access import access_context


def register(app: Hayate) -> None:
    app.use(access_context)
