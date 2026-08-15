---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:fd5c064aedfa259252aae3a949cfcbb477b7da18dc776bb7ae3ee160dadf74c2'
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
and it is formally deferred with a reference rather than carried as a checked
row: `2026-08-15-test-harness-sanity-monkeypatch-criterion-deferral-audit`.**

This record was first written naming TWO open items. The second turned out to
be closable and has been closed; correcting it is the more useful half of this
row and is described under criterion 1.

**1 — census coverage, no unclassified record, no substitutable duplicate.**
Coverage is proven by reading the walk rather than the output: `iter_source_files`
seeds its universe with the repository-root `conftest.py` and REFUSES if it or
any of `src`, `dev`, `packaging` is absent, so the four required trees cannot be
silently dropped. Today: 5601 source files and 0 aliased behaviours; the
manifest's own inventory, generated after the duplicate removals below, is 540
fixtures. The root contributes no fixture rows because it declares no
fixture — an empty result that had to be distinguished from an unscanned root,
and was.

The unclassified and substitutable-duplicate halves are **now satisfied and
reproduced**, and the way they were reached corrects this row's first reading.

They had been recorded as blocked by the generator's fail-closed guard against
a moving tree. That was true and it was not the whole reason. Running the
generator against an immovable snapshot -- `git archive HEAD | tar -x` into a
scratch directory -- turned the refusal into a readable verdict, and the verdict
was that FIVE substitutable duplicate groups existed. The artefact could not
have been written however quiet the tree became. "The tree keeps moving" was a
real obstacle standing in front of a second one nobody had looked behind, and
the first reading of this row stopped at the first obstacle.

Two of the five were introduced by this campaign's own preceding Step: giving
the bundled-authority factory one home closed the aliasing check and opened the
duplication check, because two modules then bound the same factory under the
same name. The other three were pre-existing. All five are closed, each on its
own terms rather than by relaxing anything, and the generator now completes
against the LIVE tree on the first attempt:

    fixture_count = 540   (the committed inventory had claimed 559)
    substitutable_duplicate_count = 0
    retained_divergent_count = 283

The census gate is green at 36 passed, including the completeness and
no-substitutable-duplicate check that had been failing throughout the campaign.

**2 — migrated clusters pass real-behaviour tests from each former consumer
subtree plus a collection proof.** Carried by the per-Step records. The last
cluster closed today: 382 tests collect across every changed module with no
fixture-resolution error, and a dev-tree consumer requesting the migrated
`authority` fixture reaches the fixture BODY, which is the wiring proof a
collection count alone does not give.

**3 — root collection applies marker and banned-live-import policy once to every
relevant module.** Carried by the single lane authority under `W07.P24.S99`.

**4 — no-monkeypatch inventory and its discriminating controls pass with no
allowlist, suppression or renamed equivalent. NOT SATISFIED**, and deferred with
a reference. See below.

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

**The monkeypatch criterion fails on one live site, and it is deferred with a
reference:** `2026-08-15-test-harness-sanity-monkeypatch-criterion-deferral-audit`.
`domain/calculations/registry/tests/test_read_parameter_authority_invalidation.py:115,138`
monkeypatches `bundled_path`. It landed on 2026-08-14 in commit `6d80634e6b`,
mid-campaign and from the registry lane, so it is a regression against a
criterion this plan owns rather than pre-existing debt.

The audit carries the full argument. The load-bearing part, and the part that
changed during this row, is WHY it cannot simply be rewritten against
`read_parameter`'s explicit-root argument. Reading `read_parameter` alone, the
two branches converge on one identical `ValidatedRegistryAuthority.load(...)`
call and the redirection looks gratuitous. They diverge a layer down:
`_loader.py:1224` enables the fingerprint-keyed on-disk compile cache only when
`is_bundled_registry_root(resolved)` holds, so an explicit temp root skips the
very cache the test exists to exercise. A proof through the explicit branch
would prove nothing about the branch production takes.

**What the standing goal still asks for:** the criterion says this inventory
passes with no allowlist, suppression or renamed equivalent. It does not pass.
The gate carries no allowlist at all, so the cheap close is to add one — and a
first allowlist entry created to clear a criterion that names allowlists as the
thing to avoid is the gate being switched off. It stays red.

The other half of this criterion WAS closed. Two classes landed on 2026-08-13
that the semantic double detector flagged and should not have —
`_RecordingAttachmentStore` and `_RefusingAttachmentStore`, both of which
delegate every call to a concrete `AttachmentStore` and are the opposite of a
stand-in. That exemption already existed as a bare set of names; it is now a
mapping where each entry states why its class is real, and the liveness check
fails an entry whose reason is too short to read, whose class has vanished, or
whose name matches no forbidden token. Mutation-proven from outside the
repository: the unmutated table passes and all three failure modes are detected.

An allowlist that records a judgement and an allowlist that launders a failure
are different instruments. The criterion rules out the second; the first was
available for the mock gate and is not available for the monkeypatch gate,
because there is no list there to record a judgement in.

## Notes

**Method note, because it changed this row's answer twice.**

First: the coverage criterion was nearly recorded as a gap. The census emits no
rows for the repository root, which reads as an unscanned root. Reading
`iter_source_files` showed the root `conftest.py` is REQUIRED, not merely
included, and the absence of rows is the true fact that it declares no fixtures.
An empty result cannot tell clean from unscanned, and only the code settles it.

Second, and larger: this row originally closed the ownership-manifest criterion
as blocked, on a true observation — the generator kept refusing because peers
kept editing. The refusal message names the moving files, so it answers the
question "why did this run fail" and silently does not answer "would it succeed
on a still tree". Giving it a tree that could not move answered the second
question, and the answer was five real duplicate groups. A fail-closed guard
firing for a real reason is exactly the shape that stops an investigation one
step early, because there is nothing obviously wrong with where you stopped.

**On the remaining item's cost.** The audit records a second remedy that needs no
production change: run the test in a subprocess against a PYTHONPATH-shadowed
package whose own bundled registry is the temp tree, so `bundled_path` resolves
naturally and the disk cache is genuinely exercised. It is not taken here
because it buys a subprocess test and a package copy in a campaign whose subject
is suite runtime. That trade is stated rather than left implicit, so the lane
that owns it can weigh it rather than rediscover it.
