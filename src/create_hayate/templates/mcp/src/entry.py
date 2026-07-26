"""Cloudflare Python Workers entry: expose the same MCP application."""

from app import app
from hayate.adapters.workers import $workers_adapter

$workers_export
