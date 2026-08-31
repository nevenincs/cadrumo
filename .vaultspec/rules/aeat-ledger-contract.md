# AEAT ledger contract

## Monetary semantics

- Store an amount as its non-negative magnitude and carry economic direction in the owning typed direction field. Do not encode the same direction a second time in the numeric sign.
- Currency, precision, rounding, tax category, period, and counterparty identity remain explicit. Do not infer them from descriptions, account names, or UI placement.
- A derived balance or tax total is reproducible from immutable ledger facts and the active registry authority. Corrections append a new revision or reversal; they do not erase the evidence chain.

## Evidence and classification

- Evidence attached to a ledger revision is persisted as encrypted bytes with its integrity and provenance metadata. A path, URL, filename, or plaintext cache is not the evidence.
- IVA categories come from the canonical category set. Importers map external values into that set and refuse unknown or ambiguous classifications.
- Participation, ownership, and allocation values are derived through the canonical typed relationship mechanism. Do not duplicate percentages in unrelated records or silently normalize an inconsistent total.
- Missing evidence, unknown classification, and a genuine zero are distinct states and remain distinguishable through calculation and filing handoff.

## Verification

Tests cover sign/direction invariants, currency and rounding boundaries, encrypted evidence round trips, immutable revision behavior, classification refusal, and parity between ledger-derived and filing-facing totals.
