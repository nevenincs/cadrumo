---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:fa11494fa321b698e40e50f5aca5367e783db4679c1bfd8bf1fb343b9cd11eb0'
step_id: 'S80'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Reconcile the invalid S08 manifest worklist and retire its false-positive steps

## Scope

- `.vault/plan/2026-08-10-casilla-schema-plan.md and .vault/exec/2026-08-10-casilla-schema/2026-08-10-casilla-schema-W01-P02-S08.md and .vault/research/2026-08-10-casilla-schema-research.md and src/cadrumo/domain/calculations/registry/tests/test_record_design_completeness.py`

## Description

- Re-measure every manifest-absent revision through the validated production `bundled_authority` and the canonical `calculation_closure_casilla_ids` derivation.
- Adjudicate manifest applicability against the production absence rule and the non-empty manifest schema invariant.
- Re-run the focused real registry tests that cover fleet-wide manifest applicability and the legitimate zero-closure case.
- Retire false-positive steps S42-S79 through plan CLI removals after one successful dry-run per step.
- Correct the plan lifecycle prose, historical S08 execution record, research A-09, and the fleet test's brittle exact-count assertion.

## Outcome

The validated production authority reports exactly 38 revisions without a `completeness_manifest`. Every one has an empty canonical calculation closure, so the measured population is `manifest_absent=38`, `zero_closure=38`, and `missing_required_manifest=0`.

The exact per-revision result, retained in the S08 tranche order, is:

- Tranche 1: `121/2017-y-siguientes=0`, `122/2017-y-siguientes=0`, `140/2020-y-siguientes=0`, `143/2014-y-siguientes=0`, `145/2012-01-31-y-siguientes=0`, `270/2013-y-siguientes=0`, `280/2025=0`, `308/2009-y-siguientes=0`, `341/2000-y-siguientes=0`, `345/2025=0`, `360/2010-y-siguientes=0`, `361/2010-y-siguientes=0`, `379/2024-y-siguientes=0`, `380/2005-y-siguientes=0`.
- Tranche 2: `156/2003-y-siguientes=0`, `165/2013-y-siguientes=0`, `179/2021-y-siguientes=0`, `181/2009-y-siguientes=0`, `189/2025=0`, `231/2021-y-siguientes=0`, `233/2018-y-siguientes=0`, `238/2024-y-siguientes=0`, `289/2025=0`, `347/2008-y-siguientes=0`, `721/2023-y-siguientes=0`, `848/2003-y-siguientes=0`.
- Tranche 3: `038/2002-y-siguientes=0`, `185/2025-y-siguientes=0`, `186/2003-y-siguientes=0`, `220/2024-y-siguientes=0`, `222/2025-y-siguientes=0`, `234/2021-y-siguientes=0`, `490/2021-y-siguientes=0`, `576/2007-y-siguientes=0`, `592/2022-y-siguientes=0`, `604/2021-y-siguientes=0`, `763/2011-y-siguientes=0`, `840/2003-y-siguientes=0`.

Canonical production and test evidence agrees on the lifecycle classification:

- `_validate_completeness.py:25-33` returns no failure when the canonical closure is empty and requires a manifest only for a non-empty closure.
- `_schema_surfaces.py:527-530` rejects a completeness manifest with no casilla rows, so an empty placeholder manifest is invalid.
- `test_record_design_completeness.py:157-196` proves the bidirectional per-revision property and retains positive evidence for both calculation-bearing and zero-closure revisions without a hard-coded fleet count.
- `test_referential_integrity_part2.py:217-229` proves a revision without calculation closure validates without a manifest.

The lifecycle finding is a false-positive worklist predicate, not missing registry data: S08 equated manifest absence with manifest obligation. The correct predicate is `completeness_manifest is absent AND canonical calculation closure is non-empty`. No current revision satisfies it. Authoring manifests for these revisions would fabricate closure rows and violate the schema.

Formal review folded the cleanup into S80 and retired the unexecuted S81 row. S42-S79 each passed an individual CLI removal dry-run and were then retired through `vaultspec-core vault plan step remove`; all 38 removals preserved the plan's two authored prose blocks. S08 remains checked as historical execution, and no registry data was authored.

Formal review findings and resolutions:

- The manifest-absence predicate was not a manifest-obligation predicate. Resolve by retiring S42-S79 and correcting every lifecycle statement to require both manifest absence and a non-empty canonical closure.
- Splitting cleanup into S81 left S80's adjudication incomplete. Resolve by expanding S80 to own the cleanup and retiring unexecuted S81 without reusing its identifier.
- The initial RAG note incorrectly said code semantic grounding succeeded. Resolve with the exact boundary below: vault RAG succeeded, code RAG was blocked by metadata job `c85efeb1`, and whole-file, targeted `rg`, and public-runtime fallback supplied the code grounding.
- The fleet test hard-coded the current dormant count and duplicated the revision inventory in a comment. Resolve by retaining its bidirectional per-revision property plus at-least-one calculation-bearing and at-least-one zero-closure evidence without a fleet count.
- The plan, S08 record, and research A-09 preserved false tranche, deadline, progress, or debt claims. Resolve by retaining the dated historical execution while making the canonical 38 absent, 38 zero-closure, 0 required-gap disposition authoritative.

Focused verification:

- `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_record_design_completeness.py::test_calculation_completeness_gate_is_live_for_every_calculation_bearing_modelo src/cadrumo/domain/calculations/registry/tests/test_referential_integrity_part2.py::test_revision_without_calculation_closure_passes_without_completeness_manifest`
- Result: `2 passed in 10.89s`.
- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_record_design_completeness.py` passed.
- `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/tests/test_record_design_completeness.py` reported `0 errors, 0 warnings, 0 notes`.
- Plan status reports 42 live steps, 23 complete, next open `W03.P07.S24`, and no missing exec ids. Plan check reports only the intentional non-monotonic retired-id warning.
- Feature-scoped modified-stamp and exec-mapping checks are clean. Body-sections reports one pre-existing out-of-scope warning for the empty S02 Description.
- Scoped `git diff --check` passed after normalising trailing newlines.
- Formal re-review resolved all three findings and returned PASS; its independent rerun reported `2 passed in 12.75s`, Ruff clean, and clean feature-scoped modified-stamp, exec-mapping, and diff checks.

## Notes

RAG boundary: the vault semantic search succeeded and was restricted to the `casilla-schema` feature and ADR, research, plan, and exec document types. The code semantic search was blocked by existing metadata job `c85efeb1`. The mandated fallback read the target and canonical implementation/test files whole, narrowed exact symbols and citations with `rg`, and measured the public runtime boundary through `bundled_authority` plus `calculation_closure_casilla_ids`; no result was inferred from filenames or the historical worklist.

Structural mutations were previewed with `--dry-run`. S81 was retired before execution when formal review expanded S80 to own the cleanup. Every S42-S79 removal then passed its own dry-run before the actual removal, and every actual removal reported `Preserved 2 unknown blocks`.

Non-atomic history carry-forward: commit `a3c07ef209` externally absorbed the initial S80 execution record and the S80/S81 plan rows together with unrelated S35/S38 review work before S80 formal review completed. Commit `3dfbd2b036` then absorbed the initial S80 audit with unrelated S38/S94 reviews, `cfb57c1325` absorbed the S42-S79/S81 retirement plus S08/plan/research corrections with an unrelated CLI-action plan edit, and `efeb24cb7a` absorbed the exact-count test repair with unrelated ledger/filing work. This closure does not rewrite shared history; it records those external absorptions and carries the remaining S80 execution correction, final audit resolution, and checked plan state in one bounded commit.

Modified files are limited to the plan, the S08 and S80 execution records, casilla-schema research, the S80 audit, and `test_record_design_completeness.py`. No registry data, production code, generated artifacts, or locales were changed. Nothing was staged or committed before lifecycle closure.
