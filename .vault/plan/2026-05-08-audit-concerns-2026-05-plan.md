---
tags:
  - '#plan'
  - '#audit-concerns-2026-05'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-renta-cuota-integra-state-scale-plan]]"
  - "[[2026-05-08-renta-cuota-integra-state-scale-adr]]"
  - "[[2026-05-08-renta-cuota-integra-autonomic-scale-adr]]"
  - "[[2026-04-16-live-write-test-audit-research]]"
---

# `audit-concerns-2026-05` tracking plan

Tracking plan for the four cross-concern findings raised by the
external `aeat-audit` metaproject run against rev `b01f7c6` of branch
`chore-476-restructure-execution`. Severity histogram for that run:
0 critical, 386 high, 446 medium, 6 284 low, 18 526 info; zero
broken architecture (`import-linter`) contracts.

> **Update 2026-05-08 (post-execution):** the renta-cuota-integra
> state-scale stream that the audit's allow-listed orphan parameters
> pointed at has been closed by a separate plan and ADR; see the
> `[[2026-05-08-renta-cuota-integra-state-scale-plan]]` related entry.
> Across six Modelo 100 ejercicios (2020-2025) the IRPF state-scale
> bracket parameter is now consumed by an `op = "lookup_bracket"`
> formula at casillas 0528 and 0530, the construct ownership lists
> include the new formula ids, and the orphan-detection allow-list is
> empty. Workbook parity, drift-detection, and chain-behaviour gates
> all pass for the wired chain.
>
> **Update 2026-05-12 (post-execution):** the follow-up
> autonomic-scale stream that wires casillas 0529 and 0531 through
> `op = "lookup_bracket_by_ccaa"` is now closed; see the
> `[[2026-05-08-renta-cuota-integra-autonomic-scale-plan]]` related
> entry. Across all six Modelo 100 ejercicios (2020-2025), the per-CCAA
> autonomic bracket parameters for every ordinary common-regime CCAA
> (Andalucía, Aragón, Asturias, Illes Balears, Canarias, Cantabria,
> Castilla-La Mancha, Castilla y León, Cataluña, Comunitat Valenciana,
> Extremadura, Galicia, La Rioja, Madrid, Murcia) are now consumed by
> dispatch-table formulas at casillas 0529 and 0531, the
> `renta-XXXX-profile-tax-residence-ccaa` binding routes against
> `RentaCCAA` enum values, and the orphan-detection scanner walks
> `dispatch_table` leaves. Coverage = 90 (CCAA × ejercicio)
> combinations. Per-modelo `verification_expectations` blocks now
> cover modelos 100, 200, 202, 303, 309, 322, 353, 369, and 390 — the
> full set of modelos with calculated outputs (modelos 308, 349, 360
> carry no formulas and therefore no `computed_casillas` to verify).

This plan is the in-repo mirror of the auditor's brief. The
auditor-side artefacts live outside this repo at
`Y:/code/aeat-audit/.vault/audit/2026-05-07-audit-tooling-audit-2.md`
and its sidecar `raw.json`.

## Proposed Changes

Land the four concerns one at a time, in independent slices, against
the same branch family. Each slice carries its own re-audit recipe so
clearance is measurable against a future audit run rather than against
internal opinion. The four concerns do not share file paths and there
is no evidence of a single upstream change driving them, so cross-slice
dependencies are weak; ordering is by deliverability, not by blocker
graph.

## Tasks

- Concern 2 ÔÇö `tests/import_contract/domain/invoices/` API drift
  (109 high+medium findings, 84 high)
  1. Delete the parked `_test_repository.py` (drifted; pytest had
     already excluded it via the leading underscore).
  1. Reseed `test_cli.py` against the no-arg
     `InvoiceCatalogueRepository()` / `TransactionCatalogueRepository()`
     and drop the dead `AEAT_INVOICES_DIR` / `AEAT_FINANCIAL_TXS_DIR`
     env routing.
  1. Drop the two monkeypatch tests in `test_reconciliation.py`
     (rollback semantics that `link_transaction_bidirectional` no
     longer provides) and rewrite the happy-path test against the
     no-arg repos.
  1. Add `test_repository.py` with end-to-end save ÔåÆ fresh-instance ÔåÆ
     load round-trip coverage on both catalogue repositories. This is
     the regression net the audit said was missing; type drift in this
     cluster will from now on fail at runtime, not just in CI typing.
  1. Document the catalogue export/import scope gap as a boundary in
     the `aeat financial invoices` module docstring (no CLI verb for
     cross-process backup/restore exists yet).

  Re-audit recipe: the three files drop out of the per-rule sweep
  candidates for `call-arg`, `unexpected-keyword`, `unknown-argument`,
  `attr-defined`, `missing-attribute`, `unresolved-attribute`; the 25
  medium `type-checker-divergence` rows on the same lines clear; the
  overall `high` count drops by ~84.

- Concern 1 ÔÇö `RegistryValidator._validate_revision` decomposition
  (cyclomatic 157 / cognitive 208; risk-dashboard row 6, sole
  non-trivial top-10 hotspot)
  1. Walk the audit's complexity findings on the file (sidecar's
     `cyclomatic-complexity` and `cognitive-complexity` rows for
     `RegistryValidator`).
  1. Split `_validate_revision` along its existing internal validator
     boundaries (revision shape, relation closure, previous-filing
     binding closure, source citations, construct closure ÔÇö each
     already named as a private method, but the parent dispatcher has
     accreted shared state and branching).
  1. Address the four type-precision findings on the same file
     (`_validate.py` lines 484/519 `T | None ÔåÆ T`, line 1250 bare
     `str ÔåÆ` 5-arm `Literal`, line 57 `pypdfium2` overlaps Concern 4).
  1. Avoid moving complexity into helper methods; the goal is to drop
     each leaf below the medium threshold, not to redistribute it.

  Re-audit recipe: file falls out of top-10 hotspots, severity load
  <10; `_validate_revision` no longer appears in the
  `cyclomatic-complexity` / `cognitive-complexity` high sections; the
  six other `RegistryValidator` methods either disappear or drop one
  tier; the four assignment / `Literal` type rows clear.

- Concern 3 ÔÇö CLI review-response model tightening
  (~15 type findings + co-located cognitive complexity in
  `entrypoints/cli/_invoice.py` and `_ledger.py`; sibling findings on
  `_overview.py` and `_tty.py`)
  1. Replace the loose `dict[str, bool | str | <ReviewRecord> | None]`
     return shape of invoice and ledger review with a typed pydantic
     response model whose arms include the list-of-dict and
     list-of-`FilterClause` fields the call sites actually construct.
  1. Cascade-fix the ~10 dependent `union-attr` / `call-overload` /
     `index` / `unsupported-operation` findings on lines 199ÔÇô241 of
     `_invoice.py` (they are downstream of the dict-item finding).
  1. Fix `_tty.py:44` `bad-override-mutable-attribute` on
     `NonTtyRefusedError.suggestion` (declare the override
     consistent with `AeatError`'s shape).
  1. Rename or re-scope the `lines` binding shadowed at
     `_overview.py:77`.
  1. Reduce `invoice_review` cognitive complexity below the medium
     threshold (currently 70) ÔÇö almost certainly falls out as a
     side-effect of (1) once the dict-shape juggling moves into the
     pydantic model.

  Re-audit recipe: 4 `dict-item` rows + ~10 dependent rows clear;
  `_overview.py:77` and `_tty.py:44` clear; `invoice_review`
  cognitive complexity drops below 25; the
  `entrypoints/cli/` package no longer dominates the `union-attr` /
  `dict-item` sweep candidates.

- Concern 4 ÔÇö Systemic typed-package gaps
  (105 findings: 47 `import-untyped`, 29 `unresolved-import`, 29
  `missing-source-for-stubs`, across 23 files)
  1. Inventory every untyped third-party import flagged by the audit:
     `reportlab.{lib.pagesizes,lib.units,pdfgen}`, `defusedxml`,
     `openpyxl{,.formula,.workbook,.worksheet.worksheet}`,
     `pypdfium2`, `playwright_stealth`.
  1. For each, install `types-*` stubs from PyPI when available and
     add them as a dev dependency.
  1. For packages with no stubs on PyPI, add a minimal hand-written
     stub under a project `stubs/` directory and configure each type
     checker (`mypy`, `ty`, `pyrefly`) to search it.
  1. Re-run the three checkers and confirm the rule sweeps shrink.

  Re-audit recipe: `import-untyped` / `unresolved-import` /
  `missing-source-for-stubs` rule sweeps shrink to a small remainder;
  total finding count drops by ~100 from the type category; the 23
  affected files no longer dominate the cross-category-density table.

## Parallelization

Concerns 1, 3, and 4 share no file paths and have no shared upstream;
they can land in any order in independent branches. Concern 2 is
already resolved in this slice. Concerns 1 and 3 share a structural
pattern (high type findings co-located with cognitive complexity on
the same functions) ÔÇö interleaving them gives the architect on each
slice the chance to reuse the same decomposition lens. Concern 4 is
infrastructure-level and can land entirely independently.

## Verification

Mission success is measured against the auditor's re-audit. For each
concern, success is ÔÇö literally ÔÇö "the next audit run produces the
diff described in that concern's re-audit recipe." Internal unit and
type-check passes are necessary but not sufficient: this plan exists
because internal type checks ran green at rev `b01f7c6` while the
audit still surfaced the cluster. The re-audit is the only honest
gate.

In-slice verification for Concern 2:
`uv run --no-sync pytest tests/import_contract/domain/invoices/ -q`
goes 27/27 green, including 8 round-trip persistence tests on the no-arg
repositories. The remaining concerns' verification gates are part of
their respective slices.
