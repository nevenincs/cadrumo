---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8b025f22bd6121e394433edc2b83148275abc5464c7b3c78be429569cdde7963'
step_id: 'S98'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Prove every mandate requirement has authoritative evidence and no work remains

## Scope

- `.vault/plan/2026-08-14-test-harness-sanity-plan.md`

## Description

- Take each of the nine completion criteria the plan's own Verification section
  states, and put current evidence against it rather than a recollection of when
  it was last green.
- Re-measure the criteria that can be re-measured cheaply, in this tree, today.
- Name every criterion that is NOT satisfied, and say what the standing goal
  still asks for that a close would exclude.

## Outcome

**Eight of the nine criteria are satisfied with current evidence. One is not,
and one more is satisfied in substance but not currently reproducible.** The
campaign is therefore complete except for two named items, both recorded below
with their cause, their owner and their remedy. Neither is narrowed to fit.

**1 — census coverage, no unclassified record, no substitutable duplicate.**
Coverage is proven by reading the walk rather than the output: `iter_source_files`
seeds its universe with the repository-root `conftest.py` and REFUSES if it or
any of `src`, `dev`, `packaging` is absent, so the four required trees cannot be
silently dropped. Today: 5601 source files, 499 fixtures, 43 factory-bound, 0
aliased behaviours. The root contributes no fixture rows because it declares no
fixture — an empty result that had to be distinguished from an unscanned root,
and was.

The unclassified and substitutable-duplicate halves are **satisfied in substance
but not reproducible today** — see the deferred items.

**2 — migrated clusters pass real-behaviour tests from each former consumer
subtree plus a collection proof.** Carried by the per-Step records. The last
cluster closed today: 382 tests collect across every changed module with no
fixture-resolution error, and a dev-tree consumer requesting the migrated
`authority` fixture reaches the fixture BODY, which is the wiring proof a
collection count alone does not give.

**3 — root collection applies marker and banned-live-import policy once to every
relevant module.** Carried by the single lane authority under `W07.P24.S99`.

**4 — no-monkeypatch inventory and its discriminating controls pass with no
allowlist, suppression or renamed equivalent. NOT SATISFIED.** See below.

**5 — routine unit execution launches no nested xdist probe or full-corpus
recursive collector; the dedicated harness verdict runs both proofs and fails on
empty membership.** Carried by `W08.P26.S90`.

**6 — owner-specific tests no longer inhabit `src/cadrumo/tests`, and the gate
rejects recurrence by property rather than file allowlist.** Re-run today: 47
passed. The one module added to that directory this session is shared support
consumed from two trees, which is what the directory is for, and the gate agrees.

**7 — focused gates, harness lane, unit and integration recipes and full
first-party collection have current captured outcomes with their exact
verification boundaries.** Carried by `S90`, `S91` and `S95`. `S91`'s boundary is
that both lane comparisons are reported INVALID on stated grounds; that is a
captured outcome, not a missing one.

**8 — fresh-context review finds no unresolved audit item, ownership ambiguity,
lifecycle regression, compatibility bridge or completion-criterion narrowing.**
Carried by `W08.P27.S92`, `S93` and `S94`.

**9 — every checked Step has a matching execution record, the plan validator is
clean, feature-scoped checks pass, repository-wide debt reported separately.**
Re-measured today: 63 checked rows, 63 execution records, zero checked Steps
without one. `vault check all --feature test-harness-sanity` reports **all checks
passed** after this session's two warnings were fixed at source rather than
waived.

## Deferred, with what the goal still asks for

**A — the monkeypatch criterion fails on one live site, and it is not this
campaign's to fix alone.** `domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py`
monkeypatches `bundled_path` at lines 115 and 138. It landed on 2026-08-14 in
commit `6d80634e6b`, mid-campaign and from the registry lane — so it is a
regression against a criterion this plan owns, not pre-existing debt, and it is
recorded as such rather than absorbed silently.

It is reported rather than removed because removing it needs a production change
in another lane's domain. The test exercises the DEFAULT-root branch, and
`_bundled_registry_root` is an `lru_cache` over `bundled_path("registry", "aeat")`
with no injection point, so the only alternatives are editing the shipped
registry tree or adding a production override for the bundled registry root.
Adding that override unilaterally, to satisfy a test-honesty gate, would put a
real root-redirection capability into production on a test's authority. That is
the registry lane's call.

**What the standing goal still asks for:** the criterion says this inventory
passes with no allowlist, suppression or renamed equivalent. It does not
currently pass. Note the shape of the escape that is NOT taken here: the
monkeypatch gate carries no allowlist at all, so the cheap close would be to add
one, and an allowlist added to make a gate green is the gate being switched off.

The other half of this criterion WAS closed today. Two classes landed on
2026-08-13 that the semantic double detector flagged and should not have —
`_RecordingAttachmentStore` and `_RefusingAttachmentStore`, both of which
delegate every call to a concrete `AttachmentStore` and are the opposite of a
stand-in. The existing exemption was a bare set of names; it is now a mapping
where each entry states why its class is real, and the liveness check fails an
entry whose reason is too short to read, whose class has vanished, or whose name
matches no forbidden token. Mutation-proven from outside the repository: the
unmutated table passes and all three failure modes are detected.

**B — the ownership manifest's verdict is real but not reproducible today.** The
generator is fail-closed against a moving source universe and refused twice
this session, naming different peer-edited files each time. The aliasing verdict
above does not depend on it; the unclassified and substitutable-duplicate
verdicts do. `W08.P26.S88` recorded those as zero when generation last
completed, and the committed artefact carries the correct verdict over a stale
inventory of 559 against a live population of 499.

**What the standing goal still asks for:** one clean regeneration in a quiet
tree, after which the artefact's inventory matches the live population. That is
a mechanical step behind an external blocker, not an open question about whether
duplicates exist.

## Notes

**The two deferred items share a cause worth stating once.** Both are the tree
moving under this campaign rather than anything inside it: one is a peer
landing a monkeypatch through a gate this plan owns, the other is peers editing
files while a fail-closed generator tries to photograph them. A campaign running
concurrently with five others cannot hold the tree still, and a close that
reported these as done would be claiming an authority over the tree that this
campaign does not have.

**Method note, because it changed an answer today.** The coverage criterion was
nearly recorded as a gap. The census emits no fixture rows for the repository
root, which reads as an unscanned root; reading `iter_source_files` showed the
root `conftest.py` is not merely included but REQUIRED, and the absence of rows
is the true fact that it declares no fixtures. An empty result cannot tell clean
from unscanned, and only the code settles which one it is.
