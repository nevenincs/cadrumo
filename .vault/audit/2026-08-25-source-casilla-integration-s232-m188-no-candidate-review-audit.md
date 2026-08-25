---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:54e6567eb6d888b9059a9a47d77aa2d9eda01c605a3fa90150e228c0a33f5730'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S232 M188 no-candidate review`

## Scope

Independent review of `7928b1f7b1` and correction `778ade8778`: historical
design evidence, active M188 registry boundary, removed ADR, factual research,
and no-runtime/no-census outcome.

## Findings

### evidence boundary | low | current era and historical refusal are exact

The bundled current AEAT M188 design recomputes to SHA-256
`30ced236b558de21383c3eba6339cb720fc9a704d38eaa574dd9be55cf90f9e3`.
The active applicability revision selects only 2023 onward and refuses
2019--2022 rather than backdating its design. The research records the distinct
historic BOE composite as evidence needed before those years could be assessed.

### source boundary | low | summaries remain direct manual targets

The active revision has five manual summary casillas and no bindings, formulas,
extraction profile, export layout, secure source owner, resolver, producer, or
census candidate. These summaries remain available but do not substitute for
the repeated perceptor/declarant source fact, provenance, identity, correction,
or absence semantics.

### decision boundary | low | framework is sufficient

The correction deletes the accidental blank, unreferenced M188 ADR. Research is
factual-only: it records no supportable current candidate and expressly does
not call required tax facts inapplicable. The accepted source-connectivity
framework remains the sole governing decision. No runtime or census promotion
occurred.

### verification | low | focused checks are green

The implementer completed the exact 18-test M188 gate. Independent bounded
selector/refusal coverage passed 2 tests; Ruff passed on both M188 test modules.
Vault schema and ADR-status checks are clean.

## Recommendations

PASS. Keep the active no-candidate result and preserve direct manual summaries.
Reopen only after exact historic or active era evidence proves an authoritative
source fact, native row grain, secure non-lossy owner, destination mapping, and
separate lifecycle/export proof.

