---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S22'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# run the full-tree collect-only gate and the scoped registry, filing, and dev suites, recording failure signatures and triaging owner vs peer churn

## Scope

- `src/cadrumo`

## Description

- Run the full-tree collect-only gate and confirm clean collection.
- Run the scoped suites over every tree this campaign touched.
- Triage each failure to its owner rather than reporting a count.
- Absorb every failure this campaign caused, and attribute the rest.

## Outcome

Full-tree collection is clean: 15015 tests collected of 18353, 3338 deselected by
marker, zero collection errors. That is the signal that matters most in a shared
worktree, because a broken import at HEAD blocks every concurrent campaign rather
than only this one.

Sixteen failures across the scoped suites triaged into three groups. Seven were
not real: four error-registry assertions and the loader cache-isolation test, each
of which passes in isolation (28 passed and 11 passed respectively). Those were
peers committing registry sources during a thirteen-minute parallel run, and the
cache key folds those bytes, so the race is structural rather than a defect.

Five were this campaign's own and were absorbed rather than deferred: a module
marker declared after a constant, a bare encoding literal, two modules that broke
their size ceilings, and a docstring citing a development record. The size
breaches were fixed by extraction, not by lifting a ceiling.

Four were peer-owned and were fixed anyway on an explicit operator directive to
clear all substitution machinery from the tree: two monkeypatch sites, a pair of
fake-named bindings that turned out to be a positive control needing only a
rename, and an import-hygiene ratchet that needed no new debt because a public
facade already exposed what the import wanted.

## Notes

One failure remains and is genuinely another campaign's: a module marker declared
after an assignment in a docs-sequences test. It is a one-line move available to
its owner.

**Correction.** This record originally closed the sentence above with "and this
campaign's half of that gate is clear." That was false when written. The
repository-wide privacy lint was red at the time on eight lines of this
campaign's own conformance CLI test module, which carried the operator's real
name in tracked source — introduced by this campaign's commit and carried
forward by four later ones. It is owner-caused, it was not among the five
regressions this record enumerates as absorbed, and it reds the per-push lane
rather than a manual one, so it was the most consequential failure outstanding
and the record named none of it.

The reason the triage missed it is structural and worth stating rather than
excusing. The scoped suites were selected by the trees this campaign EDITED. The
privacy gate does not live in any of them; it lives in the quality tree and
scans the whole repository, so a gate reddened by this campaign's edits but
resident elsewhere fell outside the selection entirely. The full-tree gate that
did run was collect-only, which imports every module and asserts nothing, so it
could not see an assertion failure either. Between the two, a tree-wide gate
that reads a file you changed has no route into a triage keyed on where you
changed it.

The leak was found later by the campaign-close honesty review and is closed
under a separate Step.

A methodological error worth recording. The first capture piped pytest through
`tail` before the background file was written, so the log carried only the summary
lines and every failure body was lost. Attribution then required re-running the
unattributed tests individually. Truncating before the write, rather than after,
destroys exactly the diagnostic the run was for.

The triage itself is the point of this Step rather than the count. Two of the
groups look identical in a summary line, and only re-running in isolation
distinguishes a peer's mid-run commit from a real regression.
