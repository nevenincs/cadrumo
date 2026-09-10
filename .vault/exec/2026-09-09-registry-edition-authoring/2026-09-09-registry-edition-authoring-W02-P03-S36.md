---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:93193793f39749a4bad357dcb03786cad14e52163a264943f121c9be95bb6a78'
step_id: 'S36'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
