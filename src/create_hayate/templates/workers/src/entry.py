"""Cloudflare Python Workers entry: the same app, exposed through the adapter."""

from hayate.adapters.workers import $workers_adapter

from app import app

$workers_export
