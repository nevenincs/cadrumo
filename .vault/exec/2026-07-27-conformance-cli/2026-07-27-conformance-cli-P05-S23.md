---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:7c2302d0bc893b4e16ab9df32805b1b86dd1de7fd0bf2e128a141c2401b0307b'
step_id: 'S23'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# run the first real conformance report over the bundled registry and persist the findings as a vault audit document

## Scope

- `.vault/audit`

## Description

- Run the `report` and `coverage` verbs against the validated bundled registry at
  the campaign's own HEAD.
- Persist the reading as a vault audit rather than as a number quoted into a
  summary, so the interpretation lives with the figures.

## Outcome

The tool measured the registry it was built to measure: 73 modelos, 90 revisions,
1261 reconciled casillas, 21 bundled oracle payloads, 15792 label leaves per
locale. The audit records eight readings with their interpretation.

The two that matter most are opposites. Model-law evidence coverage is complete
at 90 of 90 revisions with zero scope diagnostics, and independent checking is
thin at 4.68 percent, with 59 of 1261 reconciled casillas checked against an
outside authority and a further 39 revisions reconciling nothing at all. The
first says the registry's legal grounding is in order. The second says most
reconciliation is the engine agreeing with itself, which is a statement about
coverage of checking and never about correctness.

Governance provenance reads exactly as the design predicted: all 90 revisions
pending review, zero naming an engineer. That is the fail-closed default making
the backlog visible rather than assuming it away.

## Notes

Written by the coordinator rather than an executor, because the deliverable is a
reading of the tool's output rather than a change to the tree.

The figures moved during the campaign's own final hours and the audit says so
rather than presenting them as fixed: independent-check coverage went 0.0460 to
0.0468 as a grounding declaration landed, and unattributed oracle payloads went 1
to 0 as a payload repair landed. Anyone quoting these forward should re-derive
them; the tool recomputes from the loaded registry on every run.

The campaign's own defects are the argument for the thin axis. The prorrata
rounding error and the zero-volume divergence both sat inside the 95 percent that
nothing independently checked, and both surfaced only because a grounding pass
went looking rather than because a gate fired.
