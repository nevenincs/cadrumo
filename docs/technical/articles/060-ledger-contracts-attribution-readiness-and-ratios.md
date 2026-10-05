# Ledger contracts, attribution, readiness, and ratios

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-060` · **Topic:** [Ledger, invoices, evidence, and registers](../topics/ledger-invoices-and-registers.md)

<!-- preserved:article -->
## Scope

This chunk covers 16 ledger application modules, 4,651 lines and 43,102 measured proxy tokens. All eight bounded pages were read. It contains shared transaction and import/export contracts, party-address attribution and postal-code checks, ledger tax-readiness preflight, usage-ratio commands and derived business-share decisions, plus finalized-participation reads and rebuilds. Static only: no filing, invoice corpus, persistence adapter, frontend, or test was executed.

## Transaction contracts and operator outputs

The shared create and patch models normalize country/currency text and accept registry-controlled values only through the corresponding authority validators. Manual creation requires a nonzero nonnegative amount magnitude, with flow represented by direction; internal transfers reject tax classifications, invoice evidence, attachments and related tax facts. Patches must contain at least one field and share the canonical validators. Read projections carry decision provenance, FX facts and lifecycle timestamps; status totals separately count unconverted foreign-currency rows so the euro roll-up is visibly partial. Manual create and transfer policy (`src/cadrumo/application/ledger/models.py`) Patch constraints (`src/cadrumo/application/ledger/models.py`) Transaction read projection (`src/cadrumo/application/ledger/models.py`) Status report (`src/cadrumo/application/ledger/models.py`)

The same contract module defines typed source-import diagnostics, partial-success bulk-classification outcomes, lifecycle/removal reports, and export rows. Export metadata is recomputed against the payload through the shared tabular verifier, while date and nonnegative-decimal fields are validated on the row that both CSV and snapshot writers consume. This helps prevent an internally contradictory event/result from claiming different bytes or row counts than the exported payload. Import result and diagnostics (`src/cadrumo/application/ledger/models.py`) Bulk classification row (`src/cadrumo/application/ledger/models.py`) Export metadata validation (`src/cadrumo/application/ledger/models.py`)

## Party attribution and postal findings

The party-attribution code distinguishes whether a value was copied correctly from whether it belongs to the supplier or customer. It stamps postal/country address fields as unverified unless the field origin itself answers attribution or the document layout places it inside a region anchored by role-evidenced party identity. Identity attribution remains on a separate checked path. The stamp is recomputed both ways, so an established origin or newly resolved region clears stale warnings instead of leaving a latched flag. Address field policy (`src/cadrumo/application/ledger/party_attribution.py`) Idempotent attribution stamp (`src/cadrumo/application/ledger/party_attribution.py`)

The co-location resolver recognizes vertical blocks bounded by printed party headings and same-line columns separated by a preserved multi-space gutter. It requires both party anchors and rejects ambiguous layouts: columns with the wrong count, missing headings, merged content, repeated values across both blocks, or values appearing nowhere remain unresolved. A value found only in the other party’s region produces a contradicted outcome and a blocking discrepancy finding; the function reports the mismatch rather than swapping the fields on the basis of one reading. Unresolved values keep their stamp and operator advisory. Vertical regions (`src/cadrumo/application/ledger/party_colocation.py`) Horizontal regions (`src/cadrumo/application/ledger/party_colocation.py`) Outcome resolution (`src/cadrumo/application/ledger/party_colocation.py`) Contradiction findings (`src/cadrumo/application/ledger/party_colocation.py`) Partition selection (`src/cadrumo/application/ledger/party_colocation.py`)

Postal-shape findings ask the authoritative Spanish postal resolver whether a populated value is readable, and fire only when the country has not already settled the party’s territory. That avoids warning on legitimate non-Spanish postal formats and does not invent a default territory when the code is unreadable. Postal-shape gate (`src/cadrumo/application/ledger/postal_shape_finding.py`)

## Readiness preflight and ratios

Preflight is a read-only, period-scoped readiness analysis over active rows using value date or booked date. It checks missing business classification, expense category, MIXED ratio reference, IVA substrate, EUR tax substrate for converted foreign rows, counterparty identity/establishment, deduction admissibility, home-office censo mismatch or absent afectación, and non-declarable IVA categories. It screens income-only rows differently from deductible expenses, exempts recognized employment income from IVA-field checks, and checks the transaction category—not just an optional ratio ID—for home-office usage. This is important because the aggregation applies ratios by category. Bucket-bound preflight (`src/cadrumo/application/ledger/preflight.py`) Period filter and report (`src/cadrumo/application/ledger/preflight.py`) Home-office detection and expense-direction policy (`src/cadrumo/application/ledger/preflight.py`) IVA and deduction checks (`src/cadrumo/application/ledger/preflight.py`)

The reason mapping explicitly partitions every IVA aggregation issue into one that preflight can emit or one that cannot reach its screens; import-time guards fail if a new reason is unclassified, appears on both sides, or is missing from a reachable screen. A separate total map assigns operator action axes for every IVA issue. The registered preflight operation binds the canonical requested period and exact profile, returns a closed projection, and has read-only capabilities. Reason coverage guards (`src/cadrumo/application/ledger/preflight.py`) Preflight executor (`src/cadrumo/application/ledger/preflight_operation.py`)

Ratio projections are year-sensitive: eligible categories show their registry proportionality kind, statutory default and whether an override exists. Validation can identify missing required overrides, overrides on ineligible categories and out-of-range persisted values. Business-share resolution gives an explicit operator value precedence, then distinguishes no category, no applied censo, a non-home-office category, and a censo-derived statutory share. Eligibility and validation (`src/cadrumo/application/ledger/ratios.py`) Business-share precedence (`src/cadrumo/application/ledger/ratios.py`)

Set and unset use a per-bucket lock around load/modify/save. The higher-level set command also records before/after audit data and, when profile/censo inputs are present, a deviation warning. The source plainly documents that profile persistence and event history are separate writes: an event failure after save can leave a changed override without its audit event. That is an acknowledged consistency limitation whose durable repair would require a co-commit path; callers should not treat the pair as atomic. Locked ratio update (`src/cadrumo/application/ledger/ratios.py`) Business-share decision result (`src/cadrumo/application/ledger/ratios.py`) Set/event ordering and non-atomicity (`src/cadrumo/application/ledger/ratios.py`)

## Participation and persistence boundaries

The participation read resolves current or superseded transaction lineage within the requested profile and returns the persisted inverse index of finalized Modelo revisions, including an empty answer when there are no finalized declarations. Its registered operation is a read with no COMMIT capability. Rebuild recomputes the derived index from profile-bound calculation/work/filing/index repositories, reports transaction, participation, revision and stale-removal counts, and requires COMMIT under an irreversible, cancellation-complete section. Participation lookup (`src/cadrumo/application/ledger/participation_read.py`) Exact-profile read operation (`src/cadrumo/application/ledger/participation_operation.py`) Guarded rebuild (`src/cadrumo/application/ledger/participation_rebuild_operation.py`)

The shared pinned transaction repository prevents code that resolved against one catalogue snapshot from saving through a fresh unguarded path: unrevisioned writes fail, and compare-and-swap must match the captured revision. Pinned snapshot writer (`src/cadrumo/application/ledger/pinned_transaction_repository.py`) Import uses structural provider and co-commit protocols instead of naming storage adapters. The typed stale-finalized-revision notice correctly says that attaching evidence after finalization will not update the frozen filing bundle and that there is no safe recovery action in the described content-addressed lifecycle; it directs operators to link evidence before calculation. Stale finalized notice (`src/cadrumo/application/ledger/notices.py`)

## Assessment and follow-up

The strongest capability is defensive readiness reporting grounded in the same period/date and category facts that aggregation consumes, paired with visible attribution uncertainty instead of an unverified party assignment. Input/output contracts keep manual operations typed and preserve the provenance needed for review; the pinned repository and operation wrappers provide explicit profile and revision guards.

Two boundaries remain worth checking across callers. First, the party co-location module states that contradicted values produce blocking findings, but this chunk does not include the complete consumer that merges those findings into every invoice-draft review/readiness route; confirm both text-layer and structured readers pass role evidence and consume the contradiction findings before a filing decision. Second, ratio state and audit event are knowingly non-atomic as noted above. No tests were reviewed or run; this static pass does not prove that UI labels, adapters, source readers, or filing consumers preserve these contracts.

## Complete assigned-file coverage

- models.py (1,103 lines) (`src/cadrumo/application/ledger/models.py`) — all lines read.
- notices.py (90 lines) (`src/cadrumo/application/ledger/notices.py`) — all lines read.
- operator_input_contracts.py (61 lines) (`src/cadrumo/application/ledger/operator_input_contracts.py`) — all lines read.
- participation_operation.py (140 lines) (`src/cadrumo/application/ledger/participation_operation.py`) — all lines read.
- participation_read.py (95 lines) (`src/cadrumo/application/ledger/participation_read.py`) — all lines read.
- participation_rebuild_operation.py (184 lines) (`src/cadrumo/application/ledger/participation_rebuild_operation.py`) — all lines read.
- party_attribution.py (324 lines) (`src/cadrumo/application/ledger/party_attribution.py`) — all lines read.
- party_colocation.py (466 lines) (`src/cadrumo/application/ledger/party_colocation.py`) — all lines read.
- persistence_ports.py (17 lines) (`src/cadrumo/application/ledger/persistence_ports.py`) — all lines read.
- pinned_transaction_repository.py (100 lines) (`src/cadrumo/application/ledger/pinned_transaction_repository.py`) — all lines read.
- postal_shape_finding.py (142 lines) (`src/cadrumo/application/ledger/postal_shape_finding.py`) — all lines read.
- preconditions.py (65 lines) (`src/cadrumo/application/ledger/preconditions.py`) — all lines read.
- preflight.py (973 lines) (`src/cadrumo/application/ledger/preflight.py`) — all lines read.
- preflight_operation.py (164 lines) (`src/cadrumo/application/ledger/preflight_operation.py`) — all lines read.
- protocols.py (177 lines) (`src/cadrumo/application/ledger/protocols.py`) — all lines read.
- ratios.py (650 lines) (`src/cadrumo/application/ledger/ratios.py`) — all lines read.
<!-- /preserved:article -->
