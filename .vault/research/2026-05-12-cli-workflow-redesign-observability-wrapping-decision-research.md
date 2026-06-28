---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `observability-wrapping-decision`

## Findings

`entrypoints/cli/_observability.py` exports `build_arguments()` and
`cli_run_context()`, but there are no production call sites. Adopting them now
would expand the root UX and event model during a redesign that is trying to
narrow command surfaces.

Bucket event history already owns material state-transition audit. Evidence
bundle replay owns evidence-case replay. Generic CLI observability traces would
create a parallel audit vocabulary without a product decision.

Target decision: retire CLI observability wrapping from this redesign. Reject
opportunistically wrapping every command, exposing run or replay ids as root UX,
and mixing observability traces with evidence-bundle replay.
