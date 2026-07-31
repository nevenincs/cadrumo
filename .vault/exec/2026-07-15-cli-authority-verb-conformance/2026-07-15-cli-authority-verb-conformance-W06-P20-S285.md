---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:c7ac838a4de6451d63c26d9a86a60135c3e8ddad6f9325a25671e49b7c7dd23b'
step_id: 'S285'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Ground the HITL confirmation key against the live descriptor set at the gate itself, so the permissive default cannot auto-approve an unclassified mutation if a future caller passes an unvalidated key

## Scope

- `src/cadrumo/entrypoints/mcp/_hitl.py`

## Description

- Ground the HITL confirmation gate `confirmation_for_tool` in `_hitl.py` against the live descriptor set at the gate itself, so its safety no longer depends on every caller passing a validated key.
- Add a cached `_live_command_keys` helper returning the exposed descriptor command keys via a deferred import of the descriptor builder (avoiding a module-load cycle; the descriptor set is process-stable).
- Order the tiers so BLOCK and CONFIRM fire from the declared classification first (a declared live-write or destructive verb still resolves correctly, even when unexposed), then ground only the AUTO_APPROVE fall-through: a key that reached auto-approve solely by classifying all-false through the permissive default and names no exposed command is refused with a `ValueError` rather than silently auto-approved.
- Add a hostile-input test asserting a bogus unclassified key now raises rather than returning AUTO_APPROVE, and a counterpart test asserting real exposed read and non-destructive-mutation commands still auto-approve, so the refusal is scoped to unclassified keys.

## Outcome

Verified at HEAD `1437055950f5b8f4082d323578294fc32ad1d9fe`.

Command: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/entrypoints/mcp/tests/test_hitl_and_live_write.py` — `7 passed in 8.62s`.

Broader consumer regression sweep (annotations, risk-table parity, identity gate, elicitation, meta-tools, operator_surface, and the confirmation / active-profile / identity-switch / lifecycle agent-eval goldens): `143 passed in 66.52s`. The permanent live-write BLOCK rail still fires for a declared (unexposed) `modelo.work.submit`, confirming the tier ordering.

Direct behavioural proof: a bogus key returns `AUTO_APPROVE` before the fix and raises `ValueError` after; `ledger.remove` and `modelo.work.file` still resolve `CONFIRM`, `modelo.work.submit` (declared live-write) still `BLOCK`.

Mutation-check per added assertion (throwaway rebind probe; real passes, defect fails):

- `unclassified key refused (raises ValueError)`: real_passes=True; grounding-removed defect (descriptor set includes the bogus key) → returns AUTO_APPROVE, no raise → defect_fails=True.
- `grounding still auto-approves real exposed commands`: real_passes=True; over-aggressive-grounding defect (empty descriptor set) → real command raises → defect_fails=True.

Both HITL mutation probes reported OK. `ruff check` and `ruff format --check` clean on both touched files.

## Notes

`confirmation_for_tool`'s signature is unchanged (`command_key` only), so the agent-eval golden's structural signature assertion still holds. The full MCP test package showed 6 failures under parallel execution in the command-search and corpus-search lexical-retrieval suites; those pass under `-n0` and touch neither the HITL nor the classification surface, so they are a shared-index parallelism artefact, not feature-owned.
