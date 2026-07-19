---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S15'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove the removed replay and evidence-patch spellings are absent from every source and generated surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

- Flip `test_modelo_audit_verbs_only_register_canonical_four` to `..._three`: move `replay` from the accepted-leaf set into the forbidden-leaf set, proving the audit group now registers only show/check/export and refuses `replay`.
- Add `test_ledger_link_rejects_retired_evidence_id_grammar` proving `ledger link --evidence-id` no longer resolves.
- Correct the stale docstring in `test_root_does_not_register_bare_run_alias` that referenced `aeat app modelo audit replay`.

## Outcome

- The removed replay command and the removed `link --evidence-id` grammar are proven absent at the live CLI surface. `test_root_grammar_invariants.py`: 8 passed (integration). Commit `dc5982eee5`.

## Notes

- This is the source-surface absence proof; the generated CLI reference/tree regenerate against the live surface (already green) and the doc `.seq` citation of `link --evidence-id` was removed in S07. The locale-value absence of `--evidence-id` in the `link` help/error strings is part of the deferred S13 locale cleanup, held own-keys-only until the operator commits the live P04-door locale WIP and the `.yml` goes clean.
