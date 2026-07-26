"""Cloudflare Python Workers entry: the same app, exposed through the adapter."""

from app import app
from hayate.adapters.workers import $workers_adapter

$workers_export
