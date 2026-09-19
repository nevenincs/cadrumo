---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:4391b0c4e99784f188f6f2d3d8b3d141ef8b30845ac19453846700effc3edc4a'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` audit: `S72 Article 161 effect-date repair review`

## Scope

Re-reviewed the W03.P13.S72 legal-effect remediation only: the RDL 20/2012 Article 23 capture and source row, Article 161 source applicability, predecessor and successor fact windows, citations, and the focused boundary tests.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW findings in the remediation scope. The exact RDL capture states the 2012-09-01 legal effect, the older values end on 2012-08-31, and every successor rate cites both the Article 161 wording and the RDL effect authority. The exact August/September boundary test passes.

## Recommendations

Preserve the distinction between a consolidated-redaction wrapper date and an express deferred legal-effect date whenever future temporal facts cite consolidated BOE material.
