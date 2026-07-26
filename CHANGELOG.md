# Changelog

All notable changes to create-hayate are documented here.

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
