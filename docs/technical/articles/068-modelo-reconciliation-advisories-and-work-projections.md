# Modelo reconciliation, advisories, and work projections

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-068` · **Topic:** [Modelo work and revision lifecycle, part 1](../topics/modelo-work-and-revision-lifecycle-part-1.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 19 modules, 4,869 physical lines, 208,666 bytes, and 43,815 measured `o200k_base` proxy tokens across eight bounded pages. It includes Modelo 210 rate resolution, model reconciliation and registry guards, descendant/guardería advisories, calculation diagnostics, and the work-review/workspace projections. The source was inspected statically; no application code or tests were run and no source was changed. The token count is a measured proxy, not a claim about model context limits.

## Product capabilities

Modelo 210 rate selection reads the baseline and tariff parameter identities from the selected revision's declared rate formula, then resolves a typed income kind and date-specific treaty override. It can return a domestic baseline, an exemption, a treaty flat rate, the lower of a baseline and treaty ceiling, or defer a domestic-tariff branch to the registry formula engine. Missing required rates create blocking, provenance-bearing findings rather than silently supplying a default. Rate resolution (`src/cadrumo/application/modelo/_m210_rate.py`)

The cross-model M303/M349 reconciliation is discovered from reciprocal verification expectations in the pinned registry instead of hardcoding the model pair, operand casillas, tolerance, or references. It selects an active same-period sibling through the work selector, chooses the strongest current revision, and emits a warning only when declared totals differ beyond the selected tolerance. Absent or ambiguous authority/work state is a closed no-op. The M349 ledger guard separately refuses calculation when current intra-community ledger rows lack the counterparty-bearing operator rows a declaration needs. Registry-discovered reconciliation (`src/cadrumo/application/modelo/_m303_m349_reconcile.py`) M349 raw-ledger guard (`src/cadrumo/application/modelo/_m349_ledger_guard.py`)

The descendant advisory module exposes a broad diagnostic surface for M100 minimum and nursery deductions. It flags an undeclared descendant set where the minimum resolved to zero, inferred prorrata when a second entitled filer is indicated, missing descendant income figures where a minimum is claimed, missing adoption/foster entry dates, nursery spend recorded only as annual totals when month-level detail is required, undeclared second-cycle start month or mother's qualifying months, an unbounded cotizaciones ceiling, declared dependency assumptions, and a stored child count that diverges from the descendant rows. It uses the same family-fact reconstruction and date-bound authority as calculation, and gives targeted remedies rather than changing a filing value itself. Initial minimum and prorrata diagnostics (`src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`) Nursery shape checks (`src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`) Dependency and row-count checks (`src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`)

Other calculate- or verify-time diagnostics compare independent signals: Modelo 720 compares prior-year declaration, current per-asset evidence, and current declared casillas; objective-estimation advisories compare profile volumes with dated registry thresholds; official-box predicates disclose positive computed totals whose numbered boxes remain zero; and operator-override advisories show both a supplied value and the different source-computed value. Rate-box diagnostics explain shortfalls before a matching export refusal, and settlement diagnostics call out revisions where terminal settlement casillas remain manual rather than computed. Modelo 720 redeclaration comparison (`src/cadrumo/application/modelo/_m720_redeclaration_gate.py`) Objective-estimation thresholds (`src/cadrumo/application/modelo/_objective_estimation_advisory.py`) Override and rate-box diagnostics (`src/cadrumo/application/modelo/_operator_override_advisory.py`) Settlement structural check (`src/cadrumo/application/modelo/_settlement_grade_advisory.py`)

The casilla-population resolver scopes reconciliation to figures supported by independent local evidence. It walks formula input closures and excludes carry/relation sources that are backed by the very filed-observation store being compared. It deliberately cannot detect a nonzero real-world figure when the local bucket supplied nothing; invoice-only evidence without consumed ledger transactions can also appear empty. Population scope and documented false negatives (`src/cadrumo/application/modelo/_reconcile_population.py`)

Registry helpers validate canonical casilla IDs against the selected revision, enforce numeric versus boolean channel rules, refuse row-template values on scalar override/import paths, and rehash persisted calculation revisions while checking observation/value consistency. Work-unit creation guards validate revision and filing-period declarations. M202 alone has a hard gate requiring every declared binding to resolve; it is intentionally stricter than the generic, nonblocking missing-source diagnostics elsewhere. Input validation (`src/cadrumo/application/modelo/_registry_helpers.py`) Stored revision integrity (`src/cadrumo/application/modelo/_registry_helpers.py`) M202 required-binding gate (`src/cadrumo/application/modelo/_required_binding_gate.py`)

The review assembler projects every selected-revision casilla into a structured work-review row with official references, declared and realized value kind, concrete formulas and bindings, relation consumption, provenance, blocker facts, and origin anomalies. It derives progress only against the revision's completeness manifest and attaches safe row-source fingerprints. The paired workspace validators pin baselines, selected revisions, schema identities, contributor epochs, facet names/page cursors, and static-versus-materialized output constraints. Review rows (`src/cadrumo/application/modelo/_work_review_assembly.py`) Whole work review assembly (`src/cadrumo/application/modelo/_work_review_assembly.py`) Workspace consistency guards (`src/cadrumo/application/modelo/_workspace_model_validation.py`)

## Mechanisms and trust boundaries

The per-calculation transaction cache memoizes full catalogues, date windows, ID subsets, and date partitions while delegating writes and invalidating its caches after save. The renderer port defines the application-facing contract for one registry-declared fixed-width record without moving AEAT byte layout into this layer. Row-source identity replay checks that the emitted draft includes persisted row coordinates and matching values before attaching encrypted identities and rebuilding the draft ID. Transaction read-through cache (`src/cadrumo/application/modelo/_transaction_catalogue_cache.py`) Fichero renderer port (`src/cadrumo/application/modelo/_ports.py`) Row identity replay (`src/cadrumo/application/modelo/_row_source_identity_replay.py`)

## Quality, security, and unresolved questions

The strongest patterns are revision-scoped metadata, typed source and legal provenance, explicit blocking versus advisory outcomes, and visible disclosure of both known false-negative limits and incomplete legal facts. Review assembly reads persisted calculation overrides rather than substituting current profile state, and integrity guards make stored payload drift a refusal. These are static design findings, not evidence that user-facing wiring, translations, or lifecycle gates behave correctly at runtime.

Some diagnostics intentionally stop short of completeness: an unpopulated casilla is omitted from reconciliation rather than treated as a zero mismatch, and several descendant or treaty facts need human confirmation. This reduces false alarms but means users still need other controls for absent data. The M720 collector also returns no finding when the selected snapshot, prior baseline, or asset-row evidence is unavailable; that avoids fabricating a first-year zero baseline but leaves those states outside this advisory's coverage.

The row-source replay checks that every stored revision coordinate has a matching draft row and value, then attaches each persisted identity; downstream draft/export consumers remain responsible for displaying or acting on those safe fingerprints. The work-review projection can include taxpayer amounts and blocker details; row-source identities are reduced to opaque fingerprints. The chunk defines data-shape and integrity constraints but not an authorization, redaction, or encryption policy for review output. The cache assumes repositories provide immutable catalogue values during one calculation; cross-call freshness and concurrent writes belong to repository/transaction behavior not established here. No tests were executed, so the comments' reported failure reproductions and recovery guarantees are not independently verified in this pass.

Follow-up synthesis should connect these collectors to the actual calculate, verify, reconcile, export, and workspace request surfaces; confirm how a missing-evidence no-op is shown to operators; verify row fingerprints are safe at every API boundary; and check whether the work-unit operation pins the same authority generation for treaty rate/advisory reads. Bundled registry facts and legal references are product knowledge, not an external confirmation of current law.

## Coverage appendix

All 19 assigned files were read fully across eight bounded pages; no unread ranges remain.

- modelo/_m210_rate.py (`src/cadrumo/application/modelo/_m210_rate.py`) — 1–208
- modelo/_m303_m349_reconcile.py (`src/cadrumo/application/modelo/_m303_m349_reconcile.py`) — 1–321
- modelo/_m349_ledger_guard.py (`src/cadrumo/application/modelo/_m349_ledger_guard.py`) — 1–104
- modelo/_m720_redeclaration_gate.py (`src/cadrumo/application/modelo/_m720_redeclaration_gate.py`) — 1–112
- modelo/_minimo_descendientes_advisory.py (`src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`) — 1–971
- modelo/_objective_estimation_advisory.py (`src/cadrumo/application/modelo/_objective_estimation_advisory.py`) — 1–377
- modelo/_official_box_advisory.py (`src/cadrumo/application/modelo/_official_box_advisory.py`) — 1–111
- modelo/_operator_override_advisory.py (`src/cadrumo/application/modelo/_operator_override_advisory.py`) — 1–96
- modelo/_ports.py (`src/cadrumo/application/modelo/_ports.py`) — 1–75
- modelo/_rate_box_advisory.py (`src/cadrumo/application/modelo/_rate_box_advisory.py`) — 1–87
- modelo/_reconcile_population.py (`src/cadrumo/application/modelo/_reconcile_population.py`) — 1–274
- modelo/_registry_helpers.py (`src/cadrumo/application/modelo/_registry_helpers.py`) — 1–663
- modelo/_registry_resources.py (`src/cadrumo/application/modelo/_registry_resources.py`) — 1–89
- modelo/_required_binding_gate.py (`src/cadrumo/application/modelo/_required_binding_gate.py`) — 1–238
- modelo/_row_source_identity_replay.py (`src/cadrumo/application/modelo/_row_source_identity_replay.py`) — 1–145
- modelo/_settlement_grade_advisory.py (`src/cadrumo/application/modelo/_settlement_grade_advisory.py`) — 1–105
- modelo/_transaction_catalogue_cache.py (`src/cadrumo/application/modelo/_transaction_catalogue_cache.py`) — 1–104
- modelo/_work_review_assembly.py (`src/cadrumo/application/modelo/_work_review_assembly.py`) — 1–589
- modelo/_workspace_model_validation.py (`src/cadrumo/application/modelo/_workspace_model_validation.py`) — 1–200
<!-- /preserved:article -->
