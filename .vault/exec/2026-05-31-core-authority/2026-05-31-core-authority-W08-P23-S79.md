---
tags:
  - '#exec'
  - '#core-authority'
step_id: S79
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P23.S79 - remove module-scope application imports from adapter layer

## Outcome

Fixed 2 module-scope `adapters→application` edges (RELOC-032, Rule 3):

**`_profile_binding.py:21`** — replaced `from ....application.workflow._models import resolve_active_bucket_id`
with `from ....core._bucket_pointer_io import resolve_active_bucket_id`. The core version
returns `str | None`; `_profile_binding` already implements the None-guard with its own
`GoogleAuthProfileUnboundError`, so the application wrapper is not needed.

**`_oauth_flow.py:24`** — moved `from ....application.user_profile._orchestration import build_lifecycle_service, fact_value`
from module scope to a lazy local import inside `resolve_active_tax_id`, collocating it
with the existing local `read_profile_bucket_by_id` import.

### Documented structural blocks (not fixed in S79)

- `_calc_sheets_apply.py:43` and `_calc_sheets_pull.py:54-57` — Google↔calc_sheets
  cycle. Records need relocation to domain/ or core/. Documented in S74 step record.
- `auth/_authenticator.py:1146`, `auth/_clave_movil.py:746-749,860`,
  `browser/_factory.py:112`, `sede/_declarations.py:358`,
  `google/_oauth_flow.py:75` — already `local_scope` (lazy) in function bodies;
  fixing requires relocating `require_active_bucket_id` / application-layer
  orchestration functions to core — a larger refactor for a follow-up step.
- `auth/_providers.py:15` — PROTECT LIST (canonical `application.auth` imports).
- 35 test edges in Google adapter tests — mirror the structural block.

## Commit

`d38b51d05` — refactor(adapters): W08.P23.S79 - remove module-scope application imports from Google adapters

## Files touched

- `src/aeat/adapters/outbound/google/_profile_binding.py` — core import replaces application import
- `src/aeat/adapters/outbound/google/_oauth_flow.py` — module-scope application import moved to lazy local

## Verification

101 Google adapter tests pass. 14 pre-existing failures (MetadataMatchState PullResult
model regression and roundtrip failures) — unrelated to S79 changes. `ruff check` passes.
