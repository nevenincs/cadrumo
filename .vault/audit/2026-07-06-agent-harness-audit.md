---
tags:
  - '#audit'
  - '#agent-harness'
date: '2026-07-06'
modified: '2026-08-26'
body_hash: 'sha256:f27f1f865c12b19b740d5cfa23168ff44cfb4b320d86c2f38db0dfc9f5a86d22'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# `agent-harness` audit: `Response formula provenance hardening review`

## Scope

Reviewed the `P06.S22` response-layer provenance hardening for the agent golden-eval runner.
The review checked that `formula_id` is required only for scenario-declared expected computed
casillas, while input/manual rows remain governed by `legal_refs` and `source_refs` only.

## Findings

### response-formula-provenance | low | no blocking findings

The independent reviewer found no blocking issues. `_check_response_provenance` scopes
`formula_id` enforcement to `scenario.expected_computed_casillas`, treats missing expected
computed observations as a response-provenance failure, and does not over-gate manual or input
rows. The tests dispatch the real CLI path and mutate the real response payload, with no mocks,
fakes, monkeypatching, or duplicated calculation logic.

The reviewer noted one non-blocking residual risk: there was not yet a negative-control test
that clears `formula_id` only on non-computed/manual rows and proves the dimension still passes.
That residual was closed in the same slice by adding the negative-control test against the real
M130 calculate response.

## Recommendations

Keep future response-provenance checks tied to `expected_computed_casillas` or another
scenario-declared computed-row contract. Do not require `formula_id` on every observation row,
because manual and input rows legitimately carry legal/source grounding with no formula.
