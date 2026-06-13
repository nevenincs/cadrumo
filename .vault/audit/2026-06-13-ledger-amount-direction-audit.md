---
tags:
  - '#audit'
  - '#ledger-amount-direction'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-10-ledger-amount-direction-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ledger-amount-direction with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ledger-amount-direction` audit: `C1 suite green-pass triage: S15 owner-vs-peer`

## Scope

Close the single remaining unchecked Step of the C1 plan, `P05.S15` (run the
full `src/aeat` pytest suite sequentially; confirm zero failures; fix any
in-scope regressions). Determine whether the item is stale, already satisfied,
blocked, or real remaining work, without any broad ledger change. All other
Steps (`P01`–`P04`, `P05.S16`) were already checked; the rule
`ledger-amount-is-absolute-direction-is-authority` is codified and synced.

## Findings

### F1 — The C1 owner surface is fully implemented and green (satisfied)

Verified every C1 obligation is live in source, not just checked on paper:
`RawTransaction.amount` carries a non-negative gate
(`src/aeat/domain/transactions/_raw_transaction.py`); `_direction_from_amount`
is deleted with no call site remaining in `src/aeat/application/ledger/`;
`LedgerEvidenceRow.amount` / `value_in_eur` carry a non-negative
`field_validator` (`src/aeat/domain/modelos/_ledger_filing_snapshot.py`); the
CLI `--amount` guard is present (`src/aeat/entrypoints/cli/_ledger.py`). The
owner-scoped test surface — transactions domain tests, ledger application tests,
the CLI ledger tests, and the evidence-row roundtrip + anti-tautology proof —
runs **427 passed, 0 failed**. S15's actual intent (confirm C1 introduced no
regressions) is satisfied.

### F2 — Full `src/aeat` tree is red from 11 peer/governance gates, none owned by C1 (blocked)

`uv run --no-sync pytest src/aeat -n auto -q` finished **11 failed, 15291
passed, 4 skipped** in 15m56s. The 11 failures are all standing repo-wide
governance ratchets, not behaviour tests, and none belong to the
ledger-amount-direction surface:

- `test_cli_module_size::test_production_cli_modules_do_not_grow_into_new_monoliths`
- `test_codebase_size_budgets::test_tracked_python_modules_do_not_exceed_line_budgets`
- `test_codebase_size_budgets::test_tracked_production_callables_do_not_exceed_line_budgets`
- `test_config::TestEnvExampleAlignment::test_settings_fields_documented_in_env_example`
- `test_docstring_core_struct_links::test_modules_that_use_a_core_struct_link_it`
- `test_docstring_core_struct_links::test_public_functions_link_anchor_parameters`
- `test_docstring_return_type_links::test_public_functions_link_their_aeat_return_type`
- `test_marker_integrity::test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata`
- `test_parity::test_codebase_to_locale_parity`
- `test_relative_imports_only::test_no_absolute_self_imports_in_aeat_package`
- `test_utf8_enrollment_inventory::test_no_bare_utf8_literals_in_production_files`

The prior-day closeout (`P05-S15-attempts`, 2026-06-12) hit two `-x` blockers —
a flaky `test_verify_grants_when_required_casillas_supplied_m130` (passed in
isolation) and a real sibling-owned persistence-fixture failure,
`test_modelo_catalogue_defaults_isolate_bucket_writes` (accepted `ModeloRecord`
required `external_evidence`). Both are **absent** from this full run: the
sibling modelo/persistence owner has since resolved them. The tree is strictly
closer to green than at the prior attempt, and the residual red is now confined
to the governance ratchets above.

### F3 — The lone C1-named signature is a pre-existing, shrinking overage (not a C1 regression)

Only one failure line names a C1-touched file: the codebase-size budget reports
`src/aeat/entrypoints/cli/_ledger.py` at 1281 lines over a 1250 budget (31
over). This is **not** introduced by C1: at the C1 landing commit `3695a1b93`
the file was already **1338 lines** — over budget before C1 — and six-plus
subsequent peer ledger campaigns (IVA derivation, `_resolve_id` collapse,
`invoice --kind`, the mutation quintet, helper extraction into
`_ledger_support`) have since *reduced* it to 1281. The overage predates C1,
is owned by the broader CLI surface, and is trending down. Fixing it is
explicitly out of scope for this goal (no broad ledger changes).

### F4 — Operator-authorized full-tree sweep: 1 gate cleared, 10 abort-on-WIP blocked

The operator authorized overriding `full-tree-gate-must-distinguish-owner` to
fix all 11 gates regardless of ownership. On execution, a pre-edit WIP check
(`aeat-swarm-orchestration` abort-on-WIP) found that the target files of 10 of
the 11 gates carry **live uncommitted peer WIP** at this moment — the
ownership-override does not extend to the categorical destroy-peer-work
prohibition in `aeat-git-worktree-safety`, so those files cannot be edited
without stranding peer changes:

- module-size: `modelo/_verification_actions.py` (peer −50/+32, already
  shrinking the file), `registry/_schema.py` (peer −26/+11, already shrinking),
  `overview/tests/test_calendar_filing_evidence.py` (untracked peer file).
- callable-size: `modelo/_calculation_actions.py` (peer +35).
- env.example: peer WIP adds a *different* field (`AEAT_LIVE_FILED_REGISTER_WALK_TIMEOUT_MS`), not the flagged `AEAT_CLI_REVEAL_IDENTIFIERS`.
- utf8 literals: `bucket_maintenance/_service.py` (peer +259).
- locale parity: all four `locales/*.yml` carry peer WIP (and must be edited
  only through the locales CLI per `aeat-locales-cli`).
- marker integrity & docstring-link gates: violation sets span files that are
  partly WIP/untracked (`test_modelo_303_official_box_under_declaration.py`
  modified, `test_service_import_export.py` untracked), so the gates cannot be
  cleared even by fixing their clean members.

The single fully-clean gate, `test_no_absolute_self_imports_in_aeat_package`,
was fixed and committed (`c0a624c8b`): the 4 absolute intra-`aeat` imports in
`test_ledger_report_payload_parity.py` and `test_suggestion_command_conformance.py`
became relative `....` imports; both files pass 10/10. That gate is now green.

The two oversized modules are already being reduced by peers, so two size gates
may self-resolve once that WIP lands. The honest closeout path is to re-run the
full-tree gate after peer WIP settles and fix any genuinely-unowned residue on a
clean tree — not to edit files mid-peer-edit.

## Recommendations

- **Leave `P05.S15` unchecked** as a deferred carry-forward. Per the
  `full-tree-gate-must-distinguish-owner` rule, a full-tree verification Step
  must not be marked complete while the repository-wide gate is red; the honest
  state is that C1 introduced zero regressions but the shared worktree carries
  11 unrelated peer/governance failures. The plan is therefore **15/16**, not
  16/16.
- **No code change.** Every red signature is outside the feature surface;
  patching peer-owned governance gates to force a closeout would violate the
  scope boundary and the same rule's second Bad example.
- **Follow-on owner (not this campaign):** the standing governance ratchets
  (size budgets, docstring/return-type links, locale parity, utf8 inventory,
  marker integrity, env-example alignment, relative-imports) belong to the
  broader hardening cadence; `_ledger.py`'s residual 31-line overage folds into
  the CLI module-size burndown.

## Codification candidates

None. The owner-vs-peer triage discipline this audit applied is already codified
in `full-tree-gate-must-distinguish-owner`, and the C1 invariant itself is
codified in `ledger-amount-is-absolute-direction-is-authority`. No new durable,
constraint-shaped, project-bound lesson surfaced.
