---
step_id: S367
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P41.S367 — M721 registry stub + refusal payload

## Outcome

`aeat app overview explain 721 --year 2024` now returns exit 0 with a
structured `OverviewExplain` payload carrying all three grounding legal refs
instead of raising `OverviewExplainError("could not evaluate")`.

## Implementation

Path-B refusal stub — no casillas, formulas, or bindings. The registry is
complete enough for the applicability engine to route the verdict.

**Commit 1 — registry + legal refs** `37933ecca`

- `src/aeat/_data/registry/aeat/modelos/721/manifest.toml` — modelo manifest
  (informative, annual, ES-AEAT jurisdiction, 5 legal refs)
- `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/revision.toml`
  — revision stub (valid_from 2023-08-01, year_from=2022, periods=["0A"])
- `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/application_links/0001-application_links.toml`
  — deadline surface application link
- `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/deadline_windows/0001-deadline_windows.toml`
  — 4 deadline windows (filing years 2022–2025, Jan 1 – Mar 31)
- `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/workbook_parity_refs/0001-workbook_parity_refs.toml`
  — static_layout workbook parity ref (runner_required=false)
- `src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml` — 5 legal refs
  (ley-11-2021:da-10, orden-hfp-887-2023:art-1/2/3, rd-1065-2007:art-42-quater)
  + 2 source refs (aeat-modelo-721-procedure, boe-modelo-721-2023-form)
- 6 corpus HTML stub files under `src/aeat/_data/corpus/` (legal articles +
  AEAT procedure page) with correct sha256 and byte counts
- `src/aeat/domain/calculations/registry/_applicability.py` — M721 rule added
  to `_MODELO_APPLICABILITY_RULES`: NATURAL_PERSON + LEGAL_ENTITY;
  cuota_bearing=False; legal_refs=(ley-11-2021:da-10, orden-hfp-887-2023:art-3,
  rd-1065-2007:art-42-quater)

**Commit 2 — regression test** `c72742b42`

- `src/aeat/entrypoints/cli/test_overview_explain_verb.py::test_explain_721_returns_structured_payload_not_crash`
  — asserts exit 0, no OverviewExplainError text, and all three grounding
  legal refs present in CLI output

## Quality gates

- G1 (no naked env reads): pass — no os.environ/os.getenv added
- G2 (typed pydantic at boundaries): pass — ModeloApplicabilityRule used
- G3 (tr() for user messages): pass — no new user messages added
- G5 (no shims/duplication): pass — single canonical M721 registry path
- G6 (no tautological tests): pass — test asserts against specific legal ref
  strings that must come from the registry rule, not the test author

## Test run

```
src/aeat/entrypoints/cli/test_overview_explain_verb.py — 6 passed
src/aeat/domain/calculations/registry/test_registry_schema.py — 66 passed (5 deselected)
src/aeat/domain/calculations/registry/test_catalogue_verification.py — passed (exit 0)
```
