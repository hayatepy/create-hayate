# Changelog

All notable changes to create-hayate are documented here.

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
