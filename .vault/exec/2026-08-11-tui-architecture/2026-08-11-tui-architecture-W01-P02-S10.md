---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b857f984b1c250b27ec53d09d8c4f16a95ba06ad4dc0868327db24493bd2ebd2'
step_id: 'S10'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define revision-bound interaction requests, single-use response tokens, proposal digests, and apply or reject responses

## Scope

- `src/cadrumo/application/operations/_interactions.py`
- `src/cadrumo/application/operations/tests/test_interactions.py`

## Description

- Re-ground typed interaction, revision, response-token, continuation-digest, proposal-digest, and apply/reject semantics through live code/vault RAG, the accepted D4 decision, plan/research, and targeted source confirmation.
- Define strict immutable interaction requests bound to operation identity, revision, response schema, safe presentation code, exact continuation digest, and optional UTC expiry.
- Define discriminated apply/reject responses bound to operation and interaction identities, revision, opaque response token, continuation digest, reviewed-proposal digest, actor reference, and UTC response time; APPLY additionally binds the exact baseline and proposed-effect digests.
- Exclude callbacks, localized prompts, raw secret values, frontend state, and domain-owned proposal payloads from the generic contract.

## Outcome

- Reused S06 interaction kinds, S07 identity/revision/reference models, canonical `Hex64Str`, `ContentDigest`, stable event codes, and UTC validation; no response-token or exact-continuation authority existed to duplicate.
- APPLY immutably binds the exact baseline, reviewed proposal, proposed effect, actor, operation, interaction, revision, token, continuation, and response time. REJECT separately binds actor/time and the exact reviewed proposal without inventing baseline or effect evidence for a no-effect decision; malformed or omitted identities and digests fail closed.
- Focused verification passed: `uv run pytest src/cadrumo/application/operations/tests/test_interactions.py -q` reported `15 passed in 5.88s`; Ruff reported `All checks passed!`; basedpyright reported `0 errors, 0 warnings, 0 notes`.

## Notes

- Live code and vault semantic searches succeeded on port 8766. The code index reported `2862` missing sections, so targeted `rg` and whole governing epicenters were used rather than treating absence as evidence.
- Live remediation grounding found no canonical actor type whose constraints were a superset, so `OperationActorReference` is a narrow stable machine-reference alias rather than a domain actor redeclaration. Mutation, exact-correlation tuple, discriminated-union round-trip, and reject-separation tests cover the D4 evidence boundary.\n- Single-use consumption is enforced later by the supervisor/registry transaction; this Step defines the unforgeable token identity and exact response binding without pretending a frozen model can own persistence state.
- Final independent review closed all critical, high, and medium findings. The binding plan row was closed through `vault plan step check`. `uvx vaultspec-core vault check all` exited zero with `1357 warnings`; global residuals include 4 annotation warnings, 40 markdown warnings, 29 schema warnings, 2 modified-stamp warnings, and pre-existing body-schema corpus findings.


