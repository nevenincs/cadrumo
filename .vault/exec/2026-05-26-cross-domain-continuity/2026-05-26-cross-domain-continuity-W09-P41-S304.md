---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S304'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# latent circular import between calculations.registry _applicability and deadlines _engine

## Scope

- `introduced by commit 9368c9d46`
- `not actively CLI-blocking (Python resolution order saves it) but fragile and surfaces in test_cross_domain_snapshot_registration`
- `fix via Option A factor TaxpayerModel types to a new leaf module (preferred) OR Option B lazy import guard`
- `src/aeat/domain/calculations/registry/_applicability.py`

## Description

Audited the latent circular-import path
`calculations.registry._applicability` → `deadlines._engine`.

## Outcome

Already resolved via the Step's Option A. The import in
`_applicability.py:96` reads `from ...deadlines.taxpayer_model
import (EntityType, IrpfEstimationRegime, IrpfIncomeCategory,
TaxpayerProfile)`. The `taxpayer_model.py` module is a thin
re-export of the relevant taxpayer types from
`deadlines._models`; it does not import from
`deadlines._engine`. The `_models.py` source itself only imports
from `..profile._renta_codes`, `._errors`, and `...core._models`
— no calculations-package back-edge. The leaf-module factoring
this Step recommended is in place; the circular concern is no
longer latent.

## Outcome

Closed as audit-confirmed; see Description above.

## Notes

No additional code authored by this record. The Step is closed by
inspection; the Option A factoring is production-active.

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
