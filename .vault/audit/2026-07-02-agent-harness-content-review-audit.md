---
tags:
  - '#audit'
  - '#agent-harness-content-review'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-07-01-agent-harness-adr]]"
  - "[[2026-07-01-agent-harness-research]]"
  - "[[2026-07-02-agent-harness-audit]]"
---

# `agent-harness-content-review` audit: `content honesty review`

## Scope

A fresh-context honesty review of the DAE-80 agent-harness content rollout,
required before the `2026-07-01-agent-harness-adr` restructure decisions
(D1-D7) can be declared structurally complete, per
`aeat-campaign-close-honesty-review`. The review inherited the accepted
parent ADR, the completion-roadmap research, and the git-safety incident
already logged in `2026-07-02-agent-harness-audit` (the `84f84166f`
no-pathspec sweep and its critical post-review correction). It re-verified
every one of the seven decisions against committed HEAD and the working
tree, rather than trusting either the ADR's own "Implementation" narrative
or the earlier campaign self-report. Two CRITICAL-severity findings, one
HIGH, two MEDIUM, and one LOW-accepted-by-design finding are recorded below;
none is closed without either a verification gate or an explicit
hand-off/deferral record, per the closure discipline.

## Findings

### d1-dead-code-now-resolved | critical | the D1 persona-scoped tool boundary shipped as declared-but-unwired at ADR-close time; it is now wired at HEAD (uncommitted, verified green)

D1 (`2026-07-01-agent-harness-adr`, decision D1) chose a runtime manifest
read filtered by the active persona, backed by a build-time-verified pinning
test, over a second codegen'd allowlist artifact. Commit `198e6d6c7`
(`feat(mcp): persona-scoped tool boundary (D1)`) landed the mechanism
(`src/aeat/entrypoints/mcp/_persona_scope.py`) but the initial review found
it constructed and exported without a live call site inside the MCP
`PreToolUse` gate - a mechanism that type-checked and unit-tested in
isolation but never executed on the request path, functionally dead code at
that commit. The gap is now closed in the working tree (uncommitted): the
persona-scope filter is wired into `src/aeat/entrypoints/mcp/_server.py`'s
tool-dispatch path, and `src/aeat/entrypoints/mcp/tests/test_persona_server_wiring.py`
(new, uncommitted) exercises the end-to-end boundary - a persona's declared
`(family, mutability)` ceiling actually gates the tool call, not merely
describes it. Verified green in this review pass. Disposition: **resolved**,
pending commit under the coordinator's no-agent-commit / apply-cached
discipline (`uncommitted-wip-is-not-orphaned`) rather than a further code
change.

### d2-m100-breakage-handed-off | critical | the D2 LIVE_READ retirement's no-pathspec commit (84f84166f) permanently deleted a peer M100 anualidades derivation from history, leaving a live silent-under-declaration defect at committed HEAD

D2 (`2026-07-01-agent-harness-adr`, decision D2) retired the dormant
`LIVE_READ` `OperatorMutability` member as a "pure core-enum cleanup,
proceeds now" surface-independent change. The one-line retirement itself is
correct and landed in `84f84166f`. But the git-safety incident already
logged in `2026-07-02-agent-harness-audit` records that the same commit, via
a no-pathspec `git commit`, swept 35 files of an unrelated
`cross-domain-continuity` peer campaign's staged work into its index - and
that campaign's post-honesty-review correction found the sweep was not
merely an attribution problem. It permanently removed, from history, the
M100 anualidades separate-escala derivation
(`_inject_derived_anualidades_eligibility_facts` in
`src/aeat/application/modelo/_profile_binding.py`, added moments earlier by
peer commit `63f9b6125`) and its unit test
(`src/aeat/application/modelo/tests/test_anualidades_eligibility_derivation.py`),
and stripped `art-64`/`art-75` from the 2024/2025 M100 `renta-cuota-chain`
construct `legal_refs`. At committed HEAD,
`src/aeat/_data/registry/aeat/user_profile/schema.toml` and the M100
2020-2025 registry bindings still reference the deleted
`anualidades_sin_minimo_descendientes_{year}` profile-fact key, so the M100
anualidades regime is a broken derivation chain referencing a function that
no longer exists - a real, live silent-under-declaration-class defect
(LIRPF art. 64/75) at HEAD, not a hypothetical. The restorative fix exists
only in the dirty working tree (uncommitted, unowned by this campaign).
Disposition: **handed off** to the `cross-domain-continuity` campaign per
explicit owner decision recorded in `2026-07-02-agent-harness-audit`'s
correction - this campaign (agent-harness) must not unilaterally re-author
regulated tax logic. This audit re-confirms the hand-off is still the
correct disposition as of this review pass: the working-tree fix has not
yet landed as a `cross-domain-continuity` commit, so the defect remains open
at HEAD and is explicitly NOT this campaign's item to close.

### no-retroactive-plan-artifact | high | the seven D1-D7 decisions landed across five commits plus two uncommitted wiring passes with no plan document ever authored, breaching plan-closure-requires-exec-records in spirit

The `2026-07-01-agent-harness-adr` states in its Implementation section that
"the above is the shape the subsequent implementation plan will structure
into waves, phases, and steps" - but no `.vault/plan/2026-07-01-agent-harness-plan.md`
(or equivalent) was ever scaffolded before execution began. Work proceeded
directly from ADR to commits: D2 (`84f84166f`), D4
(`6e7fc1629`), D3 (`a0ea7d37e`), D7 (`436e5c8ca`), D1-declaration
(`198e6d6c7`), plus the D1-wiring completion and the seven golden-scenario
category files, all uncommitted at review time. `plan-closure-requires-exec-records`
requires a matching exec record (or an explicit deferred-carry-forward note)
before a step counts as complete; with no plan, there are no steps and no
exec records to check against - the campaign's completion state is legible
only by reading commit messages and the working tree, not by an operator
querying plan status. Disposition: **tracked follow-up**, closed by this
review's Recommendations (a retroactive plan document, authored separately
in this same pass, maps the seven decisions to their landed state so future
`vaultspec-core status` queries resolve honestly).

### m347-readiness-vs-verify-scope-gap | medium | the harness content review surfaced a real Track-1-adjacent backend gap: M347 readiness signals and verify-gate scope diverge, echoing the category-4 lifecycle-contradiction failure the golden eval targets

The empirical failure taxonomy in `2026-07-01-agent-harness-research`
(category 4, "wrong lifecycle sequencing / cross-surface contradiction")
names a concrete repro pattern: `modelo readiness: True` from one surface
while `verify` returns `NO_PENDING_OBLIGATION` from another, a contradiction
four testimonial reporters hit. The newly-authored
`test_lifecycle_contradiction_golden.py` (category 4, uncommitted) golden
scenario formalises the stop-and-report assertion for this class generally,
but this review's grounding pass found the M347 (declaración anual de
operaciones con terceras personas) surface specifically has NOT yet been
audited for the same readiness-vs-verify divergence - it is named nowhere in
the golden catalogue's per-category status table
(`2026-07-01-agent-harness-research`, "Golden-eval catalogue" section) and
is absent from the anchor modelos (M130, M303, M100) the eval substrate
currently covers. This is a genuine backend scope gap for Track 1, not an
agent-harness content defect, and it was not previously logged anywhere.
Disposition: **tracked follow-up** - recorded here for the Track-1 backend
hardening backlog (alongside the eight named gap briefs #1-#9) so it does
not fall through the cracks; no golden scenario or registry fix is
authored by this vault-authoring pass.

### filing-record-hyphen-underscore-drift | medium | the filing-record identifier grammar disagrees between the CLI-facing token and the JSON envelope field across the harness's cited surfaces, a real drift the black-box negative gate cannot catch

Distinct from the manifest-verb drift the positive conformance gate
(`test_rule_surface_conformance`) already guards, this review's cross-check
of the operator rules against the live CLI and envelope surface found the
filing "record marker" concept - central to D3's export/record-marker
verifier ownership decision and to the Tier-B lifecycle spine
(`work create -> calculate -> verify -> revision review -> export ->
record marker -> reconcile`) - is spelled with a hyphen in CLI-facing prose
(`record-marker`) but resolves to an underscore-separated field name on the
JSON envelope/notice payload the operator actually reads back. Because the
positive drift gate resolves backticked `aeat ...` command spans and
envelope-spine field names independently, a hyphen-vs-underscore spelling
divergence between a rule's narrative prose (not inside backticks) and the
real field can pass the gate silently while still confusing an operator
agent parsing JSON by field name. This is a real, narrow surface finding for
Track 1 (adjacent to `#1` manifest completeness and `#9` fichero parity),
not a structural defect in the D3 decision itself. Disposition: **tracked
follow-up** - recorded for Track-1 backend hardening; no rule-prose edit is
made by this vault-authoring pass since the fix belongs with whichever
brief owns the envelope field naming.

### lifecycle-rules-prose-only-accepted | low | the CALCULATE -> VERIFY -> FILE ordering invariant is enforced only as rule prose plus golden-eval assertion, never as a runtime CLI-level guard, and this is an accepted design boundary

D4's `operator-lifecycle-ordering` rule (landed in `6e7fc1629`) states the
`CALCULATE -> VERIFY -> FILE` invariant explicitly for the first time, per
the confirmed gap the rules-map design pass found (previously the ordering
lived only in `coordinator.md` prose and the manifest's `LifecycleContract`,
with no Layer-1 rule stating it). This review confirms the rule is prose-only
at the operator-agent layer: the CLI itself does not refuse an out-of-order
`export` call at the process boundary, and enforcement instead relies on
(a) the operator rule instructing the agent never to skip ahead, and (b) the
category-4 golden scenario asserting the agent stops-and-reports on a
detected contradiction rather than retrying past it. This is consistent with
the harness's overall design (rules discipline the agent; the CLI stays a
black box the agent drives, not a state machine the agent is locked out of)
and was an explicit, reasoned choice in the D4 resolution, not an oversight.
Disposition: **accepted by design** - no follow-up action; recorded here
only so a future reviewer does not mistake the prose-only enforcement for an
unnoticed gap.

## Recommendations

- Commit the D1-wiring completion (`_persona_scope.py` call-site integration
  in `_server.py`, plus `test_persona_server_wiring.py`) and the seven
  golden-scenario category files under the coordinator's no-agent-commit /
  apply-cached discipline, verifying the staged set carries zero foreign
  markers immediately before commit (`uncommitted-wip-is-not-orphaned`).
- Do NOT attempt to independently restore the deleted M100 anualidades
  derivation or its test; the correction in `2026-07-02-agent-harness-audit`
  already assigns that remediation to `cross-domain-continuity`. Re-check its
  status at the next agent-harness session start rather than re-diagnosing it.
- Land the retroactive `2026-07-01-agent-harness-plan.md` (authored in this
  same vault-authoring pass) so `vaultspec-core status` and
  `plan-closure-requires-exec-records` have a real structural target to
  check completion against going forward.
- Log the M347 readiness-vs-verify scope gap and the filing-record
  hyphen/underscore drift as backlog items for whichever Track-1 brief next
  touches manifest completeness (`#1`) or fichero parity (`#9`); neither is
  in scope for this vault-authoring pass to fix in code.
- Treat this document, not the earlier campaign self-report inside
  `2026-07-02-agent-harness-audit`, as the authoritative closure gate for the
  D1-D7 ADR decisions: the ADR is not structurally complete until every
  finding above is resolved, handed off, tracked, or accepted, which this
  document now records explicitly.
