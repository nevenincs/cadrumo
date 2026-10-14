---
tags:
  - '#audit'
  - '#domain-boundary-audit'
date: '2026-06-01'
modified: '2026-10-14'
body_hash: 'sha256:b9bb855f2ed235f9d8a212fa4ac1854597c98cf38adbbe45040405498074cda7'
related: []
---
# `domain-boundary-audit` audit: `Domain ownership and cross-boundary outlier audit`

## Scope, method, and status

This rolling ledger compares what `domain` and `application` packages claim to own with where each
functional concept actually lives. Discovery used vaultspec-rag semantic clusters, then `rg` to
confirm exact symbols and constraints. A substitutability check separates true duplication from
similarly named types whose accepted values or failure contracts differ. Findings retain stable DB
ids, severity, and their latest recorded disposition; a closed campaign step does not imply every
related architectural question is closed.

Initial inventory: 22 domain packages / 552 Python files; 25 application packages / 401 Python
files; 1,701 first-party modules across the broader inventory. The audit began 2026-06-01 with
DB-01–DB-40 and appended DB-41–DB-44 during execution. Cross-boundary findings distinguish runtime
edges from deferred imports. Running-log dates and Step IDs below are historical evidence, not
current certification.

## Findings ledger

### DB-01 (MEDIUM) — `profile` / `user_profile` / renta family-facts have no single canonical home

`domain/profile` combined legitimate tax-residence facts, M100/renta family facts, and
inventory/asset/amortization errors; 23+ importers made relocation atomic. S61/S62 moved asset and
inventory errors. On 2026-06-03, operator-confirmed S63 atomically renamed the package to
`domain/contribuyente` across 90 paths after a quiescent-tree check; documentation stubs were
regenerated and a post-rename sweep found zero production references to `domain.profile`,
`profile_catalogue`, or `application.topics`. D7 and the structural rename sequence are complete.
The stable `core.profile.errors.*` locale key remains intentionally unchanged; family records
remain taxpayer facts and were not moved to `renta`.

### DB-02 (LOW / EXCLUDED) — `invoices` and `transactions` are shared-vocabulary twins, not a duplication cluster

Shared vocabulary masks different model shapes and relationships. Substitutability check excluded
this as a duplication cluster; no consolidation.

### DB-03 (LOW) — `domain/modelos` docstring under-claims the package's real surface

The package docstring under-described the actual repository/identity surface. Documentation
correction was queued under R2; later execution rewrote the surface description. Closed as doc
drift.

### DB-04 (NOTE) — `modelos` (plural) vs `modelo` (singular) pluralization split is intentional but undocumented

Plural domain package and singular application workflow express different layer roles. The split is
intentional but needed documentation; no code rename.

### DB-05 (HIGH) — duplicate `declaration_key` / `update_declaration_pointer` in `application/workflow` with silent key divergence

Two workflow definitions could diverge silently. S68 deleted the dead `_engine` copy and retained
the richer `_models` behavior; S69 added a production-definition AST gate and case-folding behavior
check. 100 workflow tests passed and `ty` was clean. Closed.

### DB-06 (MEDIUM) — period parsing re-implemented in `application` against `domain/period.py`

Application parsers are similar to `domain/period.py` but not substitutable: aggregation accepts
`YYYY-Q1` while domain uses `YYYYQ1`; month-end choices also differ. S71 was excluded from dedup
because those semantics differ. S70 remains conditionally actionable only after verifying
raise-versus-`None` behavior in the safety path. No blind parser unification.

### DB-07 (MEDIUM) — `application/topics` types force a `core → application` upward import (hexagonal inversion)

The topics catalogue belonged in the shared kernel. S54 moved it from `application/topics` to
`core/topics`, deleted the old package without a shim, repointed consumers, and updated registry/doc
stubs. 26 focused tests, full collect-only, `ty`, docs, and the Core-not-outer contract passed.
Closed.

### DB-08 (MEDIUM) — `application/wizard/_verifier` re-derives `SituacionFamiliar` legal rule

Wizard verification duplicated the legal `SituacionFamiliar` rule. It now delegates to the canonical
`conjunta_eligible` / `monoparental_required` predicates; 273 tests passed. Closed.

### DB-09 (LOW-MEDIUM) — `setup` accepts `iva_regime` as bare `str`, bypassing the `IVARegime` enum

Raw strings bypassed the closed `IVARegime` enum. Typed enum validation and case-folding were added.
Closed.

### DB-10 (LOW) — `operator_surface.SourceKind` duplicates `core.aggregation.AggregationSourceKind`

The operator-surface set is narrower, intentionally excluding invoice cases. Preserve the narrower
contract with a derived `Literal`/frozen set if useful; do not alias a broader enum and silently
expand accepted values. Deferred/excluded by substitutability.

### DB-11 (LOW-MEDIUM) — `IvaInvoiceClassification` export asymmetry across `iva` and `invoices`

`invoices` and `iva` had an asymmetric public surface, with consumers reaching private
classification symbols. S21 exported `IvaInvoiceClassification`, `classify_invoice_line_for_iva`,
and `invoice_line_to_iva_observation` from public `iva`, then repointed `invoices` callers. Both
packages imported cleanly with no cycle; 332 iva/invoices tests passed, `ty` was clean, and no
external private-module reach-ins remained. DB-11 and its linked structural/export concern are
closed; no residual relocation is recorded.

### DB-12 (MEDIUM) — `domain/normatives` docstring promises a `NORMATIVE_CATALOGUE` singleton that does not exist

`domain/normatives` documentation promised a `NORMATIVE_CATALOGUE` singleton that did not exist. The
package surface/docstring was corrected. Closed.

### DB-13 (MEDIUM) — `domain/auth` parent package exposes none of the surface its docstring claims

`domain/auth` docstring claimed a package API that its parent did not export. Public surface and
consumers were corrected. Closed.

### DB-14 (NOTE) — closed regulatory value sets live in `application/aggregation` instead of `core/`

Closed value sets appear above core, but only one package consumes them and no behavior is
duplicated. Retain as a placement note for any regulatory-values ruling, not a relocation defect.

### DB-15 (NOTE) — `operator_surface.ModeloLifecycleStep` is the only typed filing-lifecycle vocabulary

This is the sole typed filing-lifecycle vocabulary and does not establish duplication. Informational
only.

### DB-16 (HIGH cluster) — `domain` repository implementations depend on `adapters.persistence.storage`

Six runtime imports and about 100 deferred references were found across repositories. The 2026-06-03
D4 ruling accepts domain-co-located encrypted repository implementations importing the public
storage surface, while excluding underscore-private submodule imports. W11 repointed 15 repositories
to the top-level `storage` API and removed a double-private envelope access. This is governed
architectural debt, not an invitation to move repositories piecemeal.

### DB-17 (MEDIUM) — `domain/profile/_keys.py` imports `application.wizard` (worst-direction edge)

The one production `domain → application` edge was the lazy profile-key pull. A first removal proved
registration order was load-bearing; the wizard-registration bootstrap ADR then supplied eager
registration, and S64 removed the pull safely. Closed with 748 focused tests/related checks and
collection evidence.

### DB-18 (MEDIUM cluster) — `core/resources/_repos` inverts `core → domain`/`application`

Topics and apoderamientos were moved/repointed to core-owned surfaces. After S54,
`core/resources/_repos` had zero application imports; the core-not-outer contract remained kept.
Core/profile renames are tracked separately under DB-28/39. Main identified inversion closed.

### DB-19 (NOTE / needs ADR) — `application → adapters` is a pervasive direct-concretion dependency

A broad application-to-adapter concretion pattern was measured. This is an architecture decision,
not a mechanical cleanup; retain it for the persistence-boundary ADR rather than editing imports one
at a time.

### DB-20 (HIGH) — IVA compensation (Modelo 303) is a domain concept with no domain package

Modelo 303 FIFO carry-forward, the four-year LIVA art. 99.5 window, wallet/recurrence/override
decisions, casilla mapping, and derived compensation rules lived in application/adapters with
duplicated formulas. S89 documented the full blast radius; execution created
`domain/iva_compensation` and moved the domain algorithm/authority. Focused tests, typing, and
collection were checked. The domain-home finding is closed; preserve the audit’s source/legal
grounding and do not treat structural tests as legal attestation.

### DB-21 (HIGH) — `domain/calculations/registry` public surface is systematically bypassed

The registry package public surface was bypassed by private-submodule imports. The initial count
of 38 included docstring matches; the corrected source-import count was 33, and 29 modules were
repointed to `domain.calculations.registry`. `_loader` remained private because of a cycle. Symbol
membership was checked against `__all__` and full collection passed. Closed for the measured
consumers.

### DB-22 (MEDIUM) — `application/verification` encodes registry-derived classification policy

Application verification carried classification policy derived from registry data. Preserve as a
policy-placement follow-up; no separate final closure was recorded in the running log.

### DB-23 (LOW) — `application/review.LedgerReviewIssue` duplicates `application/transactions.LedgerImportDiagnosticKind`

`LedgerReviewIssue` and `LedgerImportDiagnosticKind` overlapped. The vocabulary was collapsed; 184
tests passed. Closed.

### DB-24 (LOW) — `application/registry.RegistryManualId` is a constraint-narrowing duplicate of `ManualId`

This type deliberately accepts a strict subset. Substitutability excludes consolidation; keep its
constraint rather than broaden it.

### DB-25 (LOW) — calc-sheets re-decodes registry rounding-code and parameter-temporal vocabulary

Calc-sheets repeats registry rounding/parameter-temporal vocabulary. Retain as a candidate only
where constraint shapes are truly substitutable; no separate closure was recorded.

### DB-26 (MEDIUM cluster) — application-result ↔ entrypoint-payload twin DTOs share names

Application `BaseModel` results and CLI `OutputSchema` payloads shared names and often copied
fields. S49/S50/S52 and S51 completed the measured 1:1 collapses; remaining boundary-correct payload
adapters were renamed/translated with `from_result`. JSON shape and collection checks were retained.
Closed for the audited pairs; wire contracts remain explicit.

### DB-27 (NOTE) — `PortalRow` name collision across `adapters` (ORM) and `application` (DTO)

The adapter ORM row and application projection have different bases and purposes, not duplication.
ORM was renamed `PortalOrmRow`; 58 tests passed. Naming note resolved.

### DB-28 (MEDIUM) — `core/` shared kernel holds domain-shaped concerns and a core↔domain cycle

`core/profile.py` and the catalogue slot were wizard/setup concerns and carried a
core-to-domain/application cycle/type-erasure pattern. S65 renamed `profile.py` to
`setup_answers.py`; S66 renamed `profile_catalogue.py` to `wizard_catalogue.py`. The remaining lazy
`Any` accessors depend on a separate deadlines-cycle decision; do not call that sub-question closed.

### DB-29 (MEDIUM) — inbound adapter re-export shims violate the no-shim rule

PDF error shims and an unused identity shim violated the no-shim rule. Consumers were pointed at
canonical defining modules; dead shim was removed. Closed.

### DB-30 (LOW) — duplicate Spanish-decimal parser in inbound

The inbound parser and PDF parser shared parsing logic but differed in failure contract (raise
versus `None`). `justificante` now uses the canonical PDF parser while preserving its caller-level
error handling. Closed for the measured duplicate.

### DB-31 (MEDIUM) — outbound adapters pull application/private internals for runtime context

Adapters resolved active-bucket/profile context through application internals and one Sheets adapter
imported private `_registry_sha`. Public `registry_sha` was promoted; W10 moved active-bucket
resolution to public `core`, with consumers repointed. Sheets orchestration boundary and remaining
profile context were handled by their owning surfaces; do not conflate adapter→application legality
with private-import hygiene.

### DB-32 (HIGH) — persistence adapter runs a domain calculation in the write path

The adapter ran a domain valuation guard that production `InventoryService.movement_add` bypassed.
S57 moved the guard into the application service before save and removed the calculation from
storage. A service-level negative-stock test replaced the adapter-only test; 27 tests and typing
passed. Closed, including the real unguarded write path.

### DB-33 (MEDIUM) — `assets.py` hardcodes storage namespace literals instead of the registry constants

`assets.py` duplicated namespace literals instead of registry constants. The initial fix was blocked
by DB-44’s cross-test bucket state. After DB-44 isolation landed, S55 used central namespace
constants and verified 5/5. Closed.

### DB-34 (HIGH) — regulatory tax formulas implemented in CLI handlers

Tax formulas were moved from CLI handlers into `domain/modelos` with focused tests. Closed for the
audited formulas.

### DB-35 (HIGH) — statutory validation rules enforced only at the CLI boundary

Validation rules were found only in CLI entrypoints, leaving non-CLI callers without the statutory
guard. Retained as unresolved/high-priority boundary work; no closure recorded here.

### DB-36 (MEDIUM) — CLI handlers bypass the application layer to call domain directly

S82/S83 routed `_common.py` Modelo 100 aggregation through the existing application service and
removed a test’s private CLI import; 12 renta-ledger and 23 backend-boundary tests passed.
`usage_ratios` mutating verbs still needed application wrappers and were blocked on peer work.
Partial, not a blanket close.

### DB-37 (MEDIUM) — CLI enum-typing + private-import gaps

`--category` now uses `PortalCategory`; `StoredProfileDriftError` was exposed through the
application public surface. Focused checks passed. Closed.

### DB-38 (MEDIUM) — regulatory thresholds parked in `core/external_constants.py`

The CLI `_modelo` consumer now imports `M347_THRESHOLD_EUR` directly from its true home,
`core.external_constants`. The `row_models` re-export is intentional and tested, not a dead shim;
it is excluded from removal. DB-38 closed as partial-landed plus excluded residual; no further
action was recorded.

### DB-39 (MEDIUM) — `core/profile_catalogue.py` is a second core→application registration-slot coupling

The profile catalogue slot was the second disguised registration coupling. S66 moved it to
`core/wizard_catalogue.py`; import, tests, docs, and registry path strings were repointed. Closed
for the measured slot.

### DB-40 (LOW cluster) — borderline domain knowledge in `core/`

NIF/NIE/CIF checksum, domain-named `Settings` fields, and the shared `AggregationSourceKind` were
reviewed. No clear defect: checksum is pure and reused, settings follow existing convention, and the
enum prevents an upward dependency. Retain as ADR hygiene notes only.

### DB-41 (HIGH) — latent order-dependent circular import between `domain.invoices` and `domain.iva._invoice_classification`

An invoices-first import exposed an order-dependent cycle through `iva._invoice_classification`.
Importing `IvaRate` from the defining `_enums` leaf fixed that direction. S21 then moved the
classification consumers to the public `iva` surface; both `iva` and `invoices` imported cleanly
without a cycle, 332 focused tests passed, and `ty` was clean. The cycle and linked DB-11 export
asymmetry are closed by the latest recorded verification.

### DB-42 (MEDIUM) — the `.importlinter` layered-architecture gate was non-functional

Four confirmed stale ignore entries caused import-linter to abort before evaluating contracts. The
stale entries were removed and unmatched-ignore alerting set to `warn`; commit `4636bde35` restored
the gate. Closed for the gate-integrity defect.

### DB-43 (ungraded in source) — recurring complexity/tooling baseline

The audit recorded 582 high-complexity blocks as a tooling baseline for W08 recurring review, not as
582 defects. Use its owner and threshold context; do not treat the count as a one-time remediation
list.

### DB-44 (ungraded in source) — assets tests leaked bucket-scoped state

Tests reused default bucket ids, making secure-object/session state cross module boundaries. Each
assets scenario received a unique bucket id; the multi-module test set passed 5/5. This fixed the
flake and unblocked DB-33/S55.

## Execution chronology and durable Step references

- **2026-06-01:** Baseline and first 40 findings; six discovery agents covered 14 domain and nine
  application packages. RAG temporarily failed, so structural checks continued with deterministic
  `rg`. DB-41 emerged as a latent order-dependent cycle; DB-42 gate break, DB-43 complexity
  baseline, and DB-44 assets test isolation were added during execution.

- **2026-06-02:** Execution moved beyond audit-only under the recorded operator directive. S54 moved
  topics to core; S61/S62 relocated asset/inventory errors; S64 removed the domain-to-wizard pull
  after the registration bootstrap; S65/S66 moved setup modules; S68/S69 fixed DB-05; S70/S71
  retained different period-parser semantics; S82/S83 closed the measured DB-36 route. S63 remained
  last because it required an 89-file atomic rename, a naming decision, and a quiescent tree.

- **DB-20 / S89:** Full IVA-compensation move was scoped as a dedicated atomic pass, not a simple
  helper relocation; the domain package was later implemented and tested.

- **DB-44 → DB-33 / S55:** Unique test bucket ids fixed cross-test state first; then central asset
  namespace constants landed and passed 5/5.

- **2026-06-03, W11 / S104–S107:** Public secure-storage symbols were exported from `storage`;
  double-private envelope access was removed; 15 repositories were repointed. Seventy-one focused
  persistence/repository roundtrip tests and `ty` passed. Sanctioned fincas `_orm` imports remain a
  separate within-domain detail.

- **2026-06-03, W10 / S95–S103:** Active-bucket resolvers and `NoActiveProfileError` moved to public
  `core`; workflow copies/re-exports were removed and about 60 consumers repointed. Verification: no
  cycle, no new touched-symbol `ty` diagnostics, import-linter at prior status, 42
  core/workflow/registry plus 599 consumer tests passed. A later no-reexport cleanup found a missed
  relative importer and centralized 16 more private-core consumers; focused 397 + 110 + 43 tests
  passed.

- **2026-06-04 honesty review:** Full `src/aeat` was red: 193 failed, 13,625 passed, 5 skipped over
  36 minutes. Collect-only was clean over 13,817 tests; changed W10/W11 test files were absent from
  failures. Failures concentrated in untouched fincas, inbound declaration, and registry areas; a
  peer M200 TOML revision value caused a dominant `RegistryLoadError` (`2024-y-siguientes`, cited
  about 250 times). The campaign therefore claims focused W10/W11 evidence and no observed
  regression, not a green full suite. Follow-ups S108 (stale import-linter ignores) and S109 (CLI
  session flake) remained tracked.

## Remaining queue and authority boundaries

R1/DB-01 is complete through the operator-confirmed D7/S63 rename to `domain/contribuyente`. The family-facts and inventory-error conclusions were narrowed; do not assume the canonical home is `renta`.

R2/DB-03 is complete. R3’s per-concept sweep and R4’s application-package sweep produced the ledger;
later additions DB-41–44 are retained above. DB-16–19 required an architectural ruling: D4 ratified
public top-level storage imports and accepted runtime generic-base/value imports as managed debt;
W10/W11 carried the actionable surfaces.

Other remaining or partial items: DB-06 parser semantics, DB-22 verification-policy placement,
DB-25 registry vocabulary, DB-35 non-CLI statutory validation, DB-36 usage-ratio application
wrappers, and the core/deadlines cycle behind DB-28’s lazy accessors. Historical plan completion
means the recorded steps were reconciled; it does not erase these explicit decision/debt boundaries.

## Original recommendation ledger: R1–R20

- R1 / DB-01: complete through the operator-confirmed D7/S63 rename to `domain/contribuyente`.

- R2 / DB-03: complete. R3: broad per-concept sweep produced the later DB entries. R4: application
  sweep complete.

- R5 / DB-16/18/19: D4 ratified the public storage boundary; W10/W11 own the measured follow-up
  surfaces.

- R6 / DB-07/18: topics moved to core; residual runtime edges are not broadened without the boundary
  ruling.

- R7 / DB-17: complete through S64 registration bootstrap.

- R8: complete for the named remaining domain and application packages; DB-20–25 recorded.

- R9 / DB-20: domain IVA-compensation home created and moved; source/legal-corpus interpretation
  remains a separate concern.

- R10 / DB-21: public registry surface adopted by the measured importers.

- R11 / DB-26: measured DTO pairs reconciled; wire payload boundaries retained.

- R12 / DB-28: S65/S66 module renames landed; lazy accessor typing remains gated on the
  core/deadlines cycle.

- R13 / DB-32, R14 / DB-29: valuation moved to service; shims removed.

- R15 / DB-31: active-bucket authority moved to core and private registry digest promoted; preserve
  any remaining context-injection choices.

- R16 / DB-33/30: namespace constants and parser convergence landed after DB-44 isolation.

- R17 / DB-34/35: formulas moved; statutory M184/M347 non-CLI validation remains open.

- R18 / DB-36: aggregation route landed; usage-ratio mutating wrappers remain partial.

- R19 / DB-38: closed partial-landed plus excluded residual; no further action recorded.

- R20 / DB-37: enum typing and public error import landed.

All six layers were examined on at least one axis: domain, application, inbound/outbound/persistence
adapters, core, CLI, plus cross-cutting edge and duplicate-type scans. Broad coverage is not “done”:
re-sweep after remediations, finish the explicitly open findings, and keep roundtrip/structural
evidence with each closure.
## Codification

No new rule was proposed. The substitutability pre-filter and RAG-cluster-then-`rg` verification
discipline were already codified in `aeat-swarm-audit-cadence`; architecture boundaries already
prohibit shims and require relocation atomicity.


