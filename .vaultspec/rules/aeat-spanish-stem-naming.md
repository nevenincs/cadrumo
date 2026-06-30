---
name: aeat-spanish-stem-naming
---

# AEAT domain concepts use Spanish stems

Domain concepts that map 1:1 to AEAT surfaces MUST be named with their
Spanish stem in source code, locale keys, CLI verbs, audit-trail field
names, and `BucketEventType` values. Do not introduce English aliases
or English shim modules over a Spanish-named implementation.

## Why

AEAT publishes its surfaces, regulatory text, and operator-visible
labels in Spanish. The codebase's load-bearing concepts already follow
the Spanish stem (`iva`, `renta`, `modelo`, `casilla`, `censo`,
`borrador`, `declaracion`, `justificante`, `apoderamiento`,
`retencion`, `recargo de equivalencia`, `expediente`, `sede`). Naming
the implementation in the language of the surface it integrates with
keeps the developer mental model aligned with AEAT documentation; an
English alias layer (`Vat*`, `Census*`, `Form*`, `Receipt*`, etc.)
invites drift, duplicates vocabulary in tests and locales, and
silently rots when AEAT updates the Spanish surface.

The convention was applied retroactively to the M036 census-sync
rollout — the plan was authored in English (`Census*`) but the
implementation shipped under `Censo*` to match the AEAT G313 page
title "Mis Datos Censales". The same retroactive resolution applies
to the earlier `vat` → `iva` and `box` → `casilla` renames.

## How

- **Good:** `aeat.application.live._censo` with `CensoSnapshot`,
  `CensoSnapshotService`, `CensoFactSet`, `CensoSyncError`. CLI verbs
  `aeat config profile censo refresh / show / compare / apply`.
  Locale keys `cli.config.profile.censo.*` across all four target
  languages. `BucketEventType.CENSO_REFRESHED`, `CENSO_APPLIED`,
  `CENSO_DEPENDENT_STAMPED_STALE`.

- **Good:** `aeat.domain.iva` with `IvaCategory`, `IvaRateKind`,
  `IvaFlowDirection`, `IvaInvoiceClassification`. CLI verbs and
  locale keys under `cli.ledger.iva.*`. `BucketEventType.IVA_*`.

- **Good:** plan documents authored before this rule may keep their
  English Step text verbatim for identifier stability; the
  implementation ships under the Spanish stem and the exec record
  explicitly names the Spanish symbol that satisfies each English-
  named Step (the M036 closure on commit
  `exec(modelo-036-census-sync): close P02+P03+P04+P06` is the
  canonical reference for this pattern).

- **Bad:** introducing a new `_census.py` module that re-exports
  `CensoSnapshot` as `CensusSnapshot` for "compatibility." There is
  no compatibility surface to preserve; the Spanish stem is the
  canonical name.

- **Bad:** authoring a new ADR / plan / Step in English (`Vat*`,
  `Census*`, `Form*`) when the AEAT surface uses a Spanish noun.
  Use the Spanish stem at authoring time and avoid the retroactive
  resolution.

- **Acceptable exceptions:** generic computing vocabulary that has
  no AEAT counterpart (e.g. `repository`, `service`, `validator`,
  `boundary`, `snapshot`) stays English. Cross-cutting framework
  concepts that bind multiple AEAT domains (e.g. `Settings`,
  `Registry`, `Snapshot`) stay English where the English word is the
  framework convention.

- **Acceptable exception:** the operator-facing ledger invoice CLI noun is
  the English `invoice` by direct operator directive:
  `aeat app ledger invoice --kind issued|received`. Internal source-kind
  taxonomy remains canonical and load-bearing as `payable_invoice` and
  `collectible_invoice`; do not collapse those internal strings into a bare
  `invoice` source kind.

## Status

Active. Applies to every new domain symbol, locale key, CLI verb,
audit-trail field, and `BucketEventType` value that names an AEAT
surface. Pre-rule artefacts whose English naming is already public
keep their identifiers for stability; the implementation underneath
must use the Spanish stem.

## Source

Operator directive recorded 2026-06-02 during the autonomous-PM
session driving the chore/eliminate-shims branch, formalising the
convention applied to the M036 census-sync rollout
(sibling ADR `2026-06-02-modelo-036-census-sync-adr`).
Invoice CLI exception recorded in
`2026-06-10-ledger-invoice-unification-adr`.
