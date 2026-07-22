"""Cloudflare Python Workers entry: the same app, exposed through the adapter."""

from app import app
from hayate.adapters.workers import to_workers

Default = to_workers(app)
