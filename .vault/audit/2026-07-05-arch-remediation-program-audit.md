---
tags:
  - '#audit'
  - '#arch-remediation-program'
date: '2026-07-05'
modified: '2026-07-08'
related:
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-03-arch-remediation-registry-format-audit]]"
---

# `arch-remediation-program` audit: `Wave 4 closure honesty review`

## Scope

Fresh-context Wave 4 closure honesty review for the architecture remediation
program. The review treated the program as newly inherited: re-read the program
ADR intent, rechecked the D9 tail plans and every architecture-remediation track
plan through `vaultspec-core vault plan status`, reran the deferred
registry-format filing-grade suite, rebuilt the new program feature index, ran
feature checks for the D9 and architecture-remediation features, verified provider
sync with `vaultspec-core sync --dry-run --json`, and exercised the ratchet gates
called out by the program ADR.

This audit authors no new plan and no new ADR. It records whether the current
tree can honestly declare the program closed.

## Findings

### ratchet-gates-red | high | Program closure is blocked by current-tree ratchet failures

The Wave 4 ratchet gate bundle is red on the current tree. The first run,
`uv run --no-sync pytest -q src/aeat/tests/test_import_hygiene_gate.py
src/aeat/tests/test_importlinter_ledger.py
src/aeat/tests/test_lazy_import_policy.py
src/aeat/tests/test_data_size_budget.py
src/aeat/tests/test_codebase_size_budgets.py
src/aeat/tests/test_wheel_content_boundary.py
src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`, failed with 7 failed
and 31 passed in 55.09s. The required sequential rerun of the failing tests with
`-n 0` reproduced all 7 failures in 11.06s, so this is not a parallel-loader
artefact. The failures are: application-to-adapters pinned edges 850 > baseline
840; lazy-import allowlist edges 493 > ceiling 488; unsanctioned lazy-import site
counts `ADAPTER_INTERNAL_DEFERRAL` 191 > 176, `CORE_INTERNAL_DEFERRAL` 41 > 35,
and `APPLICATION_DEFERRAL` 605 > 516; undeclared lazy-import edges; 17 module
size-budget offenders; and 11 callable size-budget offenders. The logs are in
`var/log/arch-remediation-program-ratchets-20260705.log` and
`var/log/arch-remediation-program-ratchets-sequential-20260705.log`.

Disposition: BLOCKER TO PROGRAM CLOSURE. The program ADR says every ratchet must
be zero or frozen by an accepted ADR before Wave 4 closure. The current state
satisfies neither condition for these ratchets. This audit does not edit the
contended hub files or rebaseline ratchets; the fix needs an owning ratchet
reconciliation follow-up that either shrinks the counts back under their gates or
lands an accepted ADR deliberately freezing the new ceilings.

### deferred-filing-suite-rerun-cleared | low | Registry-format filing-grade gate now passes

The registry-format audit's deferred Wave 4 item is cleared. The focused
M303/M369 filing-grade bundle ran through pytest:
`uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_369_registry.py
src/aeat/domain/calculations/registry/tests/test_modelo_303_registry.py
src/aeat/application/filing/tests/test_modelo_303_390.py
src/aeat/application/filing/tests/test_fichero_boe_completeness_parity.py
src/aeat/adapters/outbound/aeat/export/_formats/tests/test_fichero_boe_modelo_303.py
src/aeat/adapters/outbound/aeat/export/_formats/tests/test_record_specs.py
src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary_m369.py
src/aeat/adapters/inbound/declaracion/tests/test_verification_chain_m369.py
src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary_m303.py
src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary_m303_historical.py
src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary_m303_2023_2024.py
src/aeat/adapters/inbound/declaracion/tests/test_verification_chain_m303_parser.py
src/aeat/adapters/inbound/declaracion/tests/test_verification_chain_m303_historical.py
src/aeat/adapters/inbound/declaracion/tests/test_verification_chain_m303_2023_2024.py
src/aeat/adapters/inbound/declaracion/tests/test_m303_primitive_anti_tautology.py`.
Result: 171 passed in 59.26s. The full output is in
`var/log/arch-remediation-registry-format-filing-suites-20260705.log`.

### plan-and-exec-status-clean | low | D9 and architecture-remediation track plans are structurally complete

Current `vaultspec-core vault plan status --json` results show the three D9 plans
complete with no missing exec records: `binding-vocabulary-cli-cohesion` 27/27,
`binding-resolver-contract-unification` 21/21, and
`silent-zero-base-aggregation` 18/18. The architecture-remediation tracks are
also complete with no missing exec records: gates-ratchet 12/12,
engine-lifecycle 11/11, modelo-surface 21/21, ports-inversion 20/20,
crash-window 16/16, source-kind-deferrals 9/9, registry-format 18/18,
lazy-import-policy 6/6, and data-budget 5/5.

The two live IVA follow-up plans remain intentionally not closed:
`live-iva-compensation-wallet` is 101/102 with `W06.P15.S56` open, and
`iva-compensation-chain` is 8/9 with `P03.S01` open. Those rows were already
formally deferred to the standing live-operator evidence/privacy blocker; this
audit does not change that disposition.

### feature-index-and-provider-sync-clean | low | Vault metadata and generated provider outputs are in sync

After adding this audit, `vaultspec-core vault check features --feature
arch-remediation-program` reported the program index stale. The index was rebuilt
with `vaultspec-core vault feature index -f arch-remediation-program`, and the
program feature check then reported clean. Current feature checks are clean for
the three D9 features, `arch-remediation-program`, `aeat-architecture-review`,
and every architecture-remediation track feature. A dry-run provider sync,
`vaultspec-core sync --dry-run --json`, returned `status: unchanged`; grouped
outcomes were antigravity 101 unchanged, claude 111 unchanged, codex 100
unchanged, and gemini 111 unchanged.

### codification-already-covered | low | Commit-sweep lesson is already rule-covered

The registry-format close audit recommended promoting the
`campaign-commits-never-ride-bulk-sweeps` lesson. Current rule search shows the
lesson is already covered by `subagent-commits-require-explicit-pathspec` and
`uncommitted-wip-is-not-orphaned` in both source and generated rule outputs: a
bare `git commit` can sweep peer-staged work, while explicit pathspec or the
verified-index path is required for authored work. No new rule is needed from
this audit.

### external-deferrals-remain-owned-elsewhere | low | Non-program residuals stay routed to their existing owners

The modelo-surface close audit's M210 source-hash mismatch remains a legal/IRNR
corpus hash reconciliation follow-up, not a modelo-surface or program-closure
repair. The live IVA wallet and IVA compensation chain positive-live-evidence
items remain formally deferred to the live operator evidence/privacy gate. These
items are recorded here so they are not mistaken for silently dropped program
work, but they are not repaired in this Wave 4 audit.

### ratchet-size-tail-cleared-import-policy-remains-red | high | Size ratchet is green; import ratchets still block closure

The 2026-07-05 ratchet follow-up series cleared the codebase-size module and
callable failures without rebasing ceilings. The final `codebase-size` gate
passed cleanly after the M131 formula-runtime split, and the gates-ratchet audit
now records the size-tail closure evidence. Re-running the full Wave 4 ratchet
bundle afterwards produced 5 failed and 33 passed; the required sequential rerun
of the failing tests reproduced the same 5 failures. The remaining blockers are
the import-linter application-to-adapters pin count and the lazy-import policy
allowlist/site-count gates. Logs:
`var/log/arch-remediation-program-ratchets-after-followups-20260705.log` and
`var/log/arch-remediation-program-ratchets-after-followups-sequential-20260705.log`.

## Recommendations

- Do not declare the architecture-remediation program closed while
  `ratchet-gates-red` remains true.
- Treat the registry-format filing-suite deferral as cleared.
- Treat the D9 source-kind/resolver freeze as liftable: all three D9 target
  plans are 100% complete with no exec alerts.
- Open or route a ratchet reconciliation follow-up for the lazy-import policy,
  and import-linter pinned-edge count. Closure requires those gates green, or an
  accepted ADR freezing the new ceilings.
- Do not promote a new commit-sweep rule from this audit; the existing explicit
  pathspec and uncommitted-WIP rules already carry the durable lesson.
