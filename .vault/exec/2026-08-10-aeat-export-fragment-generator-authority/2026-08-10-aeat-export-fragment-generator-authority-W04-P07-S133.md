---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6d0e2722cd9441a5b045e8fb50ae67324761980efcd158bc3b8d22ed69318dd4'
step_id: 'S133'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Add an explicit digest-bound provenance-only republish command to the canonical generated-tree CLI, require the current target manifest identity and exact semantic record reproduction before transactional replacement, refuse record or member drift, refresh every currently publication-eligible stale generated attestation, retain lower-grade and record-drifting trees only through live source-bound per-subject pins, and prove the full dynamically enrolled gate reaches only those declared pending states.

## Scope

- `dev/registry/pipeline/cli.py`
- `dev/registry/pipeline/render_check.py`
- `dev/registry/pipeline/generated_tree_dispositions.toml`
- `dev/registry/tests/test_generated_tree_cli.py`
- `dev/registry/tests/test_render_check.py`
- `dev/registry/tests/test_generated_export_trees.py`
- `src/cadrumo/_data/registry/aeat/modelos/`
- `.vault/audit/`

## Changes

- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/pipeline/generated_tree_dispositions.toml`
- `M` `dev/registry/pipeline/render_check.py`
- `M` `dev/registry/tests/test_generated_export_trees.py`
- `M` `dev/registry/tests/test_generated_tree_cli.py`
- `M` `dev/registry/tests/test_render_check.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0001-record-m151-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0002-record-m151-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0003-record-m151-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0004-record-m151-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0005-record-m151-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0006-record-m151-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0007-record-m151-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0008-record-m151-page-05.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0009-record-m151-page-06.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0010-record-m151-page-06.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0011-record-m151-page-07.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0012-record-m151-page-08.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/0013-record-m151-did.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2015-2022/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0001-record-m151-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0002-record-m151-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0003-record-m151-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0004-record-m151-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0005-record-m151-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0006-record-m151-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0007-record-m151-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0008-record-m151-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0009-record-m151-page-05.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0010-record-m151-page-06.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0011-record-m151-page-07.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0012-record-m151-page-08.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0013-record-m151-page-08.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0014-record-m151-page-09.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0015-record-m151-page-10.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/0016-record-m151-did.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0001-record-m184-declarante.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0002-record-m184-entidad.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0003-record-m184-entidad.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0001-record-m184-declarante.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0002-record-m184-entidad.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0003-record-m184-entidad.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/export/0001-record-m210-autoliquidacion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/export/0002-record-m210-autoliquidacion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/export/0003-record-m210-ingreso-devolucion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/export/0001-record-m210-autoliquidacion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/export/0002-record-m210-autoliquidacion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/export/0003-record-m210-ingreso-devolucion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/export/0001-record-m232-operaciones-vinculadas.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/export/0002-record-m232-paraisos-fiscales.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/export/0003-record-m232-paraisos-fiscales.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/export/0001-record-m232-operaciones-vinculadas.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/export/0002-record-m232-paraisos-fiscales.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/export/0003-record-m232-paraisos-fiscales.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/0001-record-m296-declarante.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/0002-record-m296-perceptor.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/0003-record-m296-perceptor-intereses.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/0004-record-m296-anexo-a-pagos.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/0005-record-m296-anexo-b-certificados.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/export/0001-record-m322-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/export/0002-record-m322-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/export/0003-record-m322-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/export/0004-record-m322-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/export/0001-record-m322-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/export/0002-record-m322-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/export/0003-record-m322-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/export/0004-record-m322-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/export/0005-record-m322-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2023/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/export/0001-record-m322-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/export/0002-record-m322-page-01.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/export/0003-record-m322-page-02.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/export/0004-record-m322-page-03.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/export/0005-record-m322-page-04.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2024-2025/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2021-2025/export/0001-record-m353-declaracion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2021-2025/export/0002-record-m353-declaracion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2021-2025/export/_generation.provenance.json`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-desde-02/export/0001-record-m353-declaracion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-desde-02/export/0002-record-m353-declaracion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-desde-02/export/0003-record-m353-domiciliacion-devolucion.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-desde-02/export/_generation.provenance.json`

- `verify:` `uv run ruff check dev/registry/pipeline/cli.py dev/registry/pipeline/render_check.py dev/registry/tests/test_generated_tree_cli.py dev/registry/tests/test_render_check.py dev/registry/tests/test_generated_export_trees.py` -> `pass`
- `verify:` `uv run basedpyright dev/registry/pipeline/cli.py dev/registry/pipeline/render_check.py dev/registry/tests/test_generated_tree_cli.py dev/registry/tests/test_render_check.py dev/registry/tests/test_generated_export_trees.py` -> `pass`
- `verify:` cached failing generated-tree nodes under a stable HEAD and measured-diff bracket -> `6 passed`
- `verify:` `uv run python -u -m dev.registry.analysis.generated_tree_state` under stable authority and export-root fingerprints -> `19 reproduced, 11 provenance-only, 2 record-drift, 1 never-committed`
- `verify:` full generated-tree, render-check, CLI, and state suite under stable HEAD and measured-diff hash `3b5cae286c21834388e95d09f19824ce11f707c7` -> `104 passed`
