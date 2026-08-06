---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:10ba08f70d33cea3d9ab4e216892f2904b5e19d62985d55b82406d8dd2cb4a12'
step_id: 'S205'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Rerun Vaultspec-RAG semantic searches across certificate custody, ledger evidence, export, hashing, replay, namespaces, filed capture, LLM review, registry queries, and duplication infrastructure

## Scope

- `src/cadrumo/`
- `dev/audit/`

## Description

Rerun the semantic searches across certificate custody, ledger evidence, export, hashing,
replay, namespaces, filed capture, LLM review, registry queries and duplication infrastructure.

## Outcome

UNVERIFIED. The instrument is degraded and every result it returned is unusable as evidence.

The index self-reports healthy while being truncated. Status output at run time: `Source code
sections: 466`, code generation 1 `succeeded`, server running. The tracked Python file count is
3982, and the product source tree alone carries 3658. A 466-section index over a 3982-file tree
cannot represent the tree.

All ten concept sweeps were run against the code index. Every one returned a miss. Three results
demonstrate the failure directly rather than merely failing to confirm.

Searching for copy-paste duplication detection returned the CLI profile-duplicate command and did
NOT return the duplication runner, which is the tree's single canonical owner of exactly that
concept and was independently confirmed to exist under S203.

Searching for a file-bytes digest returned a release-readiness module and did NOT return the core
hashing module, which declares both the bytes and the file digest helpers.

Searching for the secure-object namespace registry returned an auth operator test and did NOT
return the namespace registry module.

Two unrelated probes, replay and duplication, returned the SAME file and the same offset, which is
the recognised signature of a partial index answering from a tiny candidate pool.

## Notes

Per the governing instruction the service was NOT restarted and NOT reindexed.

The operational consequence is recorded plainly: for this Phase the semantic instrument can supply
a pointer when it hits but can never support a claim of absence. Every negative in this Phase was
established by exact search and by reading, and is recorded that way under S206.

The deeper hazard is that the degraded index answers confidently. It reports no degradation
reasons, so the mandate to refuse work when semantic discovery is unavailable never fires. That is
a standing instrument defect for the coordinator, independent of this campaign.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-verified 2026-07-28 at HEAD `a4534b8a2bfbf9d9d95eed883f98d2098a437ec0`

Written three days after the sections above, against a tree that has moved. The
figures below supersede any that conflict; nothing above is edited, so the
original measurement stays readable next to what it became.

STILL UNVERIFIED, and the instrument is materially WORSE than when this Step
measured it.

At the time of the original entry the code index reported 466 sections against
3982 tracked files while its generation reported `succeeded`. Re-measured now:
**20 indexed source-code sections**, against 3742 tracked Python files, with
the code generation again reporting `succeeded` and no degraded reason. A
control probe naming the profile-bound write guard returned the same file three
times.

So the failure mode is unchanged and sharper: a truncated index ANSWERS
confidently rather than refusing, which means the discovery mandate's own
refusal never fires - nothing looks wrong from the outside. The self-reported
`succeeded` is worthless as a health signal; only the section count against the
tree size distinguishes a working index from an empty one.

The service was NOT restarted and NOT reindexed. A restart discards an
in-progress index and produces a perpetual reindex, and an interrupted rebuild
truncates what survives. Repairing it is an operator action, and it is the
single named blocker on this Step.

This Step stays OPEN. The semantic sweep it asks for cannot be performed, and
recording it satisfied on a substitute would be exactly the false green this
campaign exists to remove. The structural scan under the sibling Step is a
substitute for the DISCOVERY, not for this Step's own instrument.

## Held OPEN 2026-07-28 by operator direction: instrument withdrawn

HELD OPEN, NOT DEFERRED AND NOT SATISFIED. The semantic sweep this row asks for was never
performed and is not claimed. The operator directed that the RAG dependency be
dropped for this campaign AND that this row stay open, so it is carried as
visibly unfinished rather than closed under a deferral label.

Final measurement of the instrument, taken at close: **0 indexed source-code
sections and 0 vault documents**, with no index generations reported at all.
That is worse than every earlier reading in this record - 466 sections when the
row was first attempted, 20 when it was re-measured hours later, and now none.
The service is not degraded; it is empty.

Nothing was restarted or rebuilt. A restart discards an in-progress index and
produces a perpetual reindex, and an interrupted rebuild truncates what
survives, so repairing it was always an operator action rather than an agent
one. The operator has now ruled it out of scope instead.

WHAT COVERS THE DISCOVERY, and what does not. The sibling swarm row substituted
a structural AST instrument for the discovery half: identifiers normalised to
positional placeholders, strings blanked, docstrings stripped, bodies hashed, so
a concept implemented twice under different names still collides - which is
precisely the duplication a token matcher cannot see. Its discrimination was
proven against a hand-built twin pair and an unrelated control before any result
was trusted, over 1411 production modules and 4250 hashed bodies. That
substitute covered the DISCOVERY. It does not cover THIS row's instrument, and
this record does not pretend otherwise.

The honest residue, stated so the closure cannot be misread: no semantic sweep
across the ten named clusters was completed by this campaign. If a future
campaign repairs the index, this row is the one to rerun, and its ten clusters
are listed above.

Held open at HEAD `90c03889b42a475ddac08693704a37f080350270` on operator direction. The work is unperformed, the row
stays unchecked, and the campaign cannot report itself complete while it does -
which is the accurate state.

## Disposition 2026-07-30: closed as SUPERSEDED, not satisfied

This row closes SUPERSEDED, not satisfied. The semantic sweep across the ten
named clusters was never performed and this record makes no claim otherwise.

Three measurements of the instrument were taken across this row's life, each
worse than the last:

- 2026-07-25 (original attempt): `Source code sections: 466` against 3982
  tracked Python files, code generation reporting `succeeded`. All ten concept
  sweeps ran and missed; two unrelated probes returned the same file and
  offset, the signature of a partial index answering from a tiny candidate
  pool.
- 2026-07-28 (re-verification at HEAD `a4534b8a2`): 20 indexed source-code
  sections against 3742 tracked files, generation still reporting `succeeded`
  with no degraded reason. A control probe returned the same file three times.
- 2026-07-28 (final measurement at close): 0 indexed source-code sections and
  0 vault documents, no index generations reported at all.

The instrument never became trustworthy across any of the three readings, and
its confident self-report at every reading (`succeeded`, no degraded reasons)
means the discovery mandate's own refusal-when-unavailable clause never fired
- the degradation was invisible from the outside at each measurement.

The discovery need this row exists to serve was met by a substitute, not by
this row's own instrument: the sibling Step `W06.P19.S204`'s structural AST
swarm covered the DISCOVERY half over 1411 production modules and 4250 hashed
bodies, its discrimination proven against a hand-built twin pair and an
unrelated control before any result was trusted. That substitute does not
retroactively satisfy this row's semantic-sweep instrument, and this closure
does not claim it does.

The residual work - repairing the RAG index and rerunning the ten named
cluster probes - is carried forward by `2026-07-30-open-work-consolidation-plan`,
not abandoned. This row closes here only because the campaign it belongs to is
closing and the instrument's repair is an operator action outside any
campaign's implementation scope.
