---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-26"
modified: '2026-05-26'
step_id: "task-34"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
---

# task-34: provisional_pending_specimen field + corpus specimen gate

## Summary

Converts the silent-failure findings from the task-32 extraction-profile
grounding audit into an enforced structural invariant.  Delivered as three
commits (plus one cache-key fix) across Unit 1, 2, and 3.

## Unit 1 — Schema field + validator gate

commit `e285001d0` (+ cache key fix `a737e05c3`)

- Added `provisional_pending_specimen: bool = False` to
  `ExtractionProfileDefinition` in `_schema.py`.
- Added `validate_declaracion_pdf_specimen_gate` to
  `_validate_extraction_profiles.py`: for any `declaracion_pdf` profile not
  marked provisional, checks that `tests/fixtures/justificantes/<modelo_id>/`
  contains at least one `.pdf`; fails with `RegistryValidationError` otherwise.
- Extended `validate_extraction_profile_section` in
  `_validate_record_sections.py` with `modelo_id` and optional `corpus_root`
  parameters; gate is invoked when corpus_root is available.
- Added `justificante_corpus_root: Path | None = None` to `RegistryValidator`;
  auto-derives from `source_root` (three parents up) when not supplied.
- Updated model and registry cache keys to include the corpus root path.
- 5 new unit tests in `test_provisional_specimen_gate.py` covering all three
  gate outcomes (fail/pass with flag/pass with fixture).

Pass count: 5/5 new tests; 71/71 registry schema tests; 49/49 referential
integrity tests.

## Unit 2 — Tag 9 PROVISIONAL profiles

commit `dbe3afa48`

Set `provisional_pending_specimen = true` in 9 TOML files:

| Modelo | File(s) | Audit class |
|--------|---------|-------------|
| M036 | `modelos/036.toml` | PROVISIONAL |
| M184 | `modelos/184.toml` | PROVISIONAL |
| M193 | `modelos/193.toml` | PROVISIONAL |
| M232 | `232/revisions/2016-2017/extraction_profiles/0001-...toml` | PROVISIONAL |
| M232 | `232/revisions/2018-y-siguientes/extraction_profiles/0001-...toml` | PROVISIONAL |
| M347 | `modelos/347.toml` | PROVISIONAL |
| M349 | `349/revisions/2020-y-siguientes/extraction_profiles/0005-...toml` | UNKNOWN |
| M720 | `modelos/720.toml` | PROVISIONAL |
| M840 | `modelos/840.toml` | PROVISIONAL |

M190 retains default `false` (GROUNDED — corpus fixture exists).
M349 `export_record` profile is unaffected.

Pass count: 220/220 (registry+declaration full suite).

## Unit 3 — ADR amendment

commit `27c54cc4b`

Added `## 2026-05-26 amendment` block to
`.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`
documenting: (a) silent-failure class found by task-32 audit; (b) the new
schema field; (c) the validator gate; (d) forward discipline for new profiles.

## Verification

Final pass count (task-specified suite):
`src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py +
src/aeat/adapters/inbound/declaracion/ + test_modelo_{036,184,193,347,349,720,840,232}_registry.py`
= **220/220 passed**.

No surprise findings. The gate correctly skips when corpus_root is None
(no source_root available), ensuring backward compatibility with existing
tests that construct `RegistryValidator(catalogues)` without source_root.

## Bug-Fix Addendum — 2026-05-26 code-review Gate 9 FAIL

**Bug**: The corpus-root derivation in Unit 1 used `parents[2]`, but every
production call site passes `source_root=bundled_path()` which resolves to
`src/aeat/_data` (not `src/aeat/_data/registry/aeat` as the original comment
assumed).  `parents[2]` of `src/aeat/_data` = `<worktree_root>`, so the
candidate path `<worktree_root>/tests/fixtures/justificantes` never existed and
`_justificante_corpus_root` was silently set to `None`.  The gate was entirely
disabled in production; the 5 existing unit tests all inject
`justificante_corpus_root` directly and therefore bypassed the broken derivation.

**Fix**: Changed `parents[2]` → `parents[0]` in `_validate.py` line 122.
`parents[0]` of `src/aeat/_data` = `src/aeat`, and the corpus is correctly
found at `src/aeat/tests/fixtures/justificantes`.

**New tests added** to `test_provisional_specimen_gate.py`:
- `test_corpus_root_derived_from_bundled_path`: constructs `RegistryValidator`
  with `source_root=bundled_path()` (no injection), asserts
  `_justificante_corpus_root` is a real existing directory named `justificantes`.
- `test_gate_fires_via_production_path`: uses M036 (declaracion_pdf profile, no
  `justificantes/036/` fixture) with `provisional_pending_specimen` overridden
  to False via production `source_root=bundled_path()` — confirms
  `RegistryValidationError` is raised.

commit `8c8865d90`

Pass count: 7/7 gate tests; ruff clean.
