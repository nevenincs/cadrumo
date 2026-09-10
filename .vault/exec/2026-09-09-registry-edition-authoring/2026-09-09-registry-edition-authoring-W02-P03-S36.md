---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:51306ec2cd916aed0287ed2f9ffd3faa66bd809699e8f5be53761da28cccb308'
step_id: 'S36'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Refuse a declared predecessor where the successor withholds by design — a lower authority grade than its predecessor, or a header-only edition refusing to state figures it cannot ground. Inheriting there would silently materialise withheld rows. This must be a load-time refusal keyed on the declared grades because the minimality screen is structurally blind to it: an edition stating two rows matches nothing inherited and reports clean. Proof: the modelo declaring nearly two thousand rows then two is refused if a predecessor is declared, and loads unchanged without one.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_grade_refusal.py`
- `verify:` `uv run --no-sync pytest test_revision_predecessor_grade_refusal.py test_revision_edition_materialisation.py test_revision_label_inheritance.py test_revision_predecessor_forest.py test_revision_predecessor_date_agreement.py test_revision_predecessor_declaration.py test_materialisation_excludes_non_casilla_families.py test_casilla_label_spanish_source_coverage.py dev/registry/tests/test_delta_minimality.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on both files -> `pass`

## Notes

- Partial step: the proof on modelo 220 does not hold. Its `2024` edition declares 1985 casillas and `2025` declares 2, and both are graded `applicability`, the lowest rung, so no grade comparison can refuse the pair. In a temporary copy with `predecessor = "2024"` declared on `2025`, the loader accepts it and `2025` materialises 1985 casillas. Without the declaration it loads unchanged, as 1985 and 2.
- The schema declares no header-only or withholding field. The "declaration header only" fact is recorded only in `revision.toml` comments and `reviewed_by` prose, so the refusal is keyed on the grade condition alone, and no field was authored. Closing the modelo 220 case needs a declared withholding field, which has to be decided first.
- The reviewer persona has not been run, so the review is still outstanding.

- The reviewer persona could not be launched. The orchestrating session reviewed the grade refusal: one ladder, declared fields only, and it runs before inheritance. Re-run: 37 passed, `registry verify` exit 0, ruff and ty clean. The Step stays OPEN, because the header-only withholding case (modelo 220: 1985 then 2 rows at equal grade) is not caught and needs a declared withholding field. That is an operator decision.

- The equal-grade case was grounded and needs no new field. Orden HAC/529/2026 (BOE-A-2026-11583) approves the full 2025 Modelo 220, and the AEAT record design DR220e25 is published and bundled as `aeat-dr-220-2025`. So 220/2025 is an authoring backlog across a measured design re-layout, not withholding by design. The one live withholding successor (165/2023-2025, filing to applicability) is refused by the grade rule. The ADR paragraph was corrected to match. Follow-ons: a derived re-layout guard, if the residual delta-first risk needs closing; the 220 comment at `revisions/2024/revision.toml:10-12` is stale; the catalogue `published_at` for Orden HAC/529/2026 (2026-05-13) should be checked against the BOE date (29 May 2026).
