---
name: aeat-naming
trigger: always_on
---

# AEAT domain naming and product identity

## Domain concepts use Spanish stems

Domain concepts that map 1:1 to AEAT surfaces MUST be named with their Spanish
stem in source code, locale keys, CLI verbs, audit-trail field names and event
type values: `iva`, `renta`, `modelo`, `casilla`, `censo`, `borrador`,
`declaracion`, `justificante`, `apoderamiento`, `retencion`, `recargo de
equivalencia`, `expediente`, `sede`. Do not introduce English aliases or English
shim modules (`Vat*`, `Census*`, `Form*`, `Receipt*`) over a Spanish-named
implementation.

AEAT publishes its surfaces and regulatory text in Spanish. An English alias
layer invites drift, duplicates vocabulary in tests and locales, and silently
rots when AEAT updates the Spanish surface.

**Acceptable exceptions:** generic computing vocabulary with no AEAT counterpart
(`repository`, `service`, `validator`, `boundary`, `snapshot`) and cross-cutting
framework concepts (`Settings`, `Registry`, `Snapshot`) stay English.
**By operator directive**, the operator-facing ledger invoice CLI noun is the
English `invoice` (`aeat app ledger invoice --kind issued|received`), while the
internal source-kind taxonomy stays canonical as `payable_invoice` /
`collectible_invoice` — do not collapse those into a bare `invoice` source kind.

Already-public pre-rule identifiers keep their names.

## Product identity versus the tax authority

Use `Cadrumo` in sentence prose and `CADRUMO` in identity contexts for
application-owned surfaces, and retain AEAT names when the referent is the
Spanish tax authority, its official evidence, or its external protocol. The sole
human CLI executable is the exact lowercase token `aeat` — it names the Cadrumo
command contract, not a legacy product alias.

Classifying by spelling alone creates contradictions even for apparently obvious
settings; classify by **ownership and referent** instead, which prevents both
stale branding and corrupted tax-authority semantics.

## How

- **Good:** `CensoSnapshot`, `CensoSnapshotService`, `CensoFactSet`,
  `CensoSyncError`; the CLI verbs `aeat config profile censo file` and
  `censo pull` (a fetch is `pull` and a local artefact is `--file`, per
  `aeat-cli-contract` — never `refresh`); locale keys
  `cli.config.profile.censo.*`; event types `CENSO_APPLIED` and
  `CENSO_DEPENDENT_STAMPED_STALE`.
- **Good:** rename an application-controlled `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR`
  setting to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`, while retaining AEAT names
  inside the authority payload stored there.
- **Good:** keep `adapters.outbound.aeat`, official AEAT URLs, legal provenance
  and the `registry/aeat` taxonomy under the CADRUMO package root; invoke the
  human CLI as `aeat` and import the package as `cadrumo`.
- **Bad:** a new `_census.py` re-exporting `CensoSnapshot` as `CensusSnapshot`
  for "compatibility", or authoring a new ADR or plan in English when the AEAT
  surface uses a Spanish noun.
- **Bad:** globally replacing every `AEAT` token with `CADRUMO`, changing the
  name of the authority or of byte-exact official evidence.
- **Bad:** retaining `aeat` for a product import, environment prefix, or storage
  owner, or exposing `cadrumo` as a second human executable.

Source: ADR `2026-07-12-cadrumo-cli-executable-adr`; audit
`2026-07-12-cadrumo-product-rename-audit`; ADR
`2026-06-02-modelo-036-census-sync-adr`.
