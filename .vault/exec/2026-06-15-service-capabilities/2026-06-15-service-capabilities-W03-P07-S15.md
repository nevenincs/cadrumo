---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S15'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
  - "[[2026-06-15-service-capabilities-audit]]"
---




# Verify: full focused suite + conformance + honesty review

## Scope

- `close the plan`
- `.vault/audit`

## Description

- Run the focused verification suite (capability core enum, capability resolution, provisioning probes, capability CLI, wizard, locale parity + honesty, documented-command + json-schema conformance): 453 passed.
- Run the full nitpicky (`-n -W`) docs-build gate: 8 passed after fixing the one blocking xref; the new onboarding page builds clean.
- Dispatch an independent fresh-context honesty review (Opus `vaultspec-code-reviewer`) over every sensitive-data egress, the resolver invariants, the probes, and claim-vs-implementation gaps.
- Action every finding: H1 fixed with a conformance test (S16), H2 resolved by H1, M1 deferred (S17), M2 accepted no-op, L1/L2 confirmed sound.
- Persist the close audit, rebuild the feature index, and run the feature vault check (clean).

## Outcome

The `service-capabilities` campaign is structurally complete. The capability backend, resolver (narrow-never-widen, gestor bar), dependency probes, doctor, CLI, wizard, and onboarding doc are landed and verified; every capability-governed egress (cloud upload, on-host vision, Google export across all four write verbs) is gated. Two items are honestly deferred as tracked follow-ups: S09 (lean-core pyproject extras) and S17/M1 (the llm_vision two-mode refusal regression).

## Notes

The full-tree docs gate was briefly red on a peer `_repository.py` `:meth:` xref unrelated to this campaign's onboarding page; fixed forward as an absorbed in-scope regression (commit `402918258`). Two shared-index git incidents during closeout (a peer sweeping staged vault files; a bare `git commit` sweeping peer-staged work) were verified to leave a consistent tree and are recorded in the close audit with the always-use-explicit-pathspec lesson.
