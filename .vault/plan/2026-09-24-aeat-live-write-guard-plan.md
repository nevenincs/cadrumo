---
tags:
  - '#plan'
  - '#aeat-live-write-guard'
date: '2026-09-24'
tier: L1
related:
  - '[[2026-10-03-aeat-live-write-guard-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:156a4e54f149a87156fe840df661ed5e41e58928327f27d9969c707e741870a0'
---

# `aeat-live-write-guard` plan

Make the no-live-AEAT-write guarantee enforced at the CLI and at the browser factory, not only where each reader remembers to check.

## Description

Approved 2026-09-24. Basis: the coordinator's approval of the investigation's steps 1 to 4 under the operator's standing authorisation.

The guarantee that the product never writes to AEAT without transaction-specific authorisation holds today through `SubmissionEngine` exposing no transport, `evaluate_remote_operation` in `src/cadrumo/domain/calculations/registry/remote_state_guard.py` refusing non-read requests, write-word URLs and unlisted browser actions for readers that call it, and the MCP policy blocking `live_write` commands. Two gaps remain: the CLI accepts a command declared `live_write` and only MCP refuses one, and the browser factory has no request-level guard, so a reader that forgets `assert_read_http_for` is unguarded. The operator-surface `live_submission_enabled` flag states the property but nothing reads it. S01 removes the dead flag and makes the CLI refuse through `AeatAccessGate.require_live_write`; S02 adds the defence-in-depth guard at the factory.

Decision coverage: this enforces an existing project rule (sensitive financial data and live writes) with no new decision, so no ADR governs.

## Steps

- [x] `S01` - delete the unread live_submission_enabled flag, its validator, its locale-contract test and its guard exemption, make CLI dispatch refuse every live_write command through AeatAccessGate.require_live_write, and turn the accepting command-policy test into a refusal plus a planted CLI command test; `src/cadrumo/application/operator_surface/models.py, src/cadrumo/entrypoints/cli command runtime and policy validation`.
- [ ] `S02` - route every browser-context request and every Playwright API request through the union of the context's declared remote-state guard policies, via the context route and a guarded API request client with a static gate against direct .request use, aborting refused requests with redacted logging and no bypass, after declared read requests are grounded by the live capture, so an AEAT reader that forgets its guard is still refused, proven by a test with such a reader; `src/cadrumo/adapters/outbound/aeat/browser/session.py, a new public module in src/cadrumo/adapters/outbound/aeat/browser, src/cadrumo/domain/calculations/registry/remote_state_guard.py, sede/notifications.py, sede/walker.py, sede/_declarations_fetch.py`.

## Parallelization

S01 and S02 cover separate enforcement boundaries: CLI dispatch and the browser factory. S02 must ground declared read requests in the live capture before the factory guard is enabled; the CLI refusal can proceed independently.

## Verification

S01 passes when CLI dispatch refuses every command declared live_write through AeatAccessGate.require_live_write and a planted command test proves the refusal. S02 passes when context and Playwright API requests both use the union of declared guards, direct .request use is statically refused, and a reader that omits its own guard is refused with redacted logging and no bypass.
