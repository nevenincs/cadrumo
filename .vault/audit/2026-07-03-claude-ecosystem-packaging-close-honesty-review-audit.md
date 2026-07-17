---
tags:
  - '#audit'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
  - '[[2026-07-03-claude-ecosystem-packaging-code-review-audit]]'
---

# `claude-ecosystem-packaging` audit: `campaign close honesty review`

## Scope

A fresh-context honesty review of the `claude-ecosystem-packaging` campaign, run per the
`aeat-campaign-close-honesty-review` rule ahead of declaring the campaign structurally
complete. The review re-inherited the campaign from scratch — treating the closure summary
as a third-party report rather than trusted prior work — and re-confirmed all seven code
dimensions the prior code-review audit had already passed clean: storage-root relocation,
the corpus-companion integrity gate plus its anti-tautology proofs, the wheel split's
single-pattern exclusion, the corpus-sources extra, the CRLF re-stamp fix, the MCP CONFIRM
annotation, the plugin and marketplace generator, the publish recipes, and the agent-facing
corpus surface. The verdict at review time was NOT-yet-closeable, carrying one blocker-grade
finding, three deferred minors, and three additional notes.

## Findings

### superseded-harness-r8-no-amendment-marker | high | ADR R8 superseded by the harness refoundation carried no amendment marker, leaving two accepted ADRs asserting contradictory consumer paths — CLOSED at `df51f07937`

The harness-refoundation decision (ADR R8) superseded an earlier accepted ADR's consumer
path, but the earlier ADR carried no cross-reference back to its successor. Two accepted
ADRs stood side by side asserting contradictory consumer paths with nothing pointing a
reader from the superseded one to the superseding one — a genuine blocker for anyone
grounding future work in the ADR trail. Fixed by adding an AMENDED-by Status note to the
superseded ADR plus bidirectional wiki-links between the two records, so the supersession is
now discoverable from either side.

### mcpb-build-docstring-claimed-primacy | low | `packaging/mcpb/build.py` docstring still claimed R8 primacy after the harness refoundation demoted the `.mcpb` path — CLOSED at `df51f07937`

The build script's module docstring described the `.mcpb` bundling path as the primary
distribution mechanism per ADR R8, but the harness refoundation had already demoted that
path to a secondary, legacy-adjacent role behind the plugin and marketplace path. The
docstring now states its demoted-secondary status explicitly, so a reader of the script
itself gets the current picture rather than a stale claim of primacy.

### kickoff-brief-briefed-superseded-mcpb-path | high | The harness-userdocs kickoff brief directed the next campaign onto the superseded `.mcpb` distribution path — CLOSED at `df51f07937`

The kickoff brief prepared for the harness-userdocs follow-on campaign described the
Distribution and connect-a-client sections in terms of the superseded `.mcpb` bundling flow,
which would have briefed the next campaign onto a path this campaign had already demoted.
Both sections are rewritten to describe the plugin, marketplace, and `uvx` path that is now
the actual primary distribution mechanism.

### code-review-minors-tracked-as-deferrals | medium | Code-review minors M2, M3, and M4 are DEFERRED and now tracked as named follow-up items

The prior code-review audit's three non-blocking minor notes are formally tracked as
deferrals rather than left as loose prose: M2 (the library registry-load path discards the
advisory tuple and should carry a short intent note documenting the ADR-sanctioned
design choice), M3 (`_persona_is_read_only` determines persona mode by parsing a
"read-only" prefix out of prose, a fail-open risk if that prose is ever reworded — bounded
by the fact that the real refusal surface is the server-side persona gate), and M4 (the
vestigial `var/*` `PROJECT_ROOT` output-root fields with zero live consumers). None of the
three block closure; each is recorded as a named deferred follow-up item in the session task
list alongside this audit's prose.

### peer-staged-deletion-live-in-shared-index | low | A peer-staged deletion of `test_registry_corpus_companion_guard.py` was live in the shared index at review time — reported, not resolved

At review time the shared git index carried a staged deletion of
`src/aeat/entrypoints/cli/tests/test_registry_corpus_companion_guard.py`, while the file
itself remains committed and intact at HEAD. This is a live shared-worktree hazard, not a
campaign defect: if a peer lands a no-pathspec commit, it would sweep that staged deletion
along with it. The finding is reported for visibility, per the shared-worktree discipline;
it is not this campaign's file to resolve and was left untouched.

### s43-checkbox-reads-stronger-than-artifact | low | `W05.P12.S43`'s checkbox reads stronger than what its artifact can currently prove, by design

Step `W05.P12.S43`'s completion checkbox reads as though the `uvx` server-start link is
fully verified, but the link is genuinely unverifiable until the package's first publish —
this is a structural property of the step, not an oversight. The step's own proof document
discloses this limitation explicitly. The residual verification gap is tracked as an
operator-gated follow-up item rather than left implicit.

### no-single-record-evidences-full-packaging-smoke-chain | low | All packaging-smoke sub-lanes are green, but no single record evidences a full `just packaging-smoke` pass in one run since the gate changed

Each individual packaging-smoke sub-lane (dependencies, split-install, extras, browser,
plugin, marketplace) is independently green, but the gate composition has changed enough
during this campaign that no single execution record captures one complete, unbroken
`just packaging-smoke` run exercising every lane together. This is tracked as part of the
operator-gated follow-up rather than blocking closure, since each constituent lane's
independent evidence is sound.

## Recommendations

- With the blocker-grade finding (superseded ADR amendment marker) fixed and findings 2
  through 4 either closed or formally tracked, the campaign IS structurally complete per the
  `aeat-campaign-close-honesty-review` rule. No further pre-closure work is required.
- Treat `W05.P12.S43`, the remaining `W05` steps `S44` through `S47`, and the package's first
  publish as formally deferred, operator-gated items — they depend on an operator-driven
  publish event this review cannot substitute for — and track them under a named follow-up
  referencing the `RELEASING.md` sequencing.
- Carry the three deferred code-review minors (M2, M3, M4) forward as named, low-priority
  follow-up items; none block closure.
- Leave the peer-staged deletion of `test_registry_corpus_companion_guard.py` for its owning
  peer to resolve; do not act on it from this campaign.
- At the first full `just packaging-smoke` run after this closure, capture one record that
  evidences the complete chain in a single pass, closing the residual gap noted above.
