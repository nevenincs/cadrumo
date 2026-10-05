# Registry reporting, cross-filing relations, and coverage checks

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-133` · **Topic:** [Tax calculation domain](../topics/tax-calculation-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 16 registry-domain modules, 4,874 physical lines, 207,531 bytes, and 44,558 measured `o200k_base` proxy tokens. All eight bounded pages were read; no application code or tests were run and no source was changed. It spans read-only registry reporting, cross-filing relations, reference and coverage checks, remote-operation policy, tax catalogues, and inheritance declarations.

## Registry discovery and filing relationships

The query layer turns a validated authority into typed reports for model listings, revision descriptions, casilla lists/details, bindings, formula dependencies, source-kind inventory, and support matrices. It has an eager diagnostic facade over `ValidatedRegistryAuthority` and a point-loaded facade over a generation-pinned operation. Both support unscoped period lookup and filing-year-scoped resolution; unscoped calls reject `as_of`, while scoped calls feed canonical revision/snapshot selection. Bulk revision walks are explicitly diagnostic, while ordinary reports select only the needed revision through the pinned directory. Reports carry regulatory references, typed provider details and formula dependency IDs, not taxpayer filing values. Legacy query facade (`src/cadrumo/domain/calculations/registry/queries.py`) Pinned query facade (`src/cadrumo/domain/calculations/registry/queries.py`) Typed report contracts (`src/cadrumo/domain/calculations/registry/query_reports.py`)

The IVA rate-box partition module detects the paired total/rate-box structure from selector axes and casilla exports rather than hard-coded model IDs. A formed partition requires one rate-blind total binding, rate-specific siblings, a non-exported total casilla and at least one exported rate box. It compares the total with the sum of rate boxes and reports strictly positive gaps, which commonly represent unrecorded rates. Excess box totals are deliberately a separate condition. Groups without a formed partition remain visible through the shortfall/residue diagnostic; the module warns that using only formed partitions for an export gate would omit the most severe missing-blind-binding case. Partition derivation (`src/cadrumo/domain/calculations/registry/rate_box_partition.py`) Coverage arithmetic (`src/cadrumo/domain/calculations/registry/rate_box_partition.py`)

Relation-prefill bindings declare one upstream modelo, one source casilla, a dependency role, and a closed temporal selector. The resolver groups equivalent source requirements by model/year/period/casilla/role/treatment/fold operation, then uses the shared observation fold to require exactly one filing observation per source period and a present casilla value. Only `copy` and `sum` fold matched filings; missing, extra, or ambiguous inputs fail rather than becoming zero. A separate external-output resolver applies the same active binding IDs and op shape. Relation provider (`src/cadrumo/domain/calculations/registry/relation_prefill_bindings.py`) Requirement construction (`src/cadrumo/domain/calculations/registry/relations.py`) Observation-backed resolution (`src/cadrumo/domain/calculations/registry/relations.py`)

## Authority, scope and data projections

The snapshot reference checker indexes canonical IDs once and accumulates dangling-reference failures across the revision graph. It checks casillas only by canonical ID, verifies formula/binding/export/extraction/dependency references, requires a bound casilla to have a binding, validates legal references are actually legal-authority tier, and prevents provenance-only corpus sources from serving as export-layout authority. Text-typed PDF extraction targets must use the named-label strategy. Snapshot integrity gate (`src/cadrumo/domain/calculations/registry/reference_checks.py`) Reference accumulator (`src/cadrumo/domain/calculations/registry/reference_checker.py`) Specialized reference checks (`src/cadrumo/domain/calculations/registry/reference_sections.py`)

The record-design coverage module derives the within-modelo calculation closure from formula targets and references, verification operands, binding endpoints and same-modelo source casillas, while excluding foreign modelo casillas. Its module docstring describes additional design-coverage inventory work, but the assigned module exports only the closure helper; any full design parser/report is outside this chunk and should be located in synthesis. Calculation closure (`src/cadrumo/domain/calculations/registry/record_design_coverage.py`)

Several dated policy readers expose bounded typed projections. Refund eligibility verifies final periods and matching filing cadence. Renta residency and EU/EEA membership resolve from separate governed facts; country membership requires unique two-letter codes. Rental-reduction tiers carry legal references and parameter IDs. Renta expense territorial declarations are selected at the profile year's end and reject duplicate mapping keys. These modules expose published authority semantics but do not establish that the authority payload remains legally current. Refund-period policy (`src/cadrumo/domain/calculations/registry/refund_eligibility.py`) Residency catalogue (`src/cadrumo/domain/calculations/registry/renta_codes_catalogue.py`) Rental-reduction tiers (`src/cadrumo/domain/calculations/registry/rental_reduction.py`) Expense territorial policy (`src/cadrumo/domain/calculations/registry/renta_expense_policy.py`)

Restated-family declarations make full replacement of an inherited family explicit instead of inferring it from omissions. They are closed to families the loader does not inherit and refuse the casilla family until the casilla merge pass can honor a restatement. Restatement declaration (`src/cadrumo/domain/calculations/registry/restated_families.py`)

## Remote-state security

`RemoteStateGuardPolicy` separates open simulators, integration-test services, public reads, authenticated reads, static-only sources and forbidden stateful surfaces. Host entries are restricted to AEAT or explicitly sanctioned government identity-provider hosts; identity-provider use requires an authenticated-read opt-in. Synthetic data is blocked for public/authenticated/static/forbidden classifications and on AEAT-hosted surfaces. The generated policy does not widen every host to sibling subdomains. Policy validation (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`) Policy construction (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`)

At operation time the guard blocks static-only and forbidden surfaces; HTTP reads require an allowed method, a canonical bare HTTPS authority, an admitted host and, when configured, an exact read path. POST is admitted only for authenticated-read policies on explicitly declared read-POST paths. URL user-info and nondefault ports are refused after URL normalization. Browser actions are checked against forbidden action tokens and an explicit pattern allowlist; an empty allowlist refuses every action. The universal write-token scan remains active even when policy-specific forbidden actions are absent. The guard only evaluates or preflights operation descriptions; it does not itself execute requests. Operation evaluation (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`) HTTP checks (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`) Browser checks (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`)

## Quality and limits

The strongest controls are explicit, fail-closed boundaries: typed reports, canonical ID-only references, exact fold cardinality, separate authority grades, and a network policy that limits host, method, path, and action. The remote guard does not carry an HTTP body or actual credential state, so its authenticated/read-POST guarantee depends on caller integration and catalog declarations; callers must run the guard before any side effect. Also, an empty `allowed_read_paths` tuple disables path filtering, so each policy's intended host-wide read scope should be reviewed. This is conditional policy breadth, not proof that an unsafe operation is reachable. Period-offset parsing also treats any two-character `str.isdigit()` token as a month before calling `int`; explicit ASCII validation would make the canonical `01`–`12` contract clearer and avoid inconsistent errors for some Unicode numeral inputs. Read-path and method decisions (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`) Monthly offset parsing (`src/cadrumo/domain/calculations/registry/period_offset_math.py`)

The frozen report DTOs and bounded authority APIs support stable diagnostics, but this chunk does not show CLI rendering, application adapters, external identity proof, operation execution, full record-design extraction, or legal-content verification. No tests were run; inline test references and policy comments are not execution evidence.

## Coverage appendix

All 25 assigned files were read fully across eight bounded pages; no unread ranges remain.

- registry/queries.py (`src/cadrumo/domain/calculations/registry/queries.py`) — 1–1479
- registry/query_reports.py (`src/cadrumo/domain/calculations/registry/query_reports.py`) — 1–328
- registry/rate_box_partition.py (`src/cadrumo/domain/calculations/registry/rate_box_partition.py`) — 1–356
- registry/record_design_coverage.py (`src/cadrumo/domain/calculations/registry/record_design_coverage.py`) — 1–199
- registry/reference_checker.py (`src/cadrumo/domain/calculations/registry/reference_checker.py`) — 1–155
- registry/reference_checks.py (`src/cadrumo/domain/calculations/registry/reference_checks.py`) — 1–271
- registry/reference_sections.py (`src/cadrumo/domain/calculations/registry/reference_sections.py`) — 1–124
- registry/refund_eligibility.py (`src/cadrumo/domain/calculations/registry/refund_eligibility.py`) — 1–135
- registry/relation_dependency.py (`src/cadrumo/domain/calculations/registry/relation_dependency.py`) — 1–87
- registry/relation_prefill_bindings.py (`src/cadrumo/domain/calculations/registry/relation_prefill_bindings.py`) — 1–129
- registry/relations.py (`src/cadrumo/domain/calculations/registry/relations.py`) — 1–493
- registry/remote_state_guard.py (`src/cadrumo/domain/calculations/registry/remote_state_guard.py`) — 1–582
- registry/renta_codes_catalogue.py (`src/cadrumo/domain/calculations/registry/renta_codes_catalogue.py`) — 1–257
- registry/renta_expense_policy.py (`src/cadrumo/domain/calculations/registry/renta_expense_policy.py`) — 1–37
- registry/rental_reduction.py (`src/cadrumo/domain/calculations/registry/rental_reduction.py`) — 1–118
- registry/restated_families.py (`src/cadrumo/domain/calculations/registry/restated_families.py`) — 1–124
<!-- /preserved:article -->
