---
name: aeat-schema-central-config
---

# AEAT schema and constants live in the central config / registry

All AEAT schema, constants, thresholds, regulatory codes, and registry-shaped data
MUST be defined in the central config or the registry authoring tree — never
inlined as Python literals in feature modules. Feature code reads from the
authority; it does not redeclare regulatory values.

## Why

AEAT regulatory values (M347 threshold, IRPF tipos, period codes, deadline
windows, casilla legal_refs, BOE article numbers, RD references, modelo revision
ids) are versioned by filing year plus revision; a Python literal bakes the value
into the call site, scatters the authority, and silently drifts on a new revision.
The compiled registry snapshot is the single source of truth, and
`cadrumo.core.config.Settings` the single deployment-settings surface, both
pydantic-validated at the boundary. Companion: `aeat-registry-authority-flow`
(the TOML→loader→schema→authority pipeline this enforces at the call-site end).

## How

- **Good:** read regulatory values through the registry authority
  (`authority.snapshot("130", filing_year=2026, period="1T")` returns a typed
  `RegistrySnapshot`); read deployment settings through
  `cadrumo.core.config.load_settings()` (honouring `override_settings()`); new
  thresholds/windows/constants land first in registry TOML under
  `src/cadrumo/_data/registry/aeat/modelos/<modelo>/...`. A one-line `from
  ...core.external_constants import M347_THRESHOLD_EUR` is acceptable for a true
  regulatory leaf constant from the curated re-export layer.
- **Bad:** `THRESHOLD = Decimal("3005.06")` inline; redeclaring period codes
  (`PERIODS = {"1T","2T","3T","4T"}`) or modelo IDs as bare-string sets (consume
  the canonical enum/tuple from `cadrumo.core.external_constants`); or hardcoding
  env-var defaults (`LIVE_TESTS_ENABLED = "0"`) instead of a `Settings`
  `Field(default=...)`.
- **Acceptable exceptions:** pure mathematical/framework constants (`CENT =
  Decimal("0.01")`, the AEAT control-letter table `TRWAGMYFPDXBNJZSQVHLCKE`,
  sentinel `Decimal("0")`); translation KEY literals (`"cli.config.google.help"`)
  are fine — but literal user-facing Spanish prose belongs in the locale files.

## Source

Operator directive recorded 2026-06-02 (autonomous-PM session,
chore/eliminate-shims). Active for every new feature module and inline-literal
remediation.
