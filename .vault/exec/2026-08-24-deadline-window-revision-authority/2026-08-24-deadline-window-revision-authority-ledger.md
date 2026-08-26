---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:0e2f1570ce8a8545ef73b938c053260be8afe62f90fc63a5a67d6c7dceaa6937'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# `deadline-window-revision-authority` ledger

## Changes

- `S01` `T` `.vault/adr/2026-08-24-deadline-window-revision-authority-adr.md`
- `S02` `T` `src/cadrumo/domain/calculations/registry/_schema.py`
- `S03` `T` `src/cadrumo/domain/calculations/registry/`
- `S04` `T` `src/cadrumo/domain/calculations/registry/_loader.py`
- `S04` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S05` `T` `src/cadrumo/domain/calculations/registry/`
- `S05` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S06` `T` `src/cadrumo/domain/calculations/registry/`
- `S06` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S07` `T` `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `S07` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S09` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S10` `T` `src/cadrumo/_data/registry/aeat/modelos/190/`
- `S11` `T` `src/cadrumo/_data/registry/aeat/modelos/193/`
- `S12` `T` `src/cadrumo/_data/registry/aeat/modelos/303/`
- `S12` `T` `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_registry.py`
- `S13` `T` `src/cadrumo/_data/registry/aeat/modelos/322/`
- `S13` `T` `src/cadrumo/domain/calculations/registry/tests/test_modelo_322_registry.py`
- `S14` `T` `src/cadrumo/_data/registry/aeat/modelos/353/`
- `S15` `T` `src/cadrumo/_data/registry/aeat/modelos/369/`
- `S16` `T` `.vault/audit/`
- `S17` `T` `src/cadrumo/_data/registry/aeat/modelos/210/`
- `S18` `T` `src/cadrumo/_data/registry/aeat/modelos/210/revisions/`
- `S19` `T` `src/cadrumo/_data/registry/aeat/modelos/210/`
- `S19` `T` `src/cadrumo/_data/registry/aeat/legal/`
- `S20` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S21` `T` `src/cadrumo/domain/calculations/registry/_authority.py`
- `S22` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S23` `T` `src/cadrumo/domain/deadlines/_plazo.py`
- `S24` `T` `src/cadrumo/domain/deadlines/_plazo.py`
- `S25` `T` `src/cadrumo/domain/deadlines/tests/`
- `S26` `T` `src/cadrumo/domain/deadlines/_engine.py`
- `S26` `T` `src/cadrumo/domain/deadlines/tests/test_engine.py`
- `S27` `T` `src/cadrumo/application/modelo/`
- `S28` `T` `src/cadrumo/application/modelo/tests/`
- `S29` `T` `src/cadrumo/application/`
- `S30` `T` `src/cadrumo/application/overview/tests/`
- `S30` `T` `src/cadrumo/application/workflow/tests/`
- `S31` `T` `src/cadrumo/entrypoints/cli/tests/`
- `S32` `T` `src/cadrumo/domain/deadlines/tests/`
- `S32` `T` `src/cadrumo/application/overview/tests/`
- `S32` `T` `src/cadrumo/application/workflow/tests/`
- `S32` `T` `src/cadrumo/entrypoints/cli/tests/`
- `S33` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S33` `T` `src/cadrumo/domain/deadlines/tests/`
- `S34` `T` `src/cadrumo/domain/calculations/registry/tests/test_modelo_*_registry.py`
- `S34` `T` `src/cadrumo/domain/deadlines/tests/test_engine.py`
- `S34` `T` `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `S34` `T` `.vault/audit/`
- `S35` `T` `src/cadrumo/`
- `S35` `T` `dev/`
- `S35` `T` `.vault/`
- `S35` `T` `current revision and owned-path evidence`
- `S36` `T` `src/cadrumo/`
- `S36` `T` `.vault/exec/`
- `S36` `T` `.vault/audit/`
- `S37` `T` `src/cadrumo/_data/registry/aeat/modelos/111/`
- `S38` `T` `src/cadrumo/_data/registry/aeat/modelos/115/`
- `S39` `T` `src/cadrumo/_data/registry/aeat/modelos/123/`
- `S40` `T` `src/cadrumo/_data/registry/aeat/modelos/130/`
- `S41` `T` `src/cadrumo/_data/registry/aeat/modelos/131/`
- `S42` `T` `src/cadrumo/_data/registry/aeat/modelos/202/`
- `S43` `T` `src/cadrumo/_data/registry/aeat/modelos/216/`
- `S44` `T` `src/cadrumo/_data/registry/aeat/modelos/349/`
- `S45` `T` `src/cadrumo/domain/deadlines/`
- `S45` `T` `src/cadrumo/entrypoints/cli/tests/`
- `S45` `T` `.vault/audit/`
- `S46` `T` `src/cadrumo/_data/registry/aeat/modelos/210`
- `S46` `T` `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`
- `S47` `T` `src/cadrumo/domain/calculations/registry/_authority.py`
- `S47` `T` `src/cadrumo/domain/calculations/registry/tests/`
- `S48` `T` `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`
- `S49` `T` `src/cadrumo/domain/calculations/registry/_authority.py`
- `S49` `T` `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
- `S50` `T` `src/cadrumo/entrypoints/cli/`
- `S50` `T` `src/cadrumo/application/overview/`
- `S50` `T` `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`
