# Profile-scoped IVA prorrata register operations

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-095` · **Topic:** [Ledger, invoices, evidence, and registers](../topics/ledger-invoices-and-registers.md)

<!-- preserved:article -->
**Scope:** 13 files under `src/cadrumo/application/prorrata_register`, totaling 3,438 lines, 132,465 bytes, and 28,407 measured `o200k_base` proxy tokens. All six bounded-reader pages and assigned ranges were read. Static inspection only; no application execution or tests were run. References to LIVA rules below describe the implementation’s declared workflow and are not independent legal validation.

## Capabilities and mechanisms

This package registers an exact-profile read and mutation surface for the cross-period IVA prorrata register. Operations list the complete register, declare differentiated sectors, elect general or especial provisional percentages, revoke especial status, seed a whole-entity or per-sector provisional percentage, and settle a sector’s definitive percentage. The register is profile-scoped persisted state; calculations and precedence resolution remain delegated to the domain. Registered request vocabulary (`src/cadrumo/application/prorrata_register/operation_requests.py`), register service boundary (`src/cadrumo/application/prorrata_register/service.py`), operation definitions and access (`src/cadrumo/application/prorrata_register/registered_operations.py`)

Election inputs must use an electable provenance. Document-backed provenance requires a nonblank reference, while provenance with no supporting document rejects a supplied reference; the computed “carried prior definitive” provenance cannot be manually elected. Special-option and revocation requests also carry transition evidence. Amounts cross the operation boundary as public decimal strings and are validated into canonical domain entries before any write. Election rules (`src/cadrumo/application/prorrata_register/election.py`), mutation preflight and entry construction (`src/cadrumo/application/prorrata_register/mutation_steps.py`)

Whole-entity seeding reads the prior year’s unmembered Modelo 303 settlement candidates, requires the prorrata casilla, orders terminal periods through the pinned authority, and chooses the latest candidate. The stamped revision is re-confirmed against the law-selected revision before it can seed; divergence yields a blocking finding and no seed. The commit then reloads the source snapshot and current register revision, checks any existing target entry, and attempts an atomic source-plus-register compare-and-swap up to four times. It refuses when the source is absent or blocked, a current carried entry contradicts the source, or a regulated override still stands. Seed candidate and revision gate (`src/cadrumo/application/prorrata_register/seed.py`), observation selection and source checks (`src/cadrumo/application/prorrata_register/seed.py`), cross-checks (`src/cadrumo/application/prorrata_register/seed.py`), source-fenced register commit (`src/cadrumo/application/prorrata_register/service.py`), CAS retry and refusal cases (`src/cadrumo/application/prorrata_register/service.py`)

Sector lifecycle uses the prior year’s definitive entry for the same sector rather than a single whole-entity 303 percentage. If there is no settled prior sector entry, it returns no seed so the caller can report the gap instead of silently inventing a provisional percentage. Year-end sector settlement computes the definitive percentage from that sector’s own con-derecho and sin-derecho volumes and adds the producing registry snapshot reference. Per-sector carry (`src/cadrumo/application/prorrata_register/sector_lifecycle.py`), sector settlement (`src/cadrumo/application/prorrata_register/sector_lifecycle.py`)

For calculation consumers, the service resolves provisional candidates through the domain precedence ladder, filtering both persisted and transient candidates to the exact year/sector address. This allows an uncommitted seed or override to be evaluated with the same authority order as a persisted entry instead of duplicating priority rules in application code. Provisional resolution (`src/cadrumo/application/prorrata_register/service.py`)

Registered execution validates the request class, operation ID, subject reference, current profile bucket, and worker identity. Reads load under a thread and finish cancellation cleanup before returning. Mutations preflight before the irreversible section, mark the effect unknown before the write begins, then perform the repository mutation and persist either a successful snapshot or a typed refusal. Successful updates report `UPDATED`; list and refusals report `NONE`. Exact-profile executor (`src/cadrumo/application/prorrata_register/executor.py`), preflight and mutation separation (`src/cadrumo/application/prorrata_register/executor.py`), irreversible commit section (`src/cadrumo/application/prorrata_register/executor.py`)

Private results retain the full canonical register; public projections are closed, strict snapshots with canonical decimal strings and finite refusal codes. Projectors revalidate result shape, bind definition and profile identity to the terminal receipt, require a successful update receipt for mutation success and a no-effect refusal receipt for refusal, and check the returned entry or sector is actually present in the committed register. Seed projections preserve source revision, year, period, and casilla identity; seed findings preserve stamped and selected revisions. Projection contracts (`src/cadrumo/application/prorrata_register/projection_contracts.py`), private result shape (`src/cadrumo/application/prorrata_register/result_contracts.py`), receipt-bound mutation projection (`src/cadrumo/application/prorrata_register/result_projections.py`)

## Knowledge, security, and implementation assessment

Knowledge comes from the pinned calculation registry, persisted prorrata register, and prior-year observation snapshot. Whole-entity carry reads the register’s scoped source-snapshot capability and compares source row revisions with the register revision during commit. Sector carry instead uses the register’s own prior-year definitive. The operation ports keep the register repository and observation snapshot source behind application-owned protocols; the production secure-object adapter is outside this chunk. Source snapshot protocol (`src/cadrumo/application/prorrata_register/ports.py`), revision-checked coordinate validation (`src/cadrumo/application/prorrata_register/service.py`)

Concrete safeguards include whole-profile access with commit permission only on mutations, exact active-profile/bucket binding, pinned-fact validation, revision-carry checks on register source coordinates, finite typed refusals, strict result-arm validators, terminal-receipt matching, cancellation completion around worker-thread work, and a source-fenced CAS for whole-entity seed. No operation here submits anything to AEAT; state changes affect the local profile register. The authorisation/proposal reference is stored as user-provided evidence metadata, so its access, redaction, and audit policy should be traced in the persistence adapter and output frontend.

One conditional provenance boundary needs cross-layer confirmation. The seed projector itself filters prior year, whole-entity rows, terminal settlement coordinates, required casilla, and revision stamp, but does not visibly test an official-AEAT observation source-kind predicate or taxpayer identity. The separate `load_prior_m303_settlement_snapshot` repository capability may already enforce that finite scope; verify its adapter before relying on it as the sole source gate. Local source filter (`src/cadrumo/application/prorrata_register/seed.py`), repository snapshot contract (`src/cadrumo/application/prorrata_register/ports.py`)

The strongest quality feature is the coordination of source and target revisions for whole-entity carry; the mutation path also distinguishes refusals known before write from outcomes requiring an effect witness. Sector settlement is passed a registry snapshot coordinate, and later reads re-confirm all coordinates in the register. Remaining verification should focus on adapter-side snapshot filtering and CAS behavior under concurrent writes. No assigned tests were run, so runtime refusal/effect accounting and races remain unverified here.

## Dependencies and follow-up

Synthesis should trace these application protocols into the encrypted profile register repository and prior-303 observation snapshot adapter, then follow provisional precedence and calculation consumption in `domain.prorrata_register` and `domain.iva`. Confirm that the source snapshot cannot include local or wrong-taxpayer observations, inspect revision guards and CAS retry behavior in the adapter, and locate tests for election provenance, special transitions, source divergence, sector gaps, and receipt/effect matching.

## Complete assigned-file coverage

All 13 assigned files were read fully across pages 1–6; no portions remain unread.

- prorrata_register/__init__.py (`src/cadrumo/application/prorrata_register/__init__.py`)
- prorrata_register/election.py (`src/cadrumo/application/prorrata_register/election.py`)
- prorrata_register/executor.py (`src/cadrumo/application/prorrata_register/executor.py`)
- prorrata_register/mutation_steps.py (`src/cadrumo/application/prorrata_register/mutation_steps.py`)
- prorrata_register/operation_requests.py (`src/cadrumo/application/prorrata_register/operation_requests.py`)
- prorrata_register/ports.py (`src/cadrumo/application/prorrata_register/ports.py`)
- prorrata_register/projection_contracts.py (`src/cadrumo/application/prorrata_register/projection_contracts.py`)
- prorrata_register/registered_operations.py (`src/cadrumo/application/prorrata_register/registered_operations.py`)
- prorrata_register/result_contracts.py (`src/cadrumo/application/prorrata_register/result_contracts.py`)
- prorrata_register/result_projections.py (`src/cadrumo/application/prorrata_register/result_projections.py`)
- prorrata_register/sector_lifecycle.py (`src/cadrumo/application/prorrata_register/sector_lifecycle.py`)
- prorrata_register/seed.py (`src/cadrumo/application/prorrata_register/seed.py`)
- prorrata_register/service.py (`src/cadrumo/application/prorrata_register/service.py`)
<!-- /preserved:article -->
