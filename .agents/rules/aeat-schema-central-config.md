---
name: aeat-schema-central-config
trigger: always_on
---

# AEAT schema and constants live in the central config / registry

All AEAT schema, constants, thresholds, regulatory codes, and
registry-shaped data MUST be defined in the central config or the
registry authoring tree — never inlined as Python literals in feature
modules. Feature code reads from the authority; it does not redeclare
regulatory values.

## Why

AEAT regulatory values (M347 threshold, IRPF tipos, period codes,
deadline windows, casilla legal_refs, BOE article numbers, RD
references, modelo revision identifiers) are versioned by filing year
plus revision. A Python literal in a feature module bakes the value
into the call site, scatters the authority across the codebase, and
silently drifts when AEAT publishes a new revision. The compiled
registry snapshot is the single source of truth; the central
:class:`aeat.core.config.Settings` is the single source of deployment
settings. Both are pydantic-validated at the boundary so a feature
module that reads them gets a typed record, not a raw string.

The companion rule `aeat-registry-authority-flow` defines the
TOML-authoring → loader/compiler → strict-schema → validated-authority
pipeline that this rule enforces at the call-site end.

## How

- **Good:** read AEAT regulatory values through the registry
  authority. `authority.snapshot("130", filing_year=2026, period="1T")`
  returns a typed `RegistrySnapshot` carrying every casilla, formula,
  legal_ref, and source_ref. Feature code consumes the typed record.

- **Good:** read deployment settings through
  `aeat.core.config.load_settings()` (which honours
  `override_settings()` for tests). The `Settings` pydantic model is
  the single config surface; per-axis env vars are validated there
  once and surfaced as typed fields.

- **Good:** new AEAT thresholds, deadline windows, or per-modelo
  constants land first in the registry TOML under
  `src/aeat/_data/registry/aeat/modelos/<modelo>/...` and ride through
  the loader/compiler. Feature code reads the compiled snapshot.

- **Good:** a one-line `from ...core.external_constants import
  M347_THRESHOLD_EUR` is acceptable when the constant is a true
  regulatory value pulled from the central authoring surface
  (`external_constants` is the curated re-export layer for the small
  set of leaf constants that are easier to consume by-name than via
  the registry).

- **Bad:** writing `THRESHOLD = Decimal("3005.06")` inline in a
  feature module. The threshold is a regulatory value; if AEAT moves
  it, this literal silently drifts.

- **Bad:** redeclaring period codes (`PERIODS = {"1T", "2T", "3T",
  "4T"}`) or modelo IDs as bare-string sets / frozen-sets in feature
  modules. The closed set lives in `aeat.core.external_constants`
  (or the registry); consume the canonical enum / tuple.

- **Bad:** hardcoding env-var defaults (`LIVE_TESTS_ENABLED = "0"`)
  in feature modules. Those belong on the `Settings` model with a
  `Field(default=...)` declaration.

- **Acceptable exceptions:** pure mathematical or framework constants
  (`CENT = Decimal("0.01")`, the AEAT control-letter table
  `TRWAGMYFPDXBNJZSQVHLCKE`, sentinel zero `Decimal("0")`). Translation
  KEY literals (`"cli.config.google.help"`) are fine; literal
  user-facing Spanish prose is not — the locale files are the
  authority for that.

## Status

Active. Applies to every new feature module and to remediation of
existing inline-literal call sites discovered by the rolling audit
swarm.

## Source

Operator directive recorded 2026-06-02 during the autonomous-PM
session driving the chore/eliminate-shims branch.
