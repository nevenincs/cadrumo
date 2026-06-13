---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S28'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add a CLI surface for the evidence-driven split suggest and apply flow

## Scope

- `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`
- `src/aeat/entrypoints/cli/_ledger_payloads.py`
- `src/aeat/locales/{en,es,ca,hu}.yml`

## Description

- Add `--llm <provider>`, `--apply`, `--read-evidence`, `--evidence-acknowledged` options to `aeat app ledger split`; route to a new `_ledger_split_llm` helper.
- Suggest path (`--llm` without `--apply`) previews `proposed_children`; apply path (`--apply --yes`) drives `apply_evidence_split`. The manual `--child-amount`/`--child-description` path stays the explicit override and is refused alongside `--llm`; `--apply` without `--yes` is refused.
- Extend `LedgerSplitResult` with optional LLM preview/apply fields plus a `LedgerSplitChildProposalPayload`. Add five split LLM locale keys across all four catalogues.
- Make `LLMSplitProposer` `runtime_checkable` so `resolve_split_proposer` narrows on the protocol, enabling a registered in-process proposer to drive the full CLI path offline.

## Outcome

Commit `d34bcd736`. Real-behaviour CLI integration test `test_ledger_llm_split` (4 tests) covers suggest/apply/refusals end to end. Documented-command-conformance (42) and JSON-schema conformance gates green; locale parity + honesty green.

## Notes

`--read-evidence` stays opt-in and gestor-barred per the cloud-consent posture.
