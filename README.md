# create-hayate

Project scaffolding for [hayate](https://github.com/hayatepy/hayate) —
`uvx create-hayate my-app` and you have a running, tested project in minutes.

> **Status: design phase.** Nothing installable yet. The internal design memo
> (Japanese, per project convention) lives in [DESIGN.md](DESIGN.md).

## Planned shape

```sh
uvx create-hayate my-app --template workers
cd my-app
uv run pytest        # green out of the box
uv run pywrangler dev
```

- Zero-dependency CLI (stdlib only), templates bundled in the package.
- Templates mirror the upstream `examples/` and are generated + tested in CI,
  so they can't rot.
- v0.1 templates: `api` (uvicorn) and `workers` (Cloudflare Python Workers);
  `lambda`, `mcp`, `auth` follow as those packages ship.

## License

MIT
