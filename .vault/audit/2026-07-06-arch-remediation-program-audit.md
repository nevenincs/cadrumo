---
tags:
  - '#audit'
  - '#arch-remediation-program'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:d48e027d2f037142a9c52ba38b0bc8c9972f9370c09de489bad726bd06583c54'
related:
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-05-arch-remediation-program-audit]]"
  - "[[2026-07-02-arch-remediation-gates-ratchet-plan]]"
---

# `arch-remediation-program` audit: `ratchet refresh after import-tail reconciliation`

## Scope

Current-tree refresh of the 2026-07-05 Wave 4 closure honesty audit after the
ratchet follow-up commits landed. This pass rechecked the program's known
closure blockers against HEAD: D9 plan status, every arch-remediation track
plan status, the Wave 4 ratchet bundle, feature-check diagnostics for the
program and gates-ratchet features, release-readiness state, and open plan rows.

This audit does not author a new plan or ADR. It records which blockers from
the prior audit are now stale, which remain live, and which are outside local
code-work scope.

## Findings

### ratchet-gates-currently-green | low | Prior ratchet blocker is stale at current HEAD

The 2026-07-05 audit's `ratchet-gates-red` and
`ratchet-size-tail-cleared-import-policy-remains-red` findings no longer
describe the current tree. After the size and import-tail reconciliation
commits, the Wave 4 ratchet bundle now passes:

`uv run --no-sync pytest -q src/aeat/tests/test_import_hygiene_gate.py
src/aeat/tests/test_importlinter_ledger.py
src/aeat/tests/test_lazy_import_policy.py
src/aeat/tests/test_data_size_budget.py
src/aeat/tests/test_codebase_size_budgets.py
src/aeat/tests/test_wheel_content_boundary.py
src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`

Result: 38 passed in 52.72s. The current log is
`var/log/arch-remediation-ratchets-current.log`.

No ratchet ceiling was raised for this closure. The last import-tail commit
rewrote private production imports onto the existing public
`application.user_profile` facade, renamed private-looking test support modules
to public test-support names, and updated the corresponding `.importlinter`
pinned edges. Focused evidence also passed before the bundle rerun:
`src/aeat/tests/test_import_hygiene_gate.py` reported 11 passed, and scoped
`ruff check` on the touched import-boundary paths reported clean.

Disposition: the code-gate blocker recorded in the prior audit is cleared for
the current tree. Future audits should treat the current ratchet bundle log as
the live evidence, not the stale 2026-07-05 red logs.

### plan-status-remains-complete | low | D9 and arch-remediation track plans are still structurally complete

Current `vaultspec-core vault plan status` output still reports all three D9
plans complete: `binding-vocabulary-cli-cohesion` 27/27,
`binding-resolver-contract-unification` 21/21, and
`silent-zero-base-aggregation` 18/18.

The architecture-remediation track plans are likewise complete:
`gates-ratchet` 12/12, `engine-lifecycle` 11/11, `modelo-surface` 21/21,
`ports-inversion` 20/20, `crash-window` 16/16,
`source-kind-deferrals` 9/9, `registry-format` 18/18,
`lazy-import-policy` 6/6, and `data-budget` 5/5. A direct open-row grep over
`.vault/plan` found no unchecked plan rows.

Disposition: there is no current open plan-row tail in the D9 or
arch-remediation plan set. The formal deferrals recorded inside some checked
exec records remain governed by their named follow-up triggers; this status
does not promote a deferred source kind or claim a resolver convention that the
source-kind deferral ADR still freezes.

### gates-ratchet-same-feature-adr-warning | medium | Vault metadata still carries a governance warning

The current feature check for `arch-remediation-gates-ratchet` reports one
non-fixable warning: the feature has a plan but no same-feature ADR. The plan is
related to the accepted program ADR, and the program ADR explicitly orders Wave
0 instruments, but the feature checker requires a same-feature ADR surface.

This is not a code ratchet failure: the Wave 4 ratchet pytest bundle is green.
It is also not appropriate to mint a mechanical ADR in this pass. The ADR
workflow requires related research and explicit user approval before creating a
new decision record; suppressing the warning by hand-tagging the program ADR
with a second feature tag would violate vault frontmatter rules.

Disposition: program closure can no longer be blocked on red ratchet tests, but
the `arch-remediation-gates-ratchet` feature remains not fully clean at the
vault metadata/governance layer until the coordinator either accepts a
same-feature ADR/research follow-up or explicitly accepts the program ADR as the
governing parent despite the checker warning.

### release-readiness-charter-blocker-remains-external | medium | Release readiness is still blocked by the permanent safety charter issue

`just release-readiness` still blocks on one open `priority:P0-blocker` issue:
`#116 Live-AEAT-write safety charter - never file a test return`. The current
issue body says the charter stays open permanently as the reference pointer, and
the release-readiness ADR and exec record intentionally treat a genuinely open
`priority:P0-blocker` issue as a hard release blocker.

Disposition: this is not a local code defect to "fix" under the architecture
remediation program. Clearing it requires a coordinator-owned GitHub label/gate
policy decision, not source changes in this worktree.

## Recommendations

- Treat the prior red ratchet findings as stale for current HEAD; the ratchet
  code-gate blocker is cleared by the 38-pass bundle.
- Do not create a gates-ratchet ADR solely to silence the feature checker.
  Follow the ADR workflow: related research first, then explicit user approval.
- Do not claim repo release readiness while `just release-readiness` remains
  blocked by issue `#116`; route that to release-policy ownership.
- Keep the D9 freeze lifted for the three target plans only: they remain 100%
  complete, while future deferred source-kind promotions still require their
  own trigger evidence and accepted design authority.
