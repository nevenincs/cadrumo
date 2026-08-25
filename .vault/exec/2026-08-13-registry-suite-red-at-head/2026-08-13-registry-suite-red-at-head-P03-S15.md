---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bf1b20eff7dcf34973702ef282c7c103acb967afafa7482f385b23ece4e21904'
step_id: 'S15'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Narrow the Modelo 720 revision 2013-y-siguientes claimed filing years to those its declared layout design covers, or declare the design that covers 2012

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/720/revisions/`

## Description

- Trace the current Modelo 720 source authority and revision selector.
- Verify filing year 2012 resolves to the declared 2013 design revision through
  the production registry authority.

## Outcome

The current source authority explicitly records a 2013 record-design epoch whose
first presentation covers ejercicio 2012. The revision therefore truthfully
starts at filing year 2012 without inventing a separate 2012 layout.

## Notes

- `test_committed_modelo_720_resolves_revision_by_filing_year`: 3 passed.
- The 2012 case resolves `2013-y-siguientes` under
  `orden-hap-72-2013:art-1`.
