---
tags:
  - '#audit'
  - '#modelo-inventory'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
  - "[[2026-04-17-modelo-inventory-remediation-adr]]"
  - "[[2026-04-17-modelo-inventory-remediation-phase-all-summary-exec]]"
---

# `modelo-inventory` audit: `legacy plan status reconciliation`

## Scope

Reconciled the unchecked acceptance checklist in
`2026-04-13-modelo-inventory-plan` against its original ADR and audit,
the accepted `2026-04-17-modelo-inventory-remediation-adr`, its phase-all
summary and audit, and the current registry-backed implementation. Semantic
discovery located the current registry authority, censo ownership, annual
`123 -> 193` relationship, and operator discovery surfaces before exact
symbol confirmation.

Current-state verification ran the real committed-registry tests for censo,
Modelo 193, Modelo 347, and canonical applicability: 61 passed. This audit
does not claim a current whole-repository quality-gate result.

## Findings

### legacy-plan-status-reconciliation | high | The apparent zero-percent plan is a parser artifact, not open delivery

`vaultspec-core vault plan status` classifies the April document as a legacy
plan with zero Waves, Phases, and Steps, so it reports 0/0 rather than
interpreting the prose checklist. The original phase-all exec records are
therefore unlinked by the structural graph. The original audit records the
nine conventional commits and all eighteen acceptance outcomes as delivered;
the remediation ADR then explicitly invalidated parts of that first delivery
and the remediation summary/audit records the corrective completion. The
legacy plan must not be read as an active zero-percent backlog.

### legacy-plan-status-reconciliation | high | Every unchecked legacy criterion is historically reconciled

| Legacy criterion | Reconciled status | Evidence and current authority |
| --- | --- | --- |
| `ModeloCode` fixed 20-member `StrEnum` | Delivered, then superseded | The original audit proves the 20-member delivery. `domain.modelos.ModeloCode` is now a three-digit value object and the registry resolves filing availability by revision; a fixed 20-code enum is no longer the contract. |
| Strict `ModeloMetadata` | Delivered, then superseded | The original strict record was delivered. `ModeloDefinition` and `ModeloRevision` now provide the revision-aware registry schema. |
| `LegalCitation` text invariant | Delivered, then superseded | The original audit proves the validator. Current revision metadata uses validated `legal_refs`, `source_refs`, and mandatory `orden_aplicabilidad`, with registry load gates. |
| Eight-profile applicability partition | Delivered, then superseded | The original partition was delivered. Current `ModeloApplicability` derives four honest verdicts from the taxpayer model; its explicit seed-coverage notice prevents a false claim of universal coverage. The old fixed matrix is not an active implementation row. |
| Twenty populated entries | Delivered, then superseded | The original inventory was delivered; remediation added 193 and withdrew 037 from active registry support. Current authority is the registry tree, not twenty Python entry modules. |
| Frozen `MODELO_REGISTRY` and `caps_into` | Delivered, then superseded | The original import-time map was delivered. `ValidatedRegistryAuthority` now validates and snapshots revisioned TOML definitions; the 193-to-123 relation is an explicit annual-summary dependency. |
| `get_modelo` / `modelos_for_profile` / `year_plan` | Delivered, then superseded | The old helpers were delivered. `RegistryQueryService`, `ValidatedRegistryAuthority.validate_modelo`, and `snapshot` are the current read boundary. |
| `AeatError`-rooted registry errors | Delivered, then superseded | The original hierarchy was delivered. Current boundaries use `ModeloError` / `ModeloValidationError` plus registry validation and snapshot errors. |
| Casilla catalogue cross-reference | Delivered, then superseded | The original test was delivered. Current committed registry tests validate model data, references, and snapshots; 037 is expressly absent from active sources. |
| Four-command `aeat modelos` CLI | Delivered, then superseded | The old surface was delivered. Current discovery commands are registry-backed `list`, `describe`, `casillas`, formula/binding inspection, and `support-matrix`, with strict envelopes. |
| `es` / `en` / `hu` display labels | Delivered, then superseded | The original audit proves the entry-label contract. Localised output and registry schema labels are now separate concerns, so the removed entry model is not a current acceptance shape. |
| Fifteen-symbol public `__all__` | Delivered, then superseded | The original facade was delivered. `domain.modelos` is now the filing aggregate facade, while the registry has its own public facade. |
| Unit-marked, no-double test suite | Delivered, then superseded | The original audit proves that suite's discipline. Current tests are organised under the current domain and registry contracts; this old file-layout requirement is not a backlog item. |
| Google docstrings and full annotations | Delivered, then superseded | The original audit proves the legacy surface. Current public surfaces document the registry and filing aggregate instead. |
| Conventional commits | Historically delivered | The original audit names all nine commits, and `git log` retains the corresponding #108 history. This is immutable delivery provenance, not current work. |
| Four original quality gates | Historically delivered | Both the original and remediation audits record green Windows gates. The focused current 61-test proof establishes relevant behaviour only; the old gate result must not be presented as a current gate. |
| No workflow-file addition | Superseded wording; historical no-add delivered | The original audit records the pre-existing `ci.yml`; the current `.github/workflows` directory exists. The literal old text is not a current filesystem assertion, but there is no active #108 workflow task. |
| No new configuration settings | Historically delivered | The original delivery audit's scoped change map records no settings work. Later repository configuration cannot reopen this feature-specific criterion. |

No unchecked criterion remains genuinely active in the April plan. The one
materially narrower current capability, full per-entity/per-regime
applicability, is deliberately represented as an incomplete verdict in the
current registry contract; it must be managed by a current, separately
grounded initiative rather than by reviving the legacy checklist.

## Recommendations

Treat `2026-04-13-modelo-inventory-plan` as reconciled historical delivery,
not as an in-flight plan. Preserve its unchecked prose checklist as historical
evidence; do not mechanically tick items whose exact architecture has been
superseded. Use this audit and the accepted remediation records when curating
active-status views, while retaining the old ADR and execution records for
traceability.
