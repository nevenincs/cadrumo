---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---



# `registry-hardening-next-work` audit: `registry Python module size and ownership boundary audit`

## Scope

Audited production Python modules under `src/aeat/domain/calculations/registry`
for size, current ownership boundaries, and safe follow-up order for `P04.S18`.
Test-module decomposition is intentionally deferred to `P04.S26`; this audit
only covers production registry surfaces.

## Findings

- **High:** The production registry package has 70 private production modules
  and 21,964 working-tree lines. Ten modules exceed 500 lines, and six exceed
  1,000 lines.
- **High:** `_bindings.py` is the largest production module at 2,614 lines. It
  mixes previous-filing selectors, invoice rows, OSS/IOSS ledger rows, IVA ledger
  rows, Renta ledger rows, counterpart rows, withholding rows, related-party rows,
  Modelo 720 rows, attribution rows, refund rows, profile/manual selectors, and
  selector validation. This is the next highest-value extraction target.
- **High:** `_schema.py` remains a generic cross-application schema module at
  2,188 lines. It is legitimately central, but it combines scalar validators,
  source/legal/catalogue models, extraction/link models, parameters, formulas,
  bindings, casillas, relations, export layouts, modelo revisions, and snapshots.
  Any split needs ADR coverage because it changes import topology.
- **Medium:** `_record_design.py` is 1,501 lines and mixes PDF/XLS extraction,
  workbook row parsing, diseno coverage derivation, and calculation-completeness
  identity helpers. It is a good standalone extraction target after bindings.
- **Medium:** `_applicability.py` is 1,324 lines and mixes model types, seed
  rule tables, taxpayer route derivation, Modelo 202 modality derivation, and
  legal-reference constants. It should be split by rule table and derivation
  services, not by modelo.
- **Medium:** `_workbook_parity.py` is 1,153 lines and mixes workbook discovery,
  scan reports, LibreOffice conversion, Excel COM execution, workbook parity
  comparison, and coverage classification.
- **Medium:** `_formula_runtime.py` is 1,150 lines and mixes snapshot materialise
  logic, binding absence policy, expression dispatch, bracket lookup evaluators,
  arithmetic dispatch, parameter resolution, rounding, and public parameter reads.
- **Medium:** `_loader.py` is 788 lines and is below the 1,000-line threshold but
  owns the fragment compiler and loader cache path. It is already separately
  planned as `P04.S19`.
- **Medium:** `_queries.py` is 731 lines and mixes public report DTOs, query
  service methods, period parsing, row projection, and public-value conversion.
- **Medium:** `__init__.py` is 647 lines and is mostly re-export surface. Its
  size reflects public API sprawl rather than internal algorithm complexity.
- **Pass:** `_validate.py` is no longer the monolith it used to be. The validator
  family now has many `_validate_*` leaf modules; the largest is
  `_validate_cross_revision.py` at 359 lines and the orchestrator `_validate.py`
  is 185 lines. Validator pressure is now coordination and naming, not one-file
  size.
- **Worktree constraint:** Twelve production registry modules are dirty in the
  shared worktree, including every large extraction target except `__init__.py`
  and `_live_parity.py`. Refactor steps must start with path-scoped diffs and
  should not edit a dirty module unless the diff is owned or explicitly accepted.

## Recommendations

Close `P04.S18` as an audit-only boundary map. Execute the follow-ups in this
order:

1. `P04.S20` before broad schema work: split `_bindings.py` by resolver family
   because it is the largest module and already has clear internal sections.
2. `P04.S19` next: isolate `_loader.py` fragment-compiler helpers without
   changing loader semantics.
3. `P04.S21` only after an ADR decision: split `_schema.py` by generic schema
   domain, never by modelo.
4. `P04.S22`, `P04.S24`, and `P04.S25` can proceed independently after their
   path-specific audits because record design, workbook parity, and formula
   runtime have natural helper clusters.
5. Treat `__init__.py` as a public API export audit, not a mechanical
   line-count refactor. Its size should shrink only if exports move behind
   compatibility-preserving submodule barrels.

## Codification candidates

- **Source:** module-size findings above.
  **Rule slug:** `registry-module-size-gate`.
  **Rule:** Production registry modules crossing 1,000 lines require an explicit
  audit or plan step before further feature growth, and new extraction work must
  preserve generic cross-modelo contracts rather than creating modelo-specific
  modules.
