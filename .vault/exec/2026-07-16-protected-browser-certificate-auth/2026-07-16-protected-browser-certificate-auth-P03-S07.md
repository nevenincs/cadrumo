---
tags:
  - '#exec'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:e873f39dc8570e170bbdd247aec721cebf1c4037f0f66213d9632f9de75d4ff9'
step_id: 'S07'
related:
  - "[[2026-07-16-protected-browser-certificate-auth-plan]]"
---
# Replace synthetic decisive proof and lifecycle coverage with credential-free real browser and process behavior while retaining the external live protected oracle

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/tests`
- `src/cadrumo/adapters/outbound/aeat/browser/tests`

## Description

- Drive exact protected-resource success and refusal branches through a real local HTTP boundary and production Playwright browser sessions.
- Exercise provider ownership, concurrent close, bounded retry, storage-state round trip, cancellation cleanup, and process reaping with real browser resources.
- Delete handwritten recording browser implementations and retain the credential-gated external AEAT protected-resource oracle as a separate acceptance check.

## Outcome

Default credential-free tests now prove the decisive local browser and lifecycle behavior without mirroring provider logic. The external live oracle remains pinned to the canonical protected resource for real AEAT acceptance evidence.

## Notes

Fresh semantic search resolved the shared real HTTP/Playwright boundary, real provider lifecycle tests, and the retained live oracle. Exact policy inventory found no recording, fake, stub, mock, monkeypatch, or xfail implementation in the scoped test trees. The focused six-file matrix passed 44 tests in 101.19 seconds. Independent code review reported PASS with no HIGH or MEDIUM findings.
