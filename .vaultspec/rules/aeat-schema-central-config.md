# AEAT schema and constants live in the central config or registry

All AEAT schema, constants, thresholds, regulatory codes, and registry-shaped
data MUST be defined in the central config or the registry authoring tree —
never inlined as Python literals in feature modules. Feature code reads from the
authority; it does not redeclare regulatory values.

## Why

AEAT regulatory values (thresholds, tipos, period codes, deadline windows,
casilla `legal_refs`, BOE article numbers, revision ids) are versioned by filing
year plus revision. A Python literal bakes the value into the call site,
scatters the authority, and silently drifts on a new revision. The compiled
registry snapshot is the single source of truth and `Settings` the single
deployment-settings surface, both pydantic-validated at the boundary.

## How

- **Good:** read regulatory values through the registry authority
  (`authority.snapshot(...)` returns a typed `RegistrySnapshot`); read deployment
  settings through `load_settings()`, honouring `override_settings()`. New
  thresholds, windows and constants land first in registry TOML. A one-line
  import from the curated `core.external_constants` re-export layer is acceptable
  for a true regulatory leaf constant.
- **Bad:** an inline `THRESHOLD = Decimal("3005.06")`; redeclaring period codes
  or modelo ids as bare-string sets instead of consuming the canonical enum;
  hardcoding an env-var default instead of a `Settings` field.
- **Acceptable exceptions:** pure mathematical or framework constants, the AEAT
  control-letter table, sentinel zeros; and translation KEY literals — but
  literal user-facing prose belongs in the locale files.

Companions: `aeat-registry-authority-flow`, `modelo-identifiers-use-core-enum`.
