---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:ba0d4778148c6a8e60ff41a5a0afc3a2861b322e801bd9b77424ab0ee8e89d4c'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S123` Review

## S123-001 | PASS | Declaration reader remains an authenticated remote mirror, not storage backend selection

The reviewed module is an authenticated AEAT Sede filed-declaration reader. It opens the declarations register, applies the remote read guard, captures AEAT-served register rows, justificante PDFs, declaration PDFs, and submitted-file downloads, then returns normalized observation records to the caller. It does not choose an outbound storage provider, construct secure-object repositories, route SQL storage, or persist its own durable side store.

The active-profile signal is confined to binding the browser session profile name with the current bucket id before opening Playwright. The module reads the encrypted auth session via the session/auth-state boundary and uses `Settings` or `load_settings()` for runtime knobs. No naked environment access was found in the reviewed file.

The plain-file signals are bounded:

- Playwright submitted-file downloads are read from the browser-provided temporary download path and converted to bytes for the returned artefact record.
- Declaration PDFs that require bbox word-position parsing are routed through `_temporary_sensitive_pdf_path()` because the parser needs a real path; the helper uses `mkstemp`, writes through the raw descriptor, closes the descriptor, unlinks the path in `finally`, and converts scratch OS failures into unchained `SedeParseError` instances with the existing translated Sede parse message.

The file's user-facing live navigation/auth failures use `tr()` translated messages on the checked paths, and the Sede error classes derive from the project `AeatError` hierarchy.

Validation:

- the historical check passed with 12 tests.
- the historical check passed.
- Source scans found no secure-object repository construction, storage-provider selection, SQL route setup, naked environment reads, or direct durable file writes in the reviewed module.

Disposition: close `AFR-021` as `remote-mirror`. The temporary PDF scratch path is accepted as parser scratch, not durable sensitive storage, only after the continuation remediation replaced `NamedTemporaryFile(delete=False)` with the private-fd `_temporary_sensitive_pdf_path()` helper, wrapped scratch failures in the central Sede/Aeat exception hierarchy without retaining chained OS exceptions, redacted parser labels, and added focused unlink plus no-chained-exception coverage. The consolidated `S121-S128` review records this as `S123-001 | MEDIUM | closed`.
