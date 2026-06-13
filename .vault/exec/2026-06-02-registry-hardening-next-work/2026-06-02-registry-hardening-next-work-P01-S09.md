---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P01.S09'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-m303-fragment-pressure-audit]]'
---

# P01.S09 Execution Record

## Step

`P01.S09`: Audit M303 casilla and export fragments near the reviewability
ceiling; `.vault/audit`.

## Result

Completed. M303 has six TOML fragments above 1200 lines and two above 1500
lines. The pressure is below the current M200 maximum, but it is now tracked for
follow-up as `P05.S29`.

The plan was extended with a new residual-pressure phase:

- `P05.S28`: remaining M200 export pressure;
- `P05.S29`: M303 casilla/export pressure;
- `P05.S30`: post-split headroom re-audit.

## Artifacts

- `2026-06-02-registry-hardening-m303-fragment-pressure-audit`
- `2026-06-02-registry-hardening-next-work-p01-s09-review`

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 10.28s.
- `uv run --no-sync python -c "from aeat.domain.calculations.registry import load_modelo_directory; from aeat.core.resources import bundled_path; m=load_modelo_directory(bundled_path('registry','aeat','modelos','303')); print(m.id, sorted(m.revisions)); print([(rid, len(rev.casillas), len(rev.export_layouts)) for rid, rev in sorted(m.revisions.items())])"`
  - Result: `303 ['2009-y-siguientes', '2023-y-siguientes']` and `[('2009-y-siguientes', 113, 1), ('2023-y-siguientes', 115, 1)]`.
