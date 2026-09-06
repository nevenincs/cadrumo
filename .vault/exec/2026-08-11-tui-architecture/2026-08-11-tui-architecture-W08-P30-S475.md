---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:c9cdbcb0ff62183d4633578a7555deade8318e772552ffa926aa00ad793247fe'
step_id: 'S475'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Recover the two documented-command ratchet baselines the import promotion sweep deleted, the third and fourth data file that commit removed while leaving the gates that read them, restoring the docs fence and inline span gates to running against the empty baselines that mean the doctrine is fully applied

## Scope

- `src/cadrumo/entrypoints/cli/tests/aeat_plain_fence_baseline.json`
- `src/cadrumo/entrypoints/cli/tests/inline_aeat_span_baseline.json`

## Changes

`test_documented_command_conformance` passes: 349 tests, where three could not
find the baselines they read.

THE SAME COMMIT AS S470, AND THIS IS THE PATTERN NOW.
`23eadb3884 refactor(imports): close the private-to-public module promotion at
zero` deleted both of these alongside
`dev/docs/tests/unconverted_static_baseline.json`, in every case leaving the
gates that read them in place. Three baseline data files, one import refactor.
The sweep evidently removed data files it judged unreferenced, and a JSON
baseline is referenced by a path constant rather than an import, so nothing it
looked at said otherwise.

Recovered with `git show 23eadb3884^:<path>`, which writes nothing to another
contributor's working tree.

BOTH BASELINES ARE `{}`, AND THAT IS THE POINT. An empty baseline grants no
exemption at all: the gate's own docstring says "an empty baseline means the
doctrine is fully applied". So the recovered files hold the docs at ZERO plain
`aeat` fences and ZERO inline `aeat` spans -- the strictest state the ratchet
can express, and the tree satisfies it. There was no risk here of restoring
stale exemptions, and I checked the content rather than assuming it, because a
non-empty baseline would have been a different decision.

Teeth, two of them, each restored by copy:

* removing a baseline again fails the well-formedness gate -- the defect
  verbatim;
* appending a plain ```` ```aeat ```` fence to `docs/how-to/authenticate-with-aeat.md`
  fails `test_no_new_aeat_plain_fences_in_user_docs`. That second one matters
  more: the first only proves the file is read, while this proves the gate still
  catches the thing it exists for. The doc was restored by copy and `docs/` is
  clean.

## Notes

FOUND BY SWEEPING A SURFACE I HAD NEVER SWEPT. Every failing gate I have worked
in this campaign came from `dev/`; `src/cadrumo` had never been measured. It
yielded eight candidates, four of which reproduced serially. That is the direct
consequence of S470's lesson about generalising "closed or blocked" from the
surfaces I happened to be working.

THE PARALLEL RUN AGAIN OVERSTATED. `test_public_definition_identity` failed
under `-n auto` and passes serially, so the eight candidates were four findings
-- exactly the discipline S473 established, applied before reporting this time
rather than after.

STILL OPEN AND VERIFIED SERIALLY:

* `test_bootstrap_exempt_entries_resolve[app registry]` -- confirmed, not yet
  diagnosed. The obvious next target.
* the two `test_export_split_part_rendering` cases for M200 casillas 00103 and
  00199 -- confirmed in the sweep, and filing-grade, so they need the same care
  as S472.
* the export-tree group stopped in S472 and characterised in S474.
* the three operator decisions -- the 125 `cli.*` extras, the 5 `application.*`
  extras, and the `tui.ledger.reconciliation.direction` spelling.
