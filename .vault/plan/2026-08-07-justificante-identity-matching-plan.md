---
tags:
  - '#plan'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:150afc34db7824829974ed73b8c30f92ffb4c5c1c1bd32f9fe41d21411ce4d77'
tier: L2
related:
  - '[[2026-08-07-justificante-identity-matching-adr]]'
---

# `justificante-identity-matching` plan

## Description

Executes `2026-08-07-justificante-identity-matching-adr`: the three call sites
that pass a register-sourced `expediente_id` into
`Justificante.matches_filing_target`'s receipt-namespace `presentation_id`
parameter stop doing so at the two register-reconciliation sites (no
receipt-namespace value is available there, per the ADR's Considerations), the
one redundant call at the capture-stamping site is dropped in favor of its
existing correct `csv == csv` check, the predicate's docstring is strengthened
to document the namespace contract, the parallel-authored pinning test is
updated to assert the corrected behavior, and the swallowed-outcome
observability gap is closed with a `Notice` distinguishing the four reasons a
justificante artefact can yield no saved evidence. `P01` lands the domain and
application fixes plus their tests; `P02` closes observability.

## Steps

### Phase `P01` - Correct the presentation_id namespace at each call site

Land the scoped removal at the three matching call sites, strengthen the predicate docstring, and update the parallel-authored pinning test to the corrected behavior.

- [ ] `P01.S01` - Drop the expediente_id argument passed as presentation_id; `src/cadrumo/application/live/_filed_observation_persistence.py`.
- [ ] `P01.S02` - Drop the expediente_id argument passed as presentation_id; `src/cadrumo/application/live/_justificante.py (_justificante_matches_capture_axis)`.
- [ ] `P01.S03` - Drop the redundant presentation_id argument now that the csv equality check already covers identity; `src/cadrumo/application/live/_justificante.py (register_capture_as_filing_evidence)`.
- [ ] `P01.S04` - Strengthen the presentation_id parameter docstring to state the receipt-namespace contract and forbid a register-sourced expediente_id; `src/cadrumo/domain/justificante/_schema.py`.
- [ ] `P01.S05` - Update the pinning test asserting today's rejection to assert the corrected match; `src/cadrumo/domain/justificante/tests/test_filing_target.py`.
- [ ] `P01.S06` - Add a real-fixture regression proving the register-reconciliation path enrolls a committed M303 justificante that never matched under the broken comparison; `src/cadrumo/application/live/tests/_filed_capture_history_support.py and a new or existing test in src/cadrumo/application/live/tests`.
- [ ] `P01.S07` - Run the domain and application justificante test suites and confirm green; `src/cadrumo/domain/justificante/tests and src/cadrumo/application/live/tests`.

### Phase `P02` - Distinguish swallowed justificante-matching outcomes

Surface a Notice distinguishing unreadable artefact, manifest mismatch, unparsable PDF, and predicate rejection so an operator can see why a capture produced no evidence.

- [ ] `P02.S08` - Distinguish the four swallowed outcomes and return a typed reason instead of returning None uniformly; `src/cadrumo/application/live/_filed_observation_persistence.py (_parse_matching_filed_justificante)`.
- [ ] `P02.S09` - Emit a Notice through the shared envelope spine naming the unreached-evidence reason when an enrollment call finds an artefact but saves nothing; `src/cadrumo/application/live/_filed_observation_persistence.py (persist_filed_justificante_metadata and enroll_filed_justificante_evidence)`.
- [ ] `P02.S10` - Add a mutation-proof test confirming the reason-distinguishing branch fires per swallowed case and confirm the CLI report surfaces the Notice; `src/cadrumo/application/live/tests and src/cadrumo/entrypoints/cli/tests`.

## Parallelization

`P01.S01`, `P01.S02`, and `P01.S03` touch disjoint call sites and can run in
parallel; `P01.S04` (docstring) has no code dependency on them and can run
alongside. `P01.S05` and `P01.S06` depend on `S01`-`S03` landing first, since
both assert against the corrected behavior. `P01.S07` gates the Phase closed
and must run last within `P01`. `P02` depends on `P01` closing first: the
reason-distinguishing branch in `P02.S08` reads the same predicate call sites
`P01` corrects, so building it against the pre-fix behavior would encode the
defect. Before `P01.S05` begins, re-check whether the parallel-authored
pinning test mentioned in the ADR's Constraints has landed elsewhere in the
tree; if so, absorb and update that test in place rather than authoring a
second one, per `aeat-agent-orchestration`'s in-scope-regression mandate.

## Verification

- Every Step in this plan is closed (`- [x]`).
- `src/cadrumo/domain/justificante/tests/test_filing_target.py` asserts the
  corrected matching behavior (no assertion still encodes
  `presentation_id == expediente_id` as valid) and passes.
- The `P01.S06` real-fixture regression passes and would fail if `P01.S01`-
  `S03` were reverted (proven by a deliberate revert-and-confirm-red pass
  before the final commit, per `aeat-quality-gates`' "a gate is unproven until
  it bites").
- `uv run --no-sync pytest src/cadrumo/domain/justificante/tests
  src/cadrumo/application/live/tests -m unit` (sequential, per
  `aeat-local-execution`) is green with the full log captured to a file, not
  piped through a truncating filter.
- The `P02.S10` mutation-proof test fails when the reason-distinguishing
  branch is reverted to the uniform `logger.warning` plus `return None` shape,
  and passes against the corrected code.
- No legal-catalogue entry is added or modified by this plan.
