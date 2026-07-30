---
tags:
  - '#exec'
  - '#scoop-runner-topology'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S04'
related:
  - "[[2026-07-25-scoop-runner-topology-plan]]"
  - "[[2026-07-22-scoop-runner-topology-adr]]"
---

# Record an explicit unaffected-and-why reconciliation against the account-distribution-standard ruling, because this record governs which runner executes the Scoop evidence lane while that record governs where Scoop manifests live, and a reader finding two Scoop decisions with no stated relationship must not have to re-derive the orthogonality

## Scope

- `.vault/adr/2026-07-22-scoop-runner-topology-adr.md`

## Description

- Read both accepted records and identified the axis each decides: this one the execution host of the Scoop evidence lane, the account distribution standard the publication destination of the Scoop manifest.
- Appended a `Reconciliation with the account distribution standard` subsection to the ADR's Consequences section stating the unaffected-and-why relationship in both directions.
- Named the one place the two axes meet, the conjunction of preconditions gating a green `scoop-windows-x86-64` acquisition row, and stated explicitly that it is a conjunction rather than a conflict.

## Outcome

The scoop runner topology ADR now carries an explicit reconciliation. A reader
meeting both Scoop-naming records finds the orthogonality stated rather than
left to be re-derived: neither record supersedes any part of the other, because
changing the publication target does not change which host can run a Scoop
install and changing the runner topology does not move a manifest. The single
downstream meeting point is recorded as a conjunction of two independent
preconditions on the acquisition row.

## Notes

A contradiction was found while reading, outside this Step's scope and left
unmodified. Plan row `S01` directs the operator to switch the shared Docker
daemon into Windows-container mode, while the accepted ADR this plan executes
rejects exactly that option and rules that the daemon stays permanently in
Linux-container mode with the Scoop lane moving to a native Windows self-hosted
runner under a dedicated non-admin user. The plan row and its governing ADR name
different host actions for the same gate, so the operator instruction should be
reconciled to the accepted decision before the row is actioned. Recorded here
rather than corrected because rewriting a peer campaign's operator-gated row is
not in this Step's scope.
