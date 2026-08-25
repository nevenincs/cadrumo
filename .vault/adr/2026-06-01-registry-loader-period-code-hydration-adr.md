---
tags:
  - '#adr'
  - '#registry-authority-flow'
date: '2026-06-01'
modified: '2026-08-25'
body_hash: 'sha256:ddb67a28ebb7359220fc656e61b406f103256d43528bd6146f4e4df3f6656807'
related:
  - '[[2026-06-04-registry-period-code-union-research]]'
---
# `registry-loader-period-code-hydration` adr: PeriodCode validator is the compiler boundary | (**status:** `accepted`)

## Problem Statement

The registry loader compiles TOML period-code strings into ModeloRevision objects. The schema defines two period-code surfaces:

- `StandardPeriodCode` (StrEnum): closed enumeration of standard filing-period forms (1T-4T, 1P-4P, 0A, 01-12)
- `PeriodCode` (Annotated[str]): validator that accepts StandardPeriodCode members + extended forms (EXT-*T, AD-HOC, EVENT-N)

The question is whether the loader should hydrate TOML period-code strings to `StandardPeriodCode` enum members when the token matches the closed subset, falling back to raw strings for EXT-*T/AD-HOC/EVENT-N tokens, OR always emit raw strings and let runtime consumers cast if they need typed values.

## Considerations

The existing `PeriodCode` validator (in `_schema.py`) already establishes the boundary: it accepts raw strings and validates them against the closed set + regex patterns. The loader delegates to pydantic validation, so it receives strings and passes them through. No intermediate hydration is happening.

`StandardPeriodCode` exists as a utility for places where code needs runtime certainty that a period is a standard form. Export layouts, deadline windows, and snapshot consumers can use it as a guard if they need to reject extended forms. But the loader is not a consumer; it is a compiler that materializes schema objects.

The registry authority flow ADR establishes the loader's role: it reads TOML, rejects local catalogues and ambiguous conflicts, includes all read files in cache invalidation, and compiles fragments into strict pydantic schema objects. The validation boundary is the pydantic model, not a pre-validation hydration step.

## Constraints

Do not add compilation logic that is not grounded in schema materialization. Hydration is a type transformation; it is a consumer responsibility, not a compiler responsibility.

Do not weaken the loader's role as a deterministic, side-effect-free TOML compiler. Pre-validation type casting would introduce state-dependent logic (token matches enum → hydrate, else → pass through), which is harder to reason about.

## Implementation

Accept the existing design: `PeriodCode` validator enforces the contract; the loader emits raw strings.

When runtime code needs `StandardPeriodCode` certainty, it should:

1. Accept a `PeriodCode` string (already validated by pydantic)
2. Attempt to construct `StandardPeriodCode(value)` if enum membership is required
3. Handle `ValueError` if the token is an extended form (EXT-*T, AD-HOC, EVENT-N)
4. Fall back to raw string or raise a domain-specific error depending on context

This pattern preserves the loader as a strict schema compiler: it does not add pre-validation casting. Consumers that need typed period codes perform their own hydration based on runtime requirements.

The pattern is consistent with how the registry handles other closed-form + extended-form axes (language codes, legal-entity forms, etc.): schema boundary is permissive (accepts all valid forms), runtime consumers are precise (hydrate to enum or raise if the context requires a standard form).

## Rationale

Hydration in the loader would couple the compiler to the consumer use case and introduce conditional logic that is not reflected in the schema. The validator is the natural place for the contract: it documents what is accepted and what is rejected at the persistence boundary.

The registry authority flow ADR emphasizes that the loader compiles, validates, and rejects; runtime consumers request snapshots and project them. Hydration is projection work, not compilation work.

## Consequences

Runtime code that needs `StandardPeriodCode` must attempt the conversion. This is explicit and testable. Consumers are aware they are narrowing from `PeriodCode` (all valid forms) to `StandardPeriodCode` (standard forms only).

Code that works with period codes without caring about the standard/extended distinction continues to work with raw strings.

Snapshot consumers and export projections that need to enforce "standard forms only" can use a guard like:

```python
def require_standard_period(code: PeriodCode) -> StandardPeriodCode:
    try:
        return StandardPeriodCode(code)
    except ValueError as exc:
        raise DomainError(f"expected standard period, got {code!r}") from exc
```

This pattern is local, explicit, and testable.
