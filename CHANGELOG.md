# Changelog

All notable changes to create-hayate are documented here.

## Unreleased

## [0.6.0] - 2026-07-27

### Added

- Add an independent `--frontend none|htmx|react|astro` generation-plan axis
  while preserving `none` as the compatibility default.
- Compose frontend-owned trees after every backend layer and reject frontend
  collisions before a partial project can survive.
- Add isolated profile metadata boundaries and fail-fast production
  compatibility constraints for the upcoming executable frontend profiles.
- Generate an executable Hayate + htmx profile with shared JSON/HTML domain
  logic, safe Jinja page/fragment rendering, CRUD validation, history, SSE,
  identity and CSRF boundaries, and responsive starter UI.
- Pin the reviewed hayate-htmx 0.1 release-gate commit and self-host htmx
  2.0.10 with recorded SHA-256/SRI, ASGI serving, Cloudflare Static Assets,
  direct tests, Chromium smoke tests, and a real workerd contract.
- Install the immutable hayate-htmx Git source on ASGI and bundle the same
  license-preserving source snapshot on Workers until Pywrangler can consume
  its VCS lock or the package is published.
- Regenerate a deterministic Jinja `DictLoader` module from canonical HTML
  before Workers commands, retaining editable file templates locally without
  relying on unsupported arbitrary files in the Python module bundle.
- Generate typed UUID path and response contracts from `hayate-openapi` 0.5
  for OpenAPI-enabled TODO APIs, while preserving the dependency-light
  Context-first implementation in minimal projects.

### Changed

- Add shared todo title normalization and update/toggle storage operations so
  API, htmx, in-memory, SQLite, and D1 compositions use one domain contract.
- Split TODO API registration into an overlay boundary so optional features
  can improve transport contracts without duplicating the application shell.

### Fixed

- Keep the generated Chromium smoke strict while accepting the one
  `net::ERR_ABORTED` signal produced when the completed SSE demo deliberately
  closes its `EventSource`.

## [0.5.1] - 2026-07-27

### Fixed

- Require hayate-openapi 0.4.2 so generated raw JSON Schema contracts are
  enforced at runtime as well as projected into OpenAPI without initializing
  the schema compiler in forbidden Workers global scope.
- Reject malformed TODO UUID route parameters in the shared application even
  without the OpenAPI feature, keeping the base scaffold lightweight while
  preserving the same public behavior across compositions.

## [0.5.0] - 2026-07-27

### Changed

- Generate projects on Hayate 0.12.1+ and hayate-openapi 0.4, completing the
  shared runtime/OpenAPI validation contract for JSON bodies and route
  parameters while retaining route middleware on the native Workers fast path.
- Reject malformed JSON through the core RFC 9457 validation path and emit the
  UUID route-parameter schema from the same generated application.
- Resolve and import all 42 supported compositions against the released
  package lines.

## [0.4.3] - 2026-07-27

### Changed

- Generate MCP and production projects on the released hayate-mcp 0.11 line,
  preserving MCP 2025-11-25 and existing Bearer/Cloudflare Access defaults.
- Check installed distribution metadata against the public `__version__`
  during ordinary CI. The signed v0.4.2 tag was rejected by this release
  invariant before build and was never published.

## [0.4.1] - 2026-07-26

### Changed

- Link generated projects and the published package description to the
  canonical ecosystem start page, production golden app, and tested
  compatibility evidence.

## [0.4.0] - 2026-07-26

### Added

- Add composable `openapi`, `mcp`, and `sql` feature generators plus explicit
  `none` and `cloudflare-access` identity strategies.
- Add a production preset that joins API routes, hardened Scalar docs, typed
  client export, MCP 2025-11-25, Access identity, D1, native rate limiting,
  CORS, security headers, and a deployment checklist.
- Test all 40 supported runtime/feature/auth/entrypoint combinations plus both
  production entrypoints for dependency resolution and import compatibility.
- Exercise the golden preset over real ASGI with SQLite and real workerd with
  D1, including an authenticated HTTP write read back through MCP.

### Changed

- Replace copied full application templates with one base app, one Workers
  runtime overlay, and small feature components. The `mcp` template is now a
  compatibility shortcut for `workers` plus the MCP component.
- Reject unsupported combinations before writing a destination directory and
  explain the compatible alternative.

## [0.3.0] - 2026-07-26

### Changed

- Align every generated project with Hayate 0.11.1+, whose lazy runtime
  adapter exports make the documented Workers exclusions deployable.
- Keep the feature-complete `WorkerEntrypoint` class as the Workers default
  while exposing the HTTP-only global handler through the explicit
  `--workers-entrypoint global` option.
- Reduce Workers uploads with safe module exclusions while retaining `uts46`;
  document the package-metadata trade-off and verify internationalized
  hostname behavior through real workerd.
- Record Wrangler's dry-run upload size and successful HTTP/MCP contract
  payloads in the real-workerd CI gate.

## [0.2.0] - 2026-07-25

### Added

- Add an `mcp` template with MCP 2025-11-25, input/output JSON Schema
  validation, request context, direct application tests, and one application
  that runs unchanged on ASGI and Cloudflare Python Workers.
- Exercise generated MCP projects through real workerd in CI without requiring
  `hayate-auth`, so existing identity providers remain a first-class path.
- Keep generated Workers launchers compatible with current Node.js 24 by
  filtering Pywrangler's obsolete experimental WASM flag.

## [0.1.3] - 2026-07-25

### Fixed

- Align generated Workers projects with workerd's Python 3.13 runtime and
  Pywrangler's supported Node.js 24 release.
- Add a cross-platform Workers launcher that rejects unsupported Node
  runtimes before Pywrangler can silently create an incomplete dependency
  bundle, and exercise that documented command against real workerd in CI.

## [0.1.2] - 2026-07-24

### Changed

- Generate the Workers template in CI and drive its CRUD API through a real
  workerd process, in addition to the direct application tests.
- Mark the distribution as typed and validate the public source with strict
  mypy.
- Audit locked dependencies on every change and publish an SPDX SBOM plus
  GitHub build and SBOM attestations with each release.

## [0.1.1] - 2026-07-24

### Changed

- Align package metadata, CI, documentation, and the protected release path
  for the public 0.1 line.

## [0.1.0] - 2026-07-22

### Added

- Add a zero-dependency CLI with bundled API and Cloudflare Workers templates,
  generated-project tests, and non-interactive operation.
