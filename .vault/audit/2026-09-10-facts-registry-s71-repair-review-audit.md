---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:933b077732b0400d0e28d33ca54abbb6836dd94463f56a70f808cbceff34f9f5'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` audit: `S71 applicability repair review`

## Scope

Re-reviewed the W03.P13.S71 remediation only: the Article 110 and Modelo 131 selector split, date coordinates, official-instruction provenance, runtime consumer, retirement of the obsolete identity, and focused tests. Excluded concurrent S64/S72 and unrelated worktree changes.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW findings in the remediation scope. The broad Article 110 selector is independently named and includes B05 from its captured legal source; the Modelo 131 selector is separately sourced to the revision-pinned official instructions, excludes B05 and B04, and the ledger passes its filing-period end date for resolution. The obsolete identity has no runtime reader or authored fact.

## Recommendations

Keep future Modelo 131 scope changes behind an explicitly revision-pinned form source and preserve the separate Article 110 selector for the broader legal class.
