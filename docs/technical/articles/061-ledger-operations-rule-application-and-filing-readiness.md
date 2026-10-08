# Ledger operations, rule application, and filing readiness

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-061` · **Topic:** [Ledger, invoices, evidence, and registers](../topics/ledger-invoices-and-registers.md)

<!-- preserved:article -->
## Scope

This chunk covers 24 ledger application modules, 5,841 lines and 47,628 measured proxy tokens. All nine bounded pages were read. It includes profile-bound ratio, review, rule, split, update, remove/reset, status and tracking operations; source-jurisdiction and document-consistency findings; and the projections and ports those surfaces share. Static only: no stored profile, ledger, provider, filing or test was executed.

## Review, rules, and shared operations

Ledger review parses the same canonical filter grammar used by the listing surface and maps status, issue, import, classification, text, direction and period into one query. The query applies those filters to a loaded catalogue, joins import/diagnostic events only when requested, and sorts by effective date then transaction ID. A list row carries compact facts; a detail query adds the transaction projection. Access derives its disclosed period from the parsed filter and binds it to the exact profile. Shared filter projection (`src/cadrumo/application/ledger/review_filter.py`) Review query and sorting (`src/cadrumo/application/ledger/review_projection.py`) Exact-profile read scope (`src/cadrumo/application/ledger/review_operation.py`)

Classification rules have bounded add/list/apply contracts and use an injected encrypted profile repository. Add validates category values under the pinned authority and delegates rule creation to the canonical action. Apply first builds one canonical match plan; dry-run returns its rows without mutation. Confirmed application fences each matched transaction write independently and tracks writer entry. If a later row fails validation before its writer begins after earlier rows committed, the operation returns a refusal with `PARTIAL` effect; an unknown failure after writer entry is not mislabeled as a clean no-op. This matches the sequential, per-row write model instead of promising batch atomicity. Rule request/result invariants (`src/cadrumo/application/ledger/rule_contracts.py`) Add/list/apply executors (`src/cadrumo/application/ledger/rule_operation.py`) Per-row write fence (`src/cadrumo/application/ledger/rule_operation.py`) Apply result/effect projection (`src/cadrumo/application/ledger/rule_results.py`)

The five ratio operations provide list, set, unset, eligible-category and validation views. Read endpoints are whole-profile reads; set/unset require COMMIT and use secure-reference input storage. Set resolves the category for the requested year, checks the value before the write, then calls the existing locked profile service. Unset has a typed no-override refusal; list suppresses stale rows and returns a distinct refusal when the stored profile conflicts with censo. Every public result is copied and checked against its terminal receipt. The ratio service’s profile/event split is non-atomic as documented in STAGE-2-060, so an interrupted set can leave the stored override without its audit append. Ratio worker inputs (`src/cadrumo/application/ledger/ratios_operation.py`) Ratio mutation executors (`src/cadrumo/application/ledger/ratios_operation.py`) Receipt-bound results (`src/cadrumo/application/ledger/ratios_operation.py`) COMMIT policy (`src/cadrumo/application/ledger/ratios_operation.py`)

Manual split, correction, remove and reset operations enforce exact-profile identity, bounded request/result models and explicit mutation authority. Split resolves all children against one revisioned catalogue and commits through a pinned repository; its result is cross-checked against the exact parent, child amounts/descriptions, direction and split lineage. Update carries a patch plus an explicit field mask so null clears survive secure JSON serialization without allowing unselected values to leak into the mutation. Removal and reset support no-effect dry runs, bound the complete receipt before mutation, then let the canonical action reload and recheck blockers during commit. Reset refuses while a finalized Modelo references ledger rows; removal preserves finalized blockers separately from nonblocking stale-draft advisories and reports cascaded evidence/attachments. Pinned split worker (`src/cadrumo/application/ledger/split_operation.py`) Split receipt correlation (`src/cadrumo/application/ledger/split_operation.py`) Masked update request (`src/cadrumo/application/ledger/update_operation.py`) Update commit and validation refusal (`src/cadrumo/application/ledger/update_operation.py`) Remove preview/commit (`src/cadrumo/application/ledger/remove_operation.py`) Reset blocker gate (`src/cadrumo/application/ledger/reset_operation.py`)

The pinned transaction repository makes a previously loaded catalogue an explicit compare-and-swap basis: unrevisioned saves fail and a write must match the revision resolved before target selection. Repository protocols keep the application boundary structural, while transaction and tracking projections preserve exact decimal text and avoid exposing raw imported source columns or the full source path. Pinned repository (`src/cadrumo/application/ledger/pinned_transaction_repository.py`) Transaction projection (`src/cadrumo/application/ledger/transaction_projection.py`) Tracking and imported provenance (`src/cadrumo/application/ledger/tracking_projection.py`)

## Readiness and audit surfaces

The status operation can scope money totals to a period, but keeps lifecycle counts and stale-filing history profile-wide. With a period selected it also joins each preflight issue to the current ledger facts that explain it; if the row disappeared between the preflight and join reads, the issue remains visible with `transaction_present=false` instead of being silently dropped. Stale filings are attributed to a profile through their work-unit owner, and older fingerprints expose `covers_current_fact_set=false` so their narrower comparison is not mistaken for evidence of drift. The access resolver intentionally asks for whole-profile authority because this result includes global filing history. Status scope and projections (`src/cadrumo/application/ledger/status_operation.py`) Status executor (`src/cadrumo/application/ledger/status_operation.py`) Readiness issue join (`src/cadrumo/application/ledger/readiness_query.py`) Profile-owned stale filing query (`src/cadrumo/application/ledger/stale_filing_query.py`)

The `track` read combines transaction state, imported provenance, evidence/edit/lifecycle lineage and finalized declaration participation. It reduces an imported source path to the filename and excludes raw source columns and source digest from the transport projection. Participation can also be read independently by a current or superseded transaction handle; rebuild is a separate guarded operation in the prior chunk. Track executor (`src/cadrumo/application/ledger/track_operation.py`) Track projection invariants (`src/cadrumo/application/ledger/track_operation.py`) Imported and lineage projections (`src/cadrumo/application/ledger/tracking_projection.py`)

Source jurisdiction is resolved as a typed outcome: an explicit operator value wins, nonresident IRNR and impatriado profiles require an operator statement, undeclared residency stays unresolved, and a declared ordinary resident defaults to Spain. That preserves unresolved data rather than silently stamping ES. Separately, a printed regime legend that conflicts with a positive IVA amount or rate produces a discrepancy finding; zero rate/cuota alone is not treated as a charged line. Jurisdiction decision (`src/cadrumo/application/ledger/source_jurisdiction.py`) Regime contradiction finding (`src/cadrumo/application/ledger/regime_contradiction.py`)

Review advisories are projected as closed kinds for both queue rows and document details, including party-attribution and country-vocabulary warnings. The structured-invoice port translates XML/format-specific readers into syntax-neutral values and element paths; the application does not own parsing syntax. Shared advisory kinds (`src/cadrumo/application/ledger/review_advisories.py`) Structured invoice boundary (`src/cadrumo/application/ledger/structured_invoice_ports.py`)

## Assessment and follow-up

The operations consistently bind profile, effect and receipt, and the multirow paths disclose their actual consistency model: full-catalogue revision pinning for split, per-row partial commits for rule application, and bounded dry-run receipts before destructive removal/reset. Read models retain missing/stale facts as signals instead of dropping them, and sensitive storage is delegated through explicit operation policies and profile-bound ports.

The principal limits are cross-store atomicity for ratio state plus audit, and the fact that static inspection cannot establish how frontends present partial rule results or stale-filing coverage. Verify that callers visibly distinguish partial rule application from full success and show the `covers_current_fact_set` qualification. No tests were reviewed or run, and the injected persistence/operation supervisors were not executed.

## Complete assigned-file coverage

- ratios_operation.py (976 lines) (`src/cadrumo/application/ledger/ratios_operation.py`) — all lines read.
- read_access.py (57 lines) (`src/cadrumo/application/ledger/read_access.py`) — all lines read.
- readiness_query.py (119 lines) (`src/cadrumo/application/ledger/readiness_query.py`) — all lines read.
- regime_contradiction.py (115 lines) (`src/cadrumo/application/ledger/regime_contradiction.py`) — all lines read.
- remove_operation.py (274 lines) (`src/cadrumo/application/ledger/remove_operation.py`) — all lines read.
- reset_operation.py (282 lines) (`src/cadrumo/application/ledger/reset_operation.py`) — all lines read.
- review_advisories.py (111 lines) (`src/cadrumo/application/ledger/review_advisories.py`) — all lines read.
- review_filter.py (48 lines) (`src/cadrumo/application/ledger/review_filter.py`) — all lines read.
- review_operation.py (185 lines) (`src/cadrumo/application/ledger/review_operation.py`) — all lines read.
- review_projection.py (266 lines) (`src/cadrumo/application/ledger/review_projection.py`) — all lines read.
- rule_contracts.py (271 lines) (`src/cadrumo/application/ledger/rule_contracts.py`) — all lines read.
- rule_operation.py (716 lines) (`src/cadrumo/application/ledger/rule_operation.py`) — all lines read.
- rule_repository.py (78 lines) (`src/cadrumo/application/ledger/rule_repository.py`) — all lines read.
- rule_results.py (213 lines) (`src/cadrumo/application/ledger/rule_results.py`) — all lines read.
- source_jurisdiction.py (175 lines) (`src/cadrumo/application/ledger/source_jurisdiction.py`) — all lines read.
- split_operation.py (397 lines) (`src/cadrumo/application/ledger/split_operation.py`) — all lines read.
- stale_filing_query.py (148 lines) (`src/cadrumo/application/ledger/stale_filing_query.py`) — all lines read.
- status_operation.py (258 lines) (`src/cadrumo/application/ledger/status_operation.py`) — all lines read.
- structured_invoice_ports.py (107 lines) (`src/cadrumo/application/ledger/structured_invoice_ports.py`) — all lines read.
- track_operation.py (158 lines) (`src/cadrumo/application/ledger/track_operation.py`) — all lines read.
- tracking_projection.py (159 lines) (`src/cadrumo/application/ledger/tracking_projection.py`) — all lines read.
- transaction_projection.py (99 lines) (`src/cadrumo/application/ledger/transaction_projection.py`) — all lines read.
- transaction_repository.py (52 lines) (`src/cadrumo/application/ledger/transaction_repository.py`) — all lines read.
- update_operation.py (577 lines) (`src/cadrumo/application/ledger/update_operation.py`) — all lines read.
<!-- /preserved:article -->
