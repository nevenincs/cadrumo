---
tags:
  - '#adr'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - '[[2026-06-04-cross-domain-continuity-research]]'
---

# `cross-domain-continuity` adr: `verification-predicate-strategy` | (**status:** `accepted`)

## Problem Statement

The `verify_modelo_revision` path enforces two kinds of completeness contracts:

1. Per-casilla presence — operator must supply a value for every required
   manual-input casilla before `VERIFICADO_COMPLETO` is granted.
2. Cross-casilla structural invariants — certain AEAT filing rules require that
   a combination of casillas be simultaneously non-zero (e.g. Modelo 130: if
   ingresos is non-zero then rendimiento neto must also be present).

The existing Layer 1 mechanism (`CasillaDefinition.required: bool` + the
`_required_input_casillas_for_revision` resolver at `_actions.py:1981`) handles
case 1. Case 2 has no machine-enforceable representation in the registry today —
the operator cannot receive a structured BLOCKING finding for invariant
violations, only a silent gap.

## Considerations

- Adding per-revision predicate definitions to the registry keeps invariants
  co-located with their legal authority, consistent with the registry-authority
  principle (`aeat-registry-authority-flow` rule).
- Layer 1 (`required = true`) is the cheaper path; it must not be replaced by
  predicate expressions where a single-field gate suffices.
- Predicate DSL complexity should be minimal in W04: `all_nonzero([ids])` and
  `any_nonzero([ids])` cover the filing rules confirmed via Orden HAP/2250/2015
  and Orden HAC/….
- `ModeloVerificationFinding` already carries `kind=BLOCKING_RULE` and is
  persisted via `VerificationReport` without schema migration.
- `VerificationPredicateDefinition` must be nullable/optional in
  `ModeloRevision` (default empty tuple) so existing revisions without
  predicates are unaffected.

## Constraints

- `ModeloRevision` is a frozen pydantic v2 model loaded from TOML by the
  registry loader. New fields must carry safe defaults to preserve backward
  compatibility with revisions that do not declare predicates.
- Predicate evaluation must happen inside `_classify_verification_outcome` or a
  dedicated helper called from `verify_modelo_revision`, after all casilla
  values are resolved, to avoid polluting the loading path.
- The `VerificationReport` schema adds no new fields — findings are emitted as
  `ModeloVerificationFinding(kind=BLOCKING_RULE, severity=BLOCKING, ...)` using
  existing slots.
- Complex predicate DSL (conditional, arithmetic, threshold) is deferred to W09.

## Implementation

**Layer 1 — single-casilla mandatory gate (existing + applied)**

`CasillaDefinition.required: bool` (default `False`) in `_schema.py:1606`.
Set `required = true` in TOML for every input casilla that must be non-empty
per the modelo's official filing instructions.

Engine resolution: `_required_input_casillas_for_revision` (`_actions.py:1981`)
collects casillas with `input_kind="manual" and required=True`. A missing
required casilla produces a `MISSING_REQUIRED_CASILLA` finding and blocks
`VERIFICADO_COMPLETO`.

**Layer 2 — cross-casilla predicate gate (new)**

New `VerificationPredicateDefinition` pydantic model in the registry schema:

```
predicate_id: str        # e.g. "130-ingresos-rendimiento-coherence"
legal_refs: tuple[str, ...]
expression: str          # "all_nonzero([\"01\", \"03\"])"
finding_kind: Literal["BLOCKING_RULE"]
```

`ModeloRevision.verification_predicates: tuple[VerificationPredicateDefinition, ...]`
defaults to `()`.

Evaluator in `_classify_verification_outcome` (or a helper):
1. Empty tuple → skip.
2. For each predicate, parse expression: `all_nonzero([ids])` or
   `any_nonzero([ids])`.
3. Resolve each `id` against the revision's current casilla values.
4. Evaluate: `all_nonzero` → all resolved values are non-zero;
   `any_nonzero` → at least one is non-zero.
5. Failing predicate → `ModeloVerificationFinding(kind=BLOCKING_RULE,
   severity=BLOCKING, predicate_id=predicate_id, legal_refs=...)`.

**Decision boundary**

| Gate | Use when |
|------|----------|
| Layer 1 `required=true` | Single casilla must be present / non-empty |
| Layer 2 predicate | Cross-casilla invariant requires ≥2 casillas' relationship |

## Rationale

Co-locating invariants in the TOML registry allows legal-authority provenance
(via `legal_refs`) to travel with the predicate, consistent with the
registry-authority-flow discipline established in the accepted
`2026-05-12-cli-workflow-redesign-verified-complete-adr`. The W04 DSL subset
(`all_nonzero`, `any_nonzero`) is narrow enough to implement without a parser;
it covers the confirmed AEAT filing invariants without over-engineering.

The `found_verificado_completo` boolean invariant on `VerificationReport` is
preserved: Layer 2 findings are `BLOCKING` severity so the existing
`_classify_verification_outcome` logic produces `BLOCKED` status and
`granted=False` without schema changes.

## Consequences

- All existing revisions with empty `verification_predicates` behave identically
  to pre-W04 behaviour (zero predicate overhead).
- Operators receive structured `BLOCKING_RULE` findings for cross-casilla
  violations, consistent with the IVA-wallet and registry-snapshot findings
  already in the ADR-accepted `VERIFICADO_COMPLETO` contract.
- W09 may extend the DSL (threshold, conditional, arithmetic) by adding new
  expression parsers without changing the `VerificationPredicateDefinition`
  struct or the `ModeloRevision` schema.
