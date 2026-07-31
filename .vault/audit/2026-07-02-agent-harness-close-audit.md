---
tags:
  - '#audit'
  - '#agent-harness-close'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d3def351b36f019f6c6abe11b381cd38a6dca013986382b8c501598b49b682a1'
related:
  - "[[2026-07-02-agent-harness-plan]]"
  - "[[2026-07-02-agent-harness-audit]]"
  - "[[2026-07-02-agent-harness-content-review-audit]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
---

# `agent-harness-close` audit: `epic close honesty review`

## Scope

The mandatory fresh-context honesty review gating the DAE-80 agent-harness
epic before it is declared structurally complete, per
`aeat-campaign-close-honesty-review`. This review inherits and re-confirms
the two prior audits (`2026-07-02-agent-harness-audit`, the git-index-sweep
incident; `2026-07-02-agent-harness-content-review-audit`, the D1-D7 content
honesty review) and re-verifies their dispositions against committed HEAD
rather than trusting either audit's own self-report. It records the final
disposition of every open item: the CRITICAL rules-count CI-breaker found
after the content-review audit landed, the plan-ledger honesty breach this
same vault-authoring pass closes, the MEDIUM/LOW Track-1 follow-ups deferred
pending a peer registry break, and the verified-clean gate set the epic
rests on.

## Findings

### rules-written-ci-breaker-fixed | critical | the stale rules_written==4 assertion breaking the standing agent-harness eval CI gate is fixed at commit 2ef4a27cc

The D4 rules reorg (commit `6e7fc1629`) grew the operator rule set from four
files to seven via `iter_operator_rules()`, but
`test_app_agent_workspace.py` - named directly in
`.github/workflows/agent-harness-eval.yml`'s job command - still asserted
`rules_written == 4`, reddening the standing CI gate on every run after the
reorg landed. Commit `2ef4a27cc` corrects the assertion to `>= 7`, matching
the sibling `>=` assertions already used elsewhere in the same test and the
live `iter_operator_rules()` count. The commit message explicitly
distinguishes this fix from the 34 concurrent eval failures the same run
surfaced (see the `eval-failures-are-a-peer-registry-break` finding below):
the CI-breaker is a one-line stale-count fix, self-contained, and does not
touch the eval substrate. Disposition: **resolved**.

### plan-ledger-honesty-closed | high | the seven P06 golden-scenario Steps and the two P05 wiring Steps now carry exec records and correct checkbox state

`2026-07-02-agent-harness-content-review-audit`'s `no-retroactive-plan-artifact`
finding was closed by authoring `2026-07-02-agent-harness-plan.md` in the
same pass - but that plan itself then drifted from
`plan-closure-requires-exec-records`: Phase `P06` Steps `S12`-`S18` (the
category-1/3/4/5/7/8/9 golden scenarios) were marked `- [x]` citing commit
`df75c1b63` with no matching exec record under
`.vault/exec/2026-07-02-agent-harness/`, and Phase `P05` Steps `S09`/`S10`
(the persona-scope wiring and its end-to-end test) were left `- [ ]` with
status `uncommitted-verified` after the wiring had in fact landed at commit
`00349c998`. This vault-authoring pass: (1) scaffolds one exec record per
Step for `P06.S12` through `P06.S18`, each citing commit `df75c1b63` and the
specific golden-scenario test file it covers, via
`vaultspec-core vault add exec --step`; (2) scaffolds exec records for
`P05.S09` and `P05.S10` citing commit `00349c998`; (3) refreshes `P05.S09`
and `P05.S10` from `uncommitted-verified`/unchecked to `done`/checked via
`vaultspec-core vault plan step edit` and `vault plan step check` - never a
hand-edit of the plan markdown. `vaultspec-core vault check features
--feature agent-harness` and `vault check all --feature agent-harness`
report clean (annotation and markdown-hygiene warnings were fixed via the
CLI's own `--fix` path, scoped to this feature only). Disposition:
**resolved**.

### eval-failures-are-a-peer-registry-break | medium | the 34 concurrent eval failures observed alongside the CI-breaker are a transient peer M100 registry-validation break, not an agent-harness defect

At the same run that surfaced the `rules_written` CI-breaker, 34 eval tests
failed concurrently. Diagnosis (recorded in the `2ef4a27cc` commit message)
traces every one of the 34 failures to a single root cause: the Modelo 100
2024 revision's `renta-2024-profile-minimo-descendientes-estatal` selector
is referenced by a registry binding but not yet declared in the
`user_profile` schema - the same class of registry-validation break the
`2026-07-02-agent-harness-audit` correction already logged as collateral
damage from the `84f84166f` no-pathspec sweep, owned by the
`cross-domain-continuity` campaign, not this one. None of the 34 failures
trace to the golden-scenario harness code (`_models.py`, `_runner.py`, the
seven new category test files) or to the persona-scope wiring; they fail at
registry-snapshot construction before any golden scenario's assertions run.
Disposition: **tracked follow-up, gate-blocked on the peer break** - this
campaign does not own or attempt the M100 schema fix, consistent with the
hand-off boundary `2026-07-02-agent-harness-audit`'s correction already
established for the related D2/M100 anualidades defect.

### m131-m349-tier-b-gap | medium | Tier-B per-modelo completion skills remain absent for Modelo 131 and Modelo 349, tracked as a gate-blocked follow-up

Plan Phase `P07.S21` (D5/D6 deferred Tier-B skill authoring) explicitly
defers "the remaining Tier-B per-modelo completion skills beyond the
M130/M303 vertical slice ... gated on each form's Track-1 surface
settling." M131 (estimación objetiva) and M349 specifically remain
unauthored. This is not a regression introduced by this pass; it is the
same deferral the plan already records, re-confirmed here as still open
and still correctly gated rather than silently dropped. Disposition:
**tracked follow-up, gate-blocked** on each form's Track-1 backend surface
settling, per `P07.S21`'s own gating condition.

### d1-family-granularity-cross-ref | medium | the D1 persona-scope filter's documented family-granularity limitation needs a cross-reference from the Track-1 manifest-completeness backlog, not a code fix

Commit `00349c998`'s message documents that the persona-scope filter
gates at tool-family granularity, not at the finer per-verb granularity a
future manifest revision might want. The limitation is pinned by a test at
landing (per `P05.S10`'s exec record) and is a deliberate, reasoned scope
boundary for this epic - not a defect. What remains open is a cross-link
from this limitation to the Track-1 `#1` manifest-completeness backlog item
so a future finer-grained persona boundary is scoped against the same
tracked item the `m347-readiness-vs-verify-scope-gap` and
`filing-record-hyphen-underscore-drift` findings in
`2026-07-02-agent-harness-content-review-audit` already reference.
Disposition: **tracked follow-up** - no code or rule change in this
vault-authoring pass; recorded so a future Track-1 manifest pass finds the
cross-reference already named.

### m303-expand-tracked | low | the M303 golden-scenario coverage remains scoped to categories 1/3/4/5/7/8/9; categories 2 and 6 stay explicitly gated

The plan's `P06` Phase header already states categories 2 and 6 are
"gated on Track-1 #7 and #1" respectively, and no Step in this plan claims
otherwise. This finding exists only to record that the closure review
checked the claim against the live test directory
(`src/aeat/agent/eval/tests/`) and confirmed no category-2 or category-6
golden scenario file exists yet - the plan's own gating language is
accurate, not aspirational. Disposition: **tracked follow-up, gate-blocked**
on the same Track-1 dependencies the plan already names; no action in this
pass.

### m353-git-reset-safety-incident | low | a git-reset safety incident by an M353-scoped agent was escalated during this epic's execution window, caused no data loss, and the governing rule was strengthened

During the epic's execution window a dispatched agent scoped to M353 work
attempted a destructive git operation (a broad-add-then-reset unstage
pattern) in the shared worktree, in violation of `aeat-git-worktree-safety`.
The incident was caught, escalated to the operator, and no peer work was
lost - the operation was intercepted before it executed against tracked
paths with foreign staged content. The governing rule was strengthened the
same day: commit `a99c35d8f` (`rule(codify): forbid the broad-add-then-reset
unstage pattern`) codifies the specific anti-pattern (`git add -A` /
`git add .` followed by `git reset` to selectively unstage) as an explicit
prohibition, closing the gap the incident exposed in the existing
`aeat-git-worktree-safety` rule's enumerated forbidden-command list.
Disposition: **resolved** - incident contained, no damage, rule
strengthened; recorded here because it occurred inside this epic's
execution window even though the offending agent was M353-scoped, not
agent-harness-scoped.

### verified-clean-gate-set | low | the epic's standing verification surface is confirmed green independent of the items above

The following gates were independently re-confirmed clean by this review
and by the two prior audits it inherits, and are not re-litigated here: the
six drift gates (`test_rule_surface_conformance`,
`test_documented_command_conformance`, `test_json_schema_conformance`, the
API-stub/apidocs conformance, the locale parity gate, and the registry
loader cache-invalidation gate); the 50 eval tests green pre-break (before
the M100 registry-validation break entered the shared worktree); the 41 MCP
tests green at the `00349c998` persona-scope wiring landing; the Tier-A
predicate set (`implies_nonzero` and siblings) exercised by the
under-declaration golden scenario; the honest-gap disclosure the plan's own
`P06`/`P07` Phase headers carry (categories 2/6 and the M131/M349 Tier-B
matrix named as gated, never silently omitted); the D2 sweep (the
`OperatorMutability.LIVE_READ` zero-consumer retirement, `P01.S01`/`S02`);
and D3/D7 (the verifier persona's export/record-marker ownership extension
and its context-isolation invariant, `P03.S06`/`P04.S07`). Disposition:
**verified clean** - listed here as the closure baseline this audit's
CRITICAL/HIGH/MEDIUM findings above are additive to, not a replacement for.

## Recommendations

- Treat this document as the authoritative closure gate for the DAE-80
  agent-harness epic: the epic is structurally complete for its own scope
  now that the CRITICAL CI-breaker is fixed and the HIGH plan-ledger gap is
  closed; the remaining MEDIUM/LOW items are explicitly tracked follow-ups,
  not silent gaps.
- Do NOT attempt the M100 `renta-2024-profile-minimo-descendientes-estatal`
  registry-schema fix from this campaign; it is owned by
  `cross-domain-continuity`, consistent with the hand-off boundary
  `2026-07-02-agent-harness-audit`'s correction already established for the
  related M100 anualidades defect. Re-check its landing status at the next
  agent-harness or cross-domain-continuity session start before re-running
  the full 50-test eval suite.
- Author the M131/M349 Tier-B completion skills and the category-2/6 golden
  scenarios only once their respective Track-1 gating dependencies (`#1`
  manifest completeness, `#7` obligation coverage) settle; do not pre-empt
  the gate.
- When a future Track-1 pass revisits manifest completeness (`#1`), fold in
  both the `d1-family-granularity-cross-ref` finding here and the
  `m347-readiness-vs-verify-scope-gap` /
  `filing-record-hyphen-underscore-drift` findings already recorded in
  `2026-07-02-agent-harness-content-review-audit`, so the three are resolved
  together rather than rediscovered independently.
- No further action is required for the M353 git-reset incident beyond what
  `a99c35d8f` already codified; treat it as closed.
