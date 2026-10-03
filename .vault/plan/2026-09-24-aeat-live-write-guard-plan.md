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
body_hash: 'sha256:3e45e41239e1e76ff228132175568a62cee6893d92edcee85960735b091cae62'
---

# `aeat-live-write-guard` plan

Make the no-live-AEAT-write guarantee enforced at the CLI and at the browser factory, not only where each reader remembers to check.

## Description

Approved 2026-09-24. Basis: the coordinator's approval of the investigation's steps 1 to 4 under the operator's standing authorisation.

The guarantee that the product never writes to AEAT without transaction-specific authorisation holds today through `SubmissionEngine` exposing no transport, `evaluate_remote_operation` in `src/cadrumo/domain/calculations/registry/remote_state_guard.py` refusing non-read requests, write-word URLs and unlisted browser actions for readers that call it, and the MCP policy blocking `live_write` commands. Two gaps remain: the CLI accepts a command declared `live_write` and only MCP refuses one, and the browser factory has no request-level guard, so a reader that forgets `assert_read_http_for` is unguarded. The operator-surface `live_submission_enabled` flag states the property but nothing reads it. S01 removes the dead flag and makes the CLI refuse through `AeatAccessGate.require_live_write`; S02 adds the defence-in-depth guard at the factory.

Decision coverage: this enforces an existing project rule (sensitive financial data and live writes) with no new decision, so no ADR governs.

## Steps

- [x] `S01` - delete the unread live_submission_enabled flag, its validator, its locale-contract test and its guard exemption, make CLI dispatch refuse every live_write command through AeatAccessGate.require_live_write, and turn the accepting command-policy test into a refusal plus a planted CLI command test; `src/cadrumo/application/operator_surface/models.py, src/cadrumo/entrypoints/cli command runtime and policy validation`.
- [ ] `S02` - route every browser-context request through the union of the context's declared remote-state guard policies, aborting refused requests with redacted logging and no bypass, after declared read requests are grounded by the live capture, so an AEAT reader that forgets its guard is still refused, proven by a test with such a reader; `src/cadrumo/adapters/outbound/aeat/browser/session.py, a new public module in src/cadrumo/adapters/outbound/aeat/browser, src/cadrumo/domain/calculations/registry/remote_state_guard.py`.

## Parallelization

## Verification
