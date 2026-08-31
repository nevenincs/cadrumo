# AEAT calculation aggregation

## One aggregation mechanism

- Every registry aggregate resolves through the canonical typed aggregation mechanism. Do not add construct-name branches, modelo-specific `if` trees, substring dispatch, or a second summation path.
- An aggregation declaration identifies its source family explicitly and is enrolled in the shared resolver dispatch. Unknown, ambiguous, or structurally invalid declarations fail validation.
- `pull`, calculation, preview, and filing consume the same compiled aggregation semantics. No caller may reinterpret or partially reproduce the registry declaration.

## Source eligibility

- A source is included only when the registry relationship proves it belongs to the aggregate for the active revision and filing context.
- Missing source data and a proven zero are distinct states. Do not coerce absent, deferred, advisory, or unsupported inputs to zero in a filing-grade total.
- Deferred or advisory sources may produce diagnostics, but must not silently contribute to a complete total.
- Sign, rounding, currency, and period behavior come from the owning typed contracts; aggregation code must not infer them from field names or presentation labels.

## Verification

Exercise at least one positive multi-source case, exclusion cases, missing/deferred source behavior, and parity between pull and calculation. Tests must use the real resolver and compiled registry rather than a mocked substitute.
