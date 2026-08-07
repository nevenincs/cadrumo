# AEAT domain concepts use Spanish stems

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

## How

- **Good:** `CensoSnapshot`, `CensoSnapshotService`, `CensoFactSet`,
  `CensoSyncError`; the CLI verbs `aeat config profile censo file` and
  `censo pull` (per `aeat-cli-pull-and-file-standard`, a fetch is `pull` and a
  local artefact is `--file` — never `refresh`); locale keys
  `cli.config.profile.censo.*`; event types `CENSO_APPLIED` and
  `CENSO_DEPENDENT_STAMPED_STALE`. A plan authored in English before this rule
  keeps its Step text for identifier stability while the implementation ships
  under the Spanish stem.
- **Bad:** a new `_census.py` re-exporting `CensoSnapshot` as `CensusSnapshot`
  for "compatibility", or authoring a new ADR, plan or Step in English when the
  AEAT surface uses a Spanish noun.
- **Acceptable exceptions:** generic computing vocabulary with no AEAT
  counterpart (`repository`, `service`, `validator`, `boundary`, `snapshot`) and
  cross-cutting framework concepts (`Settings`, `Registry`, `Snapshot`) stay
  English.
- **Acceptable exception, by operator directive:** the operator-facing ledger
  invoice CLI noun is the English `invoice` (`aeat app ledger invoice --kind
  issued|received`). The internal source-kind taxonomy stays canonical as
  `payable_invoice` / `collectible_invoice`; do not collapse those into a bare
  `invoice` source kind.

Already-public pre-rule identifiers keep their names. Companions:
`aeat-source-hygiene` (the reserved word "binding"),
`cadrumo-product-authority-names`.
