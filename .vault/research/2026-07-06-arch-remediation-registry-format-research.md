---
tags:
  - '#research'
  - '#arch-remediation-registry-format'
date: '2026-07-06'
modified: '2026-07-08'
related:
  - "[[2026-07-02-arch-remediation-registry-format-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

# `arch-remediation-registry-format` research: `program-track decision research bridge`

This research bridges the accepted registry-format ADR to the architecture
review and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not change registry files, loader tolerance, or authoring
rules.

## Findings

### Decision input

The architecture review found the registry authoring tree carried both inline
and fragmented revision formats. The loader normalized both, but every future
audit, coverage tool, and parser had to remember both shapes, and the split had
already contributed to wrong parse-only verdicts.

The accepted ADR chose planned convergence to the fragmented layout and deletion
of inline support at zero inline revisions. It rejected both permanent dual
format and migrate-on-touch because both keep the blind-spot class alive.

### Accepted constraints

Each revision migration must be a zero-semantic-drift authoring move: the loaded
`ModeloRevision` must compare equal before and after. Loader tolerance stays
until zero inline revisions; only then may inline branches be deleted and a
fragmented-layout refusal become no-legacy compliant.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
registry-format plan reports 18 of 18 steps closed by `vaultspec-core vault
plan status`. The 2026-07-05 program audit recorded the deferred filing-grade
registry suite cleared with 171 passing tests, and the current ratchet bundle is
green at HEAD.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
registry authoring format changes should preserve the single-format
convergence rule or explicitly supersede the ADR.
