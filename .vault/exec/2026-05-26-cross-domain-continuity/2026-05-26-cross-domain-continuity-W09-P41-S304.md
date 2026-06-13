---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S304'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




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

