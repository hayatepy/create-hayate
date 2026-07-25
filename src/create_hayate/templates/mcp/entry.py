"""Cloudflare Python Workers entry: expose the same MCP application."""

from app import app
from hayate.adapters.workers import to_workers

Default = to_workers(app)
