---
tags:
  - '#plan'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-06'
tier: L2
related:
  - '[[2026-07-01-agent-harness-adr]]'
  - '[[2026-07-01-agent-harness-research]]'
  - '[[2026-07-02-agent-harness-content-review-audit]]'
---

# `agent-harness` plan

### Phase `P01` - D2 - retire the unused LIVE_READ mutability member

Delete the dormant OperatorMutability.LIVE_READ member after a zero-consumer sweep, per retired-enum-members-need-consumer-reconciliation, and re-confirm the live command family stays LOCAL_STATE_MUTATING.

- [x] `P01.S01` - status:done (commit 84f84166f) - sweep zero consumers of OperatorMutability.LIVE_READ across production and test code, then delete the member; `src/aeat/core/observability/_operator_surface.py`.
- [x] `P01.S02` - status:done (commit 84f84166f) - re-confirm the live command family stays LOCAL_STATE_MUTATING and the operator_surface tests pass; `src/aeat/core/observability/tests/test_operator_surface.py`.

### Phase `P02` - D4 - rules-layer reorganisation and the black-box negative gate

Restructure the four Layer-1 operator rule files into explicit A/B/C axes, add the missing operator-lifecycle-ordering rule, and wire a negative conformance gate sourced from the manifest's own service_owner values.

- [x] `P02.S03` - status:done (commit 6e7fc1629) - split Category A behavioural-invariant rules and extract manifest-derived operator-orientation-routing (Category B); `src/aeat/_data/agent/rules/`.
- [x] `P02.S04` - status:done (commit 6e7fc1629) - author the missing operator-lifecycle-ordering rule stating CALCULATE -> VERIFY -> FILE as an invariant; `src/aeat/_data/agent/rules/operator-lifecycle-ordering.md`.
- [x] `P02.S05` - status:done (commit 6e7fc1629) - add the negative conformance gate sourcing its internal-name blocklist from the manifest's own service_owner values; `src/aeat/agent/tests/test_rule_surface_conformance.py`.

### Phase `P03` - D3 - ownership of the export / record-marker handoff boundary

Extend the verifier persona's mandate to own the irreversible export-and-record-marker step, clarifying the accepted parent ADR's underspecified roster boundary.

- [x] `P03.S06` - status:done (commit a0ea7d37e) - extend the verifier persona document to own export and the record-marker handoff; `src/aeat/_data/agent/personas/verifier.md`.

### Phase `P04` - D7 - verifier/preparer context isolation without the Agent SDK

State the verifier context-isolation invariant testably and runtime-agnostically, enforced structurally where the runtime allows and named as degraded trust in its fallback mode.

- [x] `P04.S07` - status:done (commit 436e5c8ca) - state the verifier context-isolation invariant testably and runtime-agnostically, naming the degraded self-report fallback explicitly; `src/aeat/_data/agent/personas/verifier.md`.

### Phase `P05` - D1 - per-persona tool-boundary enforcement mechanism

Declare the runtime manifest-read persona-scoped tool boundary backed by a build-time pinning test, then wire the filter into the live MCP PreToolUse dispatch path so prose and runtime behaviour cannot diverge.

- [x] `P05.S08` - status:done (commit 198e6d6c7) - declare the runtime manifest-read persona-scope filter and its build-time pinning test asserting each persona's (family, mutability) ceiling resolves against the live contract; `src/aeat/entrypoints/mcp/_persona_scope.py`.
- [x] `P05.S09` - status:done (commit 00349c998) - wire the persona-scope filter into the MCP PreToolUse dispatch path so the declared boundary actually gates the tool call, closing the critical dead-code finding; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P05.S10` - status:done (commit 00349c998) - add the end-to-end wiring test exercising a persona's tool boundary through the live dispatch path; `src/aeat/entrypoints/mcp/tests/test_persona_server_wiring.py`.

### Phase `P06` - Assurance spine - golden-eval categories proving the harness faithfully

Build the nine-category golden-eval catalogue (cat 1,3,4,5,7,8,9 landed; 2 and 6 gated on Track-1 #7 and #1) so hallucinated numerics, dropped provenance, and lifecycle contradictions are caught by a standing gate, not self-report.

- [x] `P06.S11` - status:done (pre-existing, commits 2c8020cf5/a375ed6ba/f87fff631) - anchor golden scenarios for modelo 130 and modelo 303 with AEAT numeric value-oracles; `src/aeat/agent/eval/tests/test_modelo_130_golden.py`.
- [x] `P06.S12` - status:done (commit df75c1b63) - category 1 golden scenario asserting verify MUST NOT return verified_complete plus zero findings on positive input with a zero base; `src/aeat/agent/eval/tests/test_under_declaration_golden.py`.
- [x] `P06.S13` - status:done (commit df75c1b63) - category 3 golden scenario dispatching a real modelo.work.calculate call and asserting legal_refs/source_refs on the response payload, not only the registry; `src/aeat/agent/eval/tests/test_response_provenance_golden.py`.
- [x] `P06.S14` - status:done (commit df75c1b63) - category 4 golden scenario asserting a readiness-true versus verify-NO_PENDING_OBLIGATION contradiction triggers stop-and-report, never retry-past; `src/aeat/agent/eval/tests/test_lifecycle_contradiction_golden.py`.
- [x] `P06.S15` - status:done (commit df75c1b63) - category 5 golden scenario requiring an active-profile confirmation before the first mutating verb of a sequence; `src/aeat/agent/eval/tests/test_active_profile_confirmation_golden.py`.
- [x] `P06.S16` - status:done (commit df75c1b63) - category 7 golden scenario asserting a non-zero CLI exit code is read as a verdict payload plus a continuation verb, never an abort; `src/aeat/agent/eval/tests/test_exit_code_verdict_golden.py`.
- [x] `P06.S17` - status:done (commit df75c1b63) - category 8 golden scenario wiring confirmation_for_tool into a run so a CONFIRM-tier step is not auto-approved even with an auto-yes flag; `src/aeat/agent/eval/tests/test_confirmation_gate_golden.py`.
- [x] `P06.S18` - status:done (commit df75c1b63) - category 9 golden scenario wiring faithfulness_check against a real captured calculate JSON, advisory off-handoff and hard-block at export, grounded against the M130 oracle figure to avoid false positives; `src/aeat/agent/eval/tests/test_faithfulness_golden.py`.
- [x] `P06.S19` - status:done (pre-existing) - determinism-replay pinning test confirming byte-identical trajectory replay excluding scenario-declared non-deterministic fields; `src/aeat/agent/eval/tests/test_tool_call_replay.py`.
- [x] `P06.S22` - harden category 3 response provenance so expected computed response rows require formula_id; `src/aeat/agent/eval/_runner.py; src/aeat/agent/eval/tests/test_response_provenance_golden.py`.

### Phase `P07` - D5/D6 - deferred Tier-A and Tier-B skill authoring

Record the explicit deferral of the Tier-A persona-entry itinerary enumeration (gated on Track-1 #7 obligation-coverage) and the remaining Tier-B per-modelo skill matrix (gated on each form's Track-1 surface settling), per the ADR's principle-now/enumerate-later resolution.

- [x] `P07.S20` - status:deferred-gated (blocked on Track-1 #7 obligation-coverage) - enumerate the Tier-A persona-entry itinerary set once the profile-fact predicates it derives from are settled; `src/aeat/_data/agent/skills/`.
- [x] `P07.S21` - status:deferred-gated (blocked on Track-1 per-form surfaces, generally) - author the remaining Tier-B per-modelo completion skills beyond the M130/M303 vertical slice, each authored by diff against the shared lifecycle-spine fragment; `src/aeat/_data/agent/skills/`.

## Description

Retroactive plan for `2026-07-01-agent-harness-adr`, authored after most of
its seven implementation decisions (D1-D7) had already landed, per
`plan-closure-requires-exec-records` and the HIGH finding in
`2026-07-02-agent-harness-content-review-audit` (no plan artifact existed
against which to check completion). This plan does not propose new work; it
maps the seven ADR decisions plus the golden-eval assurance-spine build-out
to their actual landed state as of this authoring pass, so future
`vaultspec-core status` queries and closure gates have a real structural
target. `2026-07-01-agent-harness-research` supplies the completion-roadmap
Phase numbering (Phase 0-8) this plan's Phases are grounded against; each
Phase below corresponds to a subset of that roadmap's Phase 2 (restructure
the surface-independent layers) plus the Phase-4/7-adjacent assurance-spine
work that landed alongside it. Status per Step is recorded honestly: `done`
(committed and verified), `uncommitted-verified` (working-tree change,
independently re-verified green in this pass, pending the coordinator's
apply-cached commit discipline), or `deferred-gated` (explicitly scoped out
pending a named Track-1 dependency, not silently dropped).

## Steps

## Parallelization

Phase `P01` (D2 enum retirement) and Phase `P02` (D4 rules reorg) were
authored and committed independently and share no interdependency; they
landed in parallel in practice. Phase `P03` (D3 export ownership) and Phase
`P04` (D7 verifier isolation) are both prose-only ADR-clarification Phases
with no shared file surface and were likewise independent. Phase `P05` (D1
persona-scoped tool boundary) has two Steps with a hard internal order - the
declaration (committed) must precede the wiring (uncommitted) - since the
wiring Step calls the declaration's exported filter. Phase `P06` (the
assurance-spine golden scenarios) Steps are mutually independent; each
category's golden scenario is its own file with no cross-category
dependency, and all nine were authored in parallel in practice. Phase `P07`
(D5/D6 deferral record) has no executable Steps of its own; it exists to
record the explicit gate rather than to sequence work.

## Verification

The plan is complete when every Step below is closed (`- [x]`). A Step is
closed only when its status is `done` (committed, with the cited commit SHA
resolving in `git log`) or when it is explicitly `deferred-gated` with its
gating dependency named - never on an unverified self-report. Phase `P05`
(commit `00349c998`) and Phase `P06` (commit `df75c1b63`) were landed by the
coordinator via the apply-cached discipline
(`uncommitted-wip-is-not-orphaned`) after this plan's initial authoring, and
each Step now carries a matching exec record under
`.vault/exec/2026-07-02-agent-harness/`
(`2026-07-02-agent-harness-close-audit`,
`plan-ledger-honesty-closed` finding). The two CRITICAL findings in
`2026-07-02-agent-harness-content-review-audit` are cross-referenced, not
duplicated, as Steps here: D1's dead-code finding is the same fact as Phase
`P05`'s wiring Step; the D2/M100 breakage is explicitly NOT a Step in this
plan because its remediation is owned by the `cross-domain-continuity`
campaign, not this one. This plan's own completion never asserts that
hand-off is resolved.
