---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f0944558da41ebb3f4878ca522ce156d3053ba5d79572a4cd4dbad87f704b699'
step_id: 'S93'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Consolidate the loopback servers, and gate the singularity

## Scope

- `src/cadrumo/llm/tests`
- `src/cadrumo/application/ledger/tests`
- `src/cadrumo/tests`

## Description

- Build the shared home from the plumbing and the two wire envelopes, and deliberately NOT from handler behaviour.
- Migrate in passes rather than one sweep, re-measuring the remaining population before each, because peers land tests hourly.
- Enter the two files an external campaign reserves, rather than deferring them, since deferred work in a reserved path is stranded work.
- Land the singularity gate only once the count outside the home reached zero.
- Absorb the lint debt the migration itself created.

## Outcome

Twenty-one modules now derive from one handler and serve through one context manager. The exclusion set is empty: nothing was left outside with a stated reason, because nothing needed to be.

**The shared home takes plumbing, not behaviour, and that line is the whole design.** These suites differ in ways that are the point of the test — one holds a request open to pin a concurrency ordering, one scripts a status per arrival, one records arrival times to measure pacing, one forwards images. Folding those behind a parameter would put the interesting behaviour where nobody reads it and quietly change what a caller asserts. The two wire envelopes stay separate builders rather than one switching on a mode, because the content sits under different keys in each protocol and a single builder lets a suite assert against the wrong shape while reading as though it chose one.

Three suites keep their bodies local for a sharper reason: they feed deliberately MALFORMED payloads — an empty list, a null models key, a numeric name — to prove a discovery probe returns a typed unavailable rather than raising. A well-formed builder cannot express those, so routing them through one would have silently repaired the exact defect under test.

**The gate is scoped by a positive property and anchored by derivation.** A module is in scope when a non-docstring string literal names an inference wire path or usage counter, so telemetry sinks, media servers, the browser boundary and the docs site fall out by property rather than by exemption — no path is named anywhere. The canonical home is whichever module declares the shared handler, with a rule asserting exactly one does, so a rename re-anchors the gate instead of emptying it. That is the commonest silent death of a gate like this: the home moves, a constant goes stale, and it passes vacuously forever.

Its load-bearing rule is the second one. The first catches a copied handler; the second catches the author who subclasses correctly and then hand-copies the bind-thread-shutdown block beneath it — which is the copy that actually drifted here, leaving differing join timeouts and the same envelope carrying different token counts for no recoverable reason. A gate checking only the class hierarchy would have passed the tree that produced this defect.

**Two anti-vacuity controls ship with it**: one asserting the in-scope set is non-empty, because a scope filter selecting nothing makes every rule pass under every mutation; one proving the detectors still fire, because a gate whose detectors quietly stopped matching looks identical to a clean tree.

**What the consolidation revealed is worth as much as what it did.** A second-level shared home was hiding inside the unmigrated remainder, and two more copies were absent from the audit that scoped the work. A half-closed duplication is harder to spot than an untouched one: a reader who finds the shared home reasonably assumes it is the only one.

**A helper the first pass shipped turned out unusable by its only plausible consumers** — the three malformed-payload suites — and was deleted under its own row rather than left as dead capacity inside a shared home.

**What this excludes.** The home carries no discovery or management verbs. Teaching it those would make it describe protocols it has no business owning, and that was declined rather than deferred.

## Verification

    llm + ledger, unit                1723 passed / 1 failed
    llm + ledger, integration           40 passed / 0 failed
    the two reserved CLI files, integ    2 passed / 0 failed
    ruff over the full path list        "All checks passed!"   exit 0

The one unit failure was a peer's `Notice` model change, routed elsewhere. The two CLI tests failed at first with an unhandled exception reaching the command boundary; that was traced to a live operator-facing crash originating in another campaign's typed-notice-action migration, fixed separately, and the verb now exits 0 where it exited 6.

Lint debt: eighteen naming errors and two nested-context errors, all migration-introduced, all absorbed. The resolution was the override decorator rather than a suppression, because the methods genuinely do override a superclass method — the decorator states a true thing where a suppression silences one.

**The lint count was measured twice over two different scopes, and the wider one is the one this row closed on.** A narrower reading was available that would have closed at zero over the files already fixed, treating the remainder as pre-existing debt the widened scope merely revealed. A census settled it against that reading: all fourteen remaining files subclass the shared handler, and none predates the migration in that shape, so their handlers became visible as overrides for exactly the reason the first seven did. Closing on the narrow form would have been narrowing the completion criterion at the moment the wider one became measurable.

## Notes

The two reserved files were entered through the index rather than deferred. The first attempt's staged-set verification returned two files instead of one — a peer's uncommitted work sitting in the shared index — so the drive was reversed and retried after it cleared. With a poisoned index neither commit shape is safe: a bare commit takes the foreign file, and a pathspec commit takes working-tree content, which after an index-only edit is the stale pre-edit version and would have committed nothing while reporting success.

That verification fired for the first time all session on the most trivial edit in it, a one-line style collapse in a file already finished with. It is worth running precisely when skipping it feels safest.
