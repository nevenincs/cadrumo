---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:afc3223c74a094fa1fd411db22188c54f0a98fe500379ff2688d8dd5775e4755'
step_id: 'S43'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Make page-coherence seed execution once-per-page with verified seed identity, immutable seed captures, and actionable fail-closed diagnostics while preserving isolated sequence semantics.

## Scope

- `dev/docs/sequences`
- `dev/docs/sequences/tests`

## Description

- Ground the page lifecycle in the accepted once-per-page seed ruling and the live sequence runner.
- Retain an invocation-local seed context carrying the verified definition, executed frames, and immutable captured values.
- Reuse repeated same-name seeds and differently named execution-equivalent seeds without replaying their side effects.
- Warn and fail closed when one identity diverges or a requested seed has no inlined state or resolved captures.
- Keep standalone sequence execution, transcript shape, expectations, goldens, product ledger refusal, and page isolation unchanged.
- Cover the lifecycle with real CLI execution against encrypted sandbox storage.

## Outcome

Page coherence now executes each verified seed premise once per page root. Repeated seeds project the first execution and its captured values into the later sequence transcript, so expectation alignment and isolated golden semantics remain intact while non-idempotent evidence creation is not replayed. Equivalent executable recipes under distinct names share state only after a narration-independent structural fingerprint agrees; a name collision with changed executable content warns and refuses.

The focused lifecycle suite passed six real integration tests. Ruff check and format check passed on the package facade, runner, and tests. Page coherence passed for `how-to/first-quarterly-filing`, `how-to/review-calculation-values`, `how-to/modelo-130`, and `how-to/modelo-303`. The first Modelo 130 attempt encountered the repository's explicit concurrent-registry fingerprint refusal before sequence execution; its settled rerun passed.

## Notes

`how-to/verification-reports` now passes the repeated-seed execution path, including the equivalent `autonomo-irpf-2026` and `iva-evidence-2026` recipes, but its discovery tier remains red because `verification-reports-modelo-303` declares `evidence_id` in both its seed and body. That contract repair and the complete fourteen-isolated/five-page matrix remain in P03.S41; S41 stays open. No golden, product ledger behavior, branch, index, commit, or worktree was changed for this step.
