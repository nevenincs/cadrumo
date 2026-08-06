---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:1ec1ede79b518be025cd6af50318df0800af3ac480657528ec6695d043426e5f'
step_id: 'S93'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove telemetry UTF-8 digests against known vectors and retained-record roundtrip

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_telemetry_retention.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` added the proof against oracles outside `core.hashing` in the same change that delegated the telemetry content digest (S92).

- Prove `content_sha256` reproduces the published NIST FIPS 180-4 "abc" worked-example vector.
- Prove a retained telemetry record built from that same input carries the identical digest through a real filesystem-backed roundtrip.

## Outcome

`test_telemetry_retention.py` asserts `content_sha256("abc") == "ba7816bf...ad"` (line 135, the literal NIST FIPS 180-4 Appendix B.1 digest) and drives `SessionTelemetryWriter.record` with the same `"abc"` text against a real filesystem-backed writer, asserting the retained record's digest matches (lines 141-153). Neither assertion is derived from the `sha256_hex` call under test.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/entrypoints/mcp/tests/test_telemetry_retention.py` reports 10 passed.

## Notes

This record was authored after the proof had already landed; it documents the verified state rather than performing new implementation work. The retention roundtrip exercises the real writer against the filesystem rather than a test double.
