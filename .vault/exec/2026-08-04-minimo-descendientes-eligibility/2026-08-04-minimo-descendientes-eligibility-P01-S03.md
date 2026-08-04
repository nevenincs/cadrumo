---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3ddac04a9c6a36fdedaac4dd8b2caaf9af897addafb7316f6292fd43c8eed8ed'
step_id: 'S03'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Verify every revision 2020-2025 loads with both new parameters resolvable and the legal-grounding gate green

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

## Outcome

Every revision 2020-2025 loads with both parameters resolvable, confirmed independently by
the coordinator: the registry authority builds a 2024 snapshot and both new parameter ids
appear on it.

The executor additionally probed all twelve through the validated read authority rather
than by reading files, and all twelve resolve at their expected values.

Gates: the registry suite passed at 3466. A focused run over the drift-detection, legal
grounding, devengo-anchoring and wheel-bundle gates passed at 23. Formatting and lint clean.

Failure attribution was measured rather than assumed. Three registry-suite failures under
full parallelism cleared on a sequential re-run, matching the project's guidance that
registry failures under parallel pytest are more often a loader-cache race than a
regression. Of sixteen tree-wide failures, exactly one belonged to this Step — a wheel gate
listing the new parameter files as unexpected purely because they were still untracked —
and it passes now that they are committed. The remaining fifteen were traced to peer work
and to the sibling campaign's in-flight files.

Two items carried forward rather than closed here.

First, an audit-trail defect. The executor staged exactly its fourteen files and verified
the index carried no foreign paths, but a peer ran a no-pathspec commit in the window
between the stage and the commit, taking the whole index. All fourteen files landed inside a
commit whose subject describes unrelated adapter work, so they are mis-attributed in
history. Atomicity nonetheless held, all fourteen in one commit, so registry load and suite
collection never split. The executor correctly declined to repair the attribution, since
every remedy is a destructive history rewrite forbidden in this shared worktree. This is the
time-of-check-to-time-of-use hazard the project's commit discipline names: a verified-clean
index does not survive to the commit.

Second, real debt. The drift gate refuses a parameter no consumer reads, and nothing reads
these thresholds until the predicate lands. The executor used the gate's own documented
staging mechanism rather than a skip, recording a rationale and an explicit exit condition
for each of the twelve entries. That exit condition is now written into the consuming Step
so it cannot be forgotten: delete the entries outright if the consumer is visible to the
gate's scan, or re-document each against its real consumer if it lands in the
application-layer injector instead.

Not verified: whether the figures are current beyond the bundled 2025 manual. No live source
was consulted. Both bundled authorities agree and no post-2014 amendment exists in the
consolidated file, so the risk is judged low, but this is reasoned rather than measured.

## Notes
