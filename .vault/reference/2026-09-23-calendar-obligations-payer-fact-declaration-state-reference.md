---
tags:
  - '#reference'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:790fb5329b4688363331463b46178d1bfb03fa28a05cd82f82335ea192f61c8d'
related: []
---

# `calendar-obligations` reference: `payer-fact declaration state and per-window profile predicates`

Code and registry grounding for the payer-fact declaration state and the per-quarter Modelo 136 gate, read on 2026-09-23 at `ae58608c62`.

## Summary

**The payer fact is a boolean.**
- `payer_fact_holds` (`src/cadrumo/domain/calculations/registry/applicability_payer_facts.py:213`) reads the profile attribute named by the dated projection and requires a `bool`.
- `ModeloApplicabilityRule._payer_fact_result` (`src/cadrumo/domain/calculations/registry/applicability.py:329`) returns INCOMPLETE whenever it is `False`, through `_undetermined_applicability` (`src/cadrumo/domain/calculations/registry/applicability.py:641`), whose docstring states that payer facts have no tri-state.

**A stored `false` is not provably an answer.**
- The setup confirm question defaults to `"false"` (`src/cadrumo/application/wizard/catalogue.py:41`).
- A stored fact's `source` defaults to `manual_cli` (`src/cadrumo/domain/user_profile/values.py:244`).

**Schema version is pinned.** The profile schema is version 6 (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:3`). `validate_profile_schema_identity` (`src/cadrumo/domain/user_profile/values.py:273`) refuses both future and pre-current payload versions on read.

**A three-state parse already exists.** `_parse_optional_bool` (`src/cadrumo/domain/deadlines/profiles.py:540`) returns `None` for an absent value, which is the precedent for an optional boolean profile field.

**Delimited multi-token values have a precedent.** IRPF income categories are a delimited string validated at the boundary (`src/cadrumo/domain/deadlines/profiles.py:782`).

**Windows are gated per window by typed predicates.**
- `_obligation_for_window` (`src/cadrumo/domain/deadlines/engine.py:308`) filters each deadline window by its filing schedules and its `applicability_conditions`.
- The schedule-predicate operations are `equals` and `not_equals` only (`src/cadrumo/domain/calculations/registry/schema_verification.py:134`). The `EQUALS` at `:856` belongs to a different, verification-rule enum.

**Only APPLICABLE earns a calendar row.** The calendar lists INCOMPLETE and NOT_APPLICABLE modelos as suppressed, with their reason (`src/cadrumo/application/overview/calendar.py:1047`).

**Modelo 136 grounding** (`src/cadrumo/_data/registry/aeat/legal/modelo-136.toml`):
- `orden-hap-70-2013:art-6` (line 45) makes the modelo owed only when the prize was not subject to retención or ingreso a cuenta.
- `orden-hap-70-2013:art-7` (line 65) sets quarterly windows for prizes cashed in the preceding quarter.
- `ley-35-2006:da-33` (line 1) is the gravamen especial.

**Modelo 136 registry shape.** The 136 editions declare a quarterly filing schedule and one deadline window per quarter (`src/cadrumo/_data/registry/aeat/modelos/136/revisions/2022-2025/deadline_windows/0001-declarations.toml`, and the 2026 edition). Its 2022-2025 applicability declares no `required_payer_fact` (`src/cadrumo/_data/registry/aeat/modelos/136/revisions/2022-2025/applicability/0001-declarations.toml`).
