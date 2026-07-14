---
name: aeat-spanish-stem-naming
trigger: always_on
---

# AEAT domain concepts use Spanish stems

Domain concepts that map 1:1 to AEAT surfaces MUST be named with their Spanish
stem in source code, locale keys, CLI verbs, audit-trail field names, and
`BucketEventType` values (`iva`, `renta`, `modelo`, `casilla`, `censo`,
`borrador`, `declaracion`, `justificante`, `apoderamiento`, `retencion`, `recargo
de equivalencia`, `expediente`, `sede`). Do not introduce English aliases or
English shim modules (`Vat*`, `Census*`, `Form*`, `Receipt*`) over a
Spanish-named implementation.

## Why

AEAT publishes its surfaces and regulatory text in Spanish; an English alias
layer invites drift, duplicates vocabulary in tests and locales, and silently
rots when AEAT updates the Spanish surface. Applied retroactively to the M036
census-sync rollout (planned as `Census*`, shipped as `Censo*` to match the AEAT
G313 "Mis Datos Censales"), and to the earlier `vat`→`iva` and `box`→`casilla`
renames (ADR `2026-06-02-modelo-036-census-sync-adr`).

## How

- **Good:** `cadrumo.application.live._censo` with `CensoSnapshot`,
  `CensoSnapshotService`, `CensoFactSet`, `CensoSyncError`; CLI verbs `aeat config
  profile censo refresh / show / compare / apply`; locale keys
  `cli.config.profile.censo.*`; `BucketEventType.CENSO_REFRESHED` /
  `CENSO_APPLIED` / `CENSO_DEPENDENT_STAMPED_STALE`. Plan docs authored in English
  before this rule keep their Step text for identifier stability while the
  implementation ships under the Spanish stem and the exec record names the
  Spanish symbol satisfying each Step.
- **Bad:** a new `_census.py` re-exporting `CensoSnapshot` as `CensusSnapshot`
  for "compatibility", or authoring a new ADR/plan/Step in English (`Vat*`,
  `Census*`, `Form*`) when the AEAT surface uses a Spanish noun.
- **Acceptable exceptions:** generic computing vocabulary with no AEAT counterpart
  (`repository`, `service`, `validator`, `boundary`, `snapshot`) and cross-cutting
  framework concepts (`Settings`, `Registry`, `Snapshot`) stay English.
- **Acceptable exception:** the operator-facing ledger invoice CLI noun is the
  English `invoice` by operator directive: `aeat app ledger invoice --kind
  issued|received`. Internal source-kind taxonomy remains canonical as
  `payable_invoice` and `collectible_invoice`; do not collapse those into a bare
  `invoice` source kind.

## Source

Operator directive 2026-06-02; ADR `2026-06-02-modelo-036-census-sync-adr`.
Invoice CLI exception: `2026-06-10-ledger-invoice-unification-adr`. Active for
every new AEAT-surface symbol; already-public pre-rule identifiers keep their
names.
