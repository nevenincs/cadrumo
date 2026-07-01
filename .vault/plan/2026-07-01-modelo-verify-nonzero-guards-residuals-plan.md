---
tags:
  - '#plan'
  - '#modelo-verify-nonzero-guards-residuals'
date: '2026-07-01'
modified: '2026-07-01'
tier: L2
related:
  - '[[2026-07-01-modelo-verify-nonzero-guards-residuals-adr]]'
  - '[[2026-07-01-modelo-verify-nonzero-guards-residuals-research]]'
---

# `modelo-verify-nonzero-guards-residuals` plan

### Phase `P01` - M202 casilla-33 DA-14 legal grounding

Author the LIS Disposicion Adicional Decimocuarta legal-catalogue entry and consolidated-corpus excerpt (Ley 6/2018 art. 71 redaccion) and add it to casilla 33 legal_refs on all three M202 revisions, closing the registry-calculation-legal-grounding gap identified in the residuals research. No verify guard is added.

- [x] `P01.S01` - Author DA-14 corpus excerpt and is.toml legal entry and add to casilla 33 legal_refs on all three revisions; `verify registry loads and legal-grounding evidence gate passes; `src/aeat/_data/corpus/normatives/html/ley-27-2014-da-14.html, src/aeat/_data/registry/aeat/legal/is.toml, src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/casillas/0049-33.toml, src/aeat/_data/registry/aeat/modelos/202/revisions/2023-2024/casillas/0042-33.toml, src/aeat/_data/registry/aeat/modelos/202/revisions/2019-2022/casillas/0042-33.toml`.

### Phase `P02` - Canary tests pinning the three documented non-guards

Add real-behaviour canary tests that assert the three documented non-guards (M202 c33 minimo, M714 base-imponible to base-liquidable, M714 total-cuota-integra to cuota-a-ingresar) remain unguarded, each citing the residuals research by name so a future prerequisite landing is forced to revisit the decision.

- [x] `P02.S02` - Add canary tests pinning the three documented non-guards, each citing the residuals research by name; `src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py, src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`.

## Description

## Steps

## Parallelization

## Verification
