---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S551
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P36.S551`

Added `CAST-RATIONALE-*` inline markers to three production sites where `Any` is unavoidable at an external or polymorphic boundary.

- Modified: `src/aeat/adapters/inbound/justificante/_extract.py`
- Modified: `src/aeat/application/live/_borrador_100.py`
- Modified: `src/aeat/core/profile.py`

## Description

Each site received a block comment using the `CAST-RATIONALE-*` naming convention established in the W2.P13 inventory:

- `_extract.py` at `TypeAdapter(AnyHttpUrl).validate_python(...)`: pydantic's `TypeAdapter.validate_python` returns `Any` in its public stubs; the function's own `-> AnyHttpUrl` annotation narrows at the caller boundary. Marker: `CAST-RATIONALE-JUSTIFICANTE-EXTRACT-TYPEADAPTER`.

- `_borrador_100.py` `_derive_snapshot_id(self, **kwargs: Any)`: the `SnapshotService[T]` abstract hook contract uses `**kwargs` to allow subclass-specific keyword arguments without a shared typed parameter set. Marker: `CAST-RATIONALE-BORRADOR100-SNAPSHOT-DISPATCH`.

- `core/profile.py` `_parse_iva_regime(cls, value: object) -> Any`: pydantic `@field_validator(mode="before")` requires `-> Any`; the post-coercion value is validated against the field's declared type by pydantic. The return type cannot be narrowed because `IVARegime` is resolved lazily via `_m()` to avoid a circular import. Marker: `CAST-RATIONALE-PROFILE-FIELD-VALIDATOR-ANY`.

## Tests

No new tests for the markers themselves; the markers act as documentation sentinels. The inventory test pattern (asserting marker presence) is documented as an optional follow-up in the plan.
