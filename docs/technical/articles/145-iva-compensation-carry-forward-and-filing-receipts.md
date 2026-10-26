# IVA compensation carry-forward and filing receipts

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-145` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 11 files, 2,151 manifest-counted lines, 88,399 bytes, and 19,070 measured tokens across IVA compensation and justificante receipt domains. All four bounded pages were read through their listed ranges. This is static inspection only; I did not import or execute the application, modify `src/`, run tests, or validate legal content against external authorities.

## Product capabilities

The IVA compensation domain turns filed-period observations into dated credit lots, projects the remaining wallet, partitions a year’s credit between the last filing period and amounts generated earlier in the year, and reconciles conflicting sources before a consumer uses a starting balance. The derivation helper computes new compensation from negative Modelo 303 results while excluding a refunded result; the filed-casilla adapter records which registry-declared casillas and values supported its result available credit derivation (`src/cadrumo/domain/iva_compensation/carry_forward.py`) filed casilla derivation (`src/cadrumo/domain/iva_compensation/filed_derivation.py`).

The carry-forward projection applies recorded use FIFO: earlier credit is consumed before later credit, and a period’s own new generation is appended only after that period’s application. Each output lot retains its taxpayer, source year and period, source observation key, generated/applied/remaining amounts, age, and a coarse expiry-review state. A separate balance report sums the lots and exposes active, expired-review, and next-review-year figures carry-forward report and projection (`src/cadrumo/domain/iva_compensation/carry_forward.py`) balance report (`src/cadrumo/domain/iva_compensation/balance.py`). A year-end partition reports how much remaining credit is associated with the final period and how much was generated earlier in that year year-end partition (`src/cadrumo/domain/iva_compensation/carry_forward.py`).

Reconciliation accepts an AEAT wallet observation, locally reconstructed filed history, and an optional taxpayer override. It checks target identity and period, compares evidence against the requested registry snapshot, and returns a decision carrying selected authority, divergence, blocking state, timestamps, and source provenance. The decision flow gives an explicit override priority, permits a documented first-period zero case, distinguishes missing and stale wallet evidence, and checks fresh wallet evidence against local recurrence reconciliation entry point (`src/cadrumo/domain/iva_compensation/reconciliation.py`) decision paths (`src/cadrumo/domain/iva_compensation/reconciliation.py`) wallet target check (`src/cadrumo/domain/iva_compensation/reconciliation.py`).

The justificante domain defines a strict, frozen record for a parsed AEAT filing receipt: CSV, model and exercise, typed period, optional presentation number, taxpayer ID, payment/refund totals, printed verification URL, source PDF reference and digest, and UTC parse time. It coerces a printed period token only when it can pair it with a numeric exercise, and offers a predicate for matching a receipt to model/year/period and optionally taxpayer. The repository protocol specifies load, save, and iteration without prescribing storage receipt schema (`src/cadrumo/domain/justificante/schema.py`) period parsing and filing-target match (`src/cadrumo/domain/justificante/schema.py`) repository protocol (`src/cadrumo/domain/justificante/protocols.py`).

## How it works

Period states are immutable, strict records tied to a filing year, period, registry snapshot, provenance, presentation time, and source observation. AEAT-derived fields are constrained by the stated provenance, period/year pairs must agree, and amounts used by the carry-forward projection cannot be negative. The `Period` and registry snapshot references preserve the authority context for interpreting captured casillas period-state contract (`src/cadrumo/domain/iva_compensation/carry_forward.py`) provenance and period checks (`src/cadrumo/domain/iva_compensation/carry_forward.py`).

The carry-window resolver delegates the number of years to a pinned authority operation and accepts an effective date, while the projection resolves each lot at its source period end. Lot age and expiry labels are review indicators rather than computed statutory filing deadlines. This intentionally leaves the next legal-action date to a caller or higher-level workflow carry-window authority lookup (`src/cadrumo/domain/iva_compensation/carry_window.py`) lot expiry labels (`src/cadrumo/domain/iva_compensation/carry_forward.py`). The year-opening helper returns `None` when the first captured state is not the first period or does not contain enough prior-balance evidence, keeping unknown distinct from a known zero opening-balance derivation (`src/cadrumo/domain/iva_compensation/carry_forward.py`).

The reconciliation API uses typed authority kinds and source records to retain where values came from. Local recurrence authority construction carries source filing years, periods, and registry snapshot references. Wallet observations must match the taxpayer and requested year/period; stale status is based on a caller-configurable age limit whose default is defined in the module. The receipt’s printed `presented_at` remains a naive local timestamp because the receipt gives Madrid wall-clock time without an offset; parse completion instead uses `UtcInstant` authority source models (`src/cadrumo/domain/iva_compensation/reconciliation.py`) local recurrence source (`src/cadrumo/domain/iva_compensation/reconciliation.py`) wallet staleness (`src/cadrumo/domain/iva_compensation/reconciliation.py`) receipt timestamp contract (`src/cadrumo/domain/justificante/schema.py`).

## Knowledge and data

The models contain the structural facts needed for deterministic projection: filed amounts, period/year identity, observation provenance, and selected registry snapshots. The carry-window length itself is resolved from authority data, not a hard-coded statutory duration in this domain. `filed_derivation` likewise receives a `CompensationCasillaDeclarations` value from the caller, so the registry-selected meaning of posterior, generated, and result casillas is outside the chunk. The carry-forward code documents Modelo 303 boxes and legal rules, but this inspection does not independently verify those legal interpretations against current AEAT or legislation casilla declarations (`src/cadrumo/domain/iva_compensation/filed_derivation.py`) authority-supplied carry window (`src/cadrumo/domain/iva_compensation/carry_window.py`).

The justificante record stores a digest and privacy-preserving source path but does not itself parse PDF bytes, prove the URL belongs to AEAT, fetch that URL, or verify the CSV against an independently obtained value. Its documentation explicitly assigns CSV verification to its caller. The repository is only a protocol here; encryption, access control, retention, and concrete persistence are implementation concerns elsewhere verification boundary (`src/cadrumo/domain/justificante/schema.py`) receipt repository boundary (`src/cadrumo/domain/justificante/protocols.py`).

## Security and safety

The compensation models emphasize provenance and refusal. Snapshot and target checks prevent a wallet for another filing from being silently adopted; stale, missing, contradictory, and unusable evidence take distinct decision paths; and overrides require an explanation plus an evidence locator. Amount and lot invariants prevent several malformed ledgers from reaching the balance projection. The output still needs a downstream policy that treats `blocked` decisions and coarse expiry review states appropriately override record (`src/cadrumo/domain/iva_compensation/reconciliation.py`) missing/stale/fresh-wallet paths (`src/cadrumo/domain/iva_compensation/reconciliation.py`).

One material projection gap is visible in `build_iva_compensation_carry_forward_report`: it initializes an opening balance and subtracts applications from it, but the report schema carries only `opening_applied_amount`, not an opening remainder or an opening-balance lot. Any part not consumed by captured applications disappears from the returned `lots` and from `build_iva_wallet_balance_report`, which totals those lots. For example, a positive opening balance with no period states produces an empty-lot report; a balance larger than recorded applications reports only the amount used. Callers would need to preserve and add the remainder independently, or the report should materialize it opening balance consumption and returned fields (`src/cadrumo/domain/iva_compensation/carry_forward.py`) projection return (`src/cadrumo/domain/iva_compensation/carry_forward.py`) balance totals from lots (`src/cadrumo/domain/iva_compensation/balance.py`). The docstring’s claim that a negative opening balance is refused is also conditional in implementation: with no application, `opening_applied_amount` remains zero and the negative input is not directly validated; when applications make that field negative, model validation refuses it opening-balance branch (`src/cadrumo/domain/iva_compensation/carry_forward.py`).

The age check marks a wallet stale only when `decided_at - captured_at` exceeds the threshold. A future-dated capture therefore has a negative age and is treated as fresh; any clock-skew or implausible-future check must be enforced elsewhere. The receipt schema accepts `AnyHttpUrl`, which is broader than an AEAT-host allowlist; this is data validation, not network access, so callers that open the printed URL should validate its destination staleness predicate (`src/cadrumo/domain/iva_compensation/reconciliation.py`) verification URL type (`src/cadrumo/domain/justificante/schema.py`).

## Implementation assessment

The separation between observed filed states, authority-resolved carry windows, lot projection, and decision provenance makes the ledger explainable. Decimal amounts and strict frozen schemas reduce accidental mutation and coercion. The strongest follow-up is to resolve the opening-credit omission before consumers interpret the wallet total as complete. Reconciliation should also reject future wallet timestamps or explicitly define permitted clock skew, and receipt URL consumers should apply an AEAT destination policy. There are no tests in this chunk; static inspection cannot establish how consumers handle blocked decisions, missing carry-window authority, or receipt URL trust.

## Dependencies and follow-up

Trace opening-balance callers and wallet consumers to determine whether they separately retain unused prior credit; if not, carry-forward totals can understate available compensation. Confirm that callers pass the target registry snapshot consistently to casilla declarations, recurrence reconstruction, and wallet observations. At integration level, verify the evidence locator for overrides is reviewable, future capture timestamps are bounded, blocked states stop filing, and receipt CSV verification uses a value independent of the PDF. Review concrete justificante repository controls in its adapter implementation.

## Complete assigned-file coverage

- iva_compensation/__init__.py (`src/cadrumo/domain/iva_compensation/__init__.py`)
- iva_compensation/balance.py (`src/cadrumo/domain/iva_compensation/balance.py`)
- iva_compensation/carry_forward.py (`src/cadrumo/domain/iva_compensation/carry_forward.py`)
- iva_compensation/carry_window.py (`src/cadrumo/domain/iva_compensation/carry_window.py`)
- iva_compensation/errors.py (`src/cadrumo/domain/iva_compensation/errors.py`)
- iva_compensation/filed_derivation.py (`src/cadrumo/domain/iva_compensation/filed_derivation.py`)
- iva_compensation/reconciliation.py (`src/cadrumo/domain/iva_compensation/reconciliation.py`)
- justificante/__init__.py (`src/cadrumo/domain/justificante/__init__.py`)
- justificante/errors.py (`src/cadrumo/domain/justificante/errors.py`)
- justificante/protocols.py (`src/cadrumo/domain/justificante/protocols.py`)
- justificante/schema.py (`src/cadrumo/domain/justificante/schema.py`)
<!-- /preserved:article -->
