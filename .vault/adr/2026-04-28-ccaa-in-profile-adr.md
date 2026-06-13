---
tags:
  - '#adr'
  - '#ccaa-in-profile'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - '[[2026-04-28-ccaa-in-profile-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-adr]]'
  - '[[2026-04-28-modelo-100-renta-full-calc-exec]]'
---

# `ccaa-in-profile` adr: `tax-residence profile as local JSON state` | (**status:** `accepted`)

## Problem Statement

Modelo 100 verification depends on Kent's ordinary CCAA for the autonomic general tarifa and Anexo Ñ deductions, but the project has no durable profile field for that fact. The only current option is call-site supplied CCAA, which blocks automatic RENTA verification from a dropped PDF.

## Considerations

The project already has three unrelated profile surfaces: financial usage ratios, browser sessions, and spending-category defaults. Tax residence is neither a browser profile nor a financial classification profile. It is personal local state that belongs to Kent's identity and filing context.

`#216` is changing database-backed storage in a sibling branch. This issue must not depend on that moving surface. `aeat.core.config.Settings` is stable, but pure env-var storage would make a user-facing profile command less natural and would treat identity state as process configuration.

País Vasco and Navarra are out of scope for this profile because `#424` owns foral regimes. The existing `CCAA` enum correctly excludes them, so the CLI must reject common foral spellings with a clear `ForalRegimeError`.

## Constraints

The profile model must use Pydantic v2 with `frozen=True`, `strict=True`, and `extra="forbid"`. It must consume the existing `CCAA` enum and must not duplicate autonomous-community values. Persistence must be local-state Path A, not the in-flight storage database. User-facing strings must pass through the trilingual `Translatable` pattern, with Spanish default, English explicit support, and Hungarian defaults.

## Implementation

Create a new top-level public `aeat.domain.profile` subpackage. It exports `KentTaxResidence`, `ResidenceChange`, `load_tax_residence`, `save_tax_residence`, `clear_tax_residence`, `default_path`, and the profile errors. `KentTaxResidence` carries `schema_version: str = "1"`, `ccaa: CCAA`, `tax_residence_since: date | None`, and `tax_residence_change_history: tuple[ResidenceChange, ...]`.

Persist as JSON at `XDG_CONFIG_HOME/aeat/tax-residence.json` on POSIX-like systems, `%APPDATA%\aeat\tax-residence.json` on Windows, and `~/.config/aeat/tax-residence.json` otherwise. Writes are atomic via a same-directory temporary file and `os.replace`.

Add `aeat profile show`, `aeat profile set tax-region <ccaa> --since <date>`, and `aeat profile clear`. `show --json` uses the shared CLI JSON schema registry. `set tax-region` accepts the 15 enum values and rejects `pais-vasco`, `país-vasco`, `pais_vasco`, `país_vasco`, and `navarra` with `ForalRegimeError` pointing to `#424`.

Wire `aeat filing import --from-borrador` and Modelo 100 `--from-declaracion` to load the tax-residence profile. If missing, raise `ProfileNotConfiguredError` with REFUSED exit code and the suggestion `aeat profile set tax-region <ccaa>`. For borrador, use `compute_cuota_autonomica_general(provided["0545"], residence.ccaa, año)` to validate printed `0551` when both casillas are present. Existing programmatic calculations can still pass CCAA explicitly; the profile is the CLI fallback and automation source.

Extend the setup wizard by adding a tax-region prompt and saving the tax-residence JSON alongside the existing `AutonomoProfile` and env file outputs.

## Rationale

The new `aeat.domain.profile` namespace avoids polluting existing profile surfaces and leaves the database backend untouched. JSON under the OS config directory is stable, inspectable, and easy to set from the CLI or setup wizard. The model keeps forward-compatible change history without attempting same-year multi-residency logic.

## Consequences

M100 CLI imports now require a configured ordinary CCAA profile before running autonomic RENTA checks. That is intentionally loud: without the profile, automatic verification would be silently incomplete. Foral regimes, multi-residency within a year, and per-CCAA per-deduction detail remain out of scope.
