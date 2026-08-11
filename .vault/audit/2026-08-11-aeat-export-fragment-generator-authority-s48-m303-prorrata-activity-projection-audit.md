---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a08dc8fbc0d8456689c8112913496c589034a37081366b33d877c15c3fbb2c18'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S48 M303 prorrata activity projection`

## Scope

Audit the typed row owner, secure persistence, projection-only schema, official
geometry, live refusal path, and absence of parallel scalar authority.

## Findings

### s48-m303-prorrata-activity-projection | low | One typed owner projects exact fixed slots

The encrypted ProrrataRegister remains the sole owner and store. Five immutable
rows project exactly to casillas 500 through 524, including the 2026 CNAE width
change. Direct scalar input, invalid or incomplete rows, duplicates, and excess
rows refuse. No second store, selector, scalar family, formula, binding, export
layout, alias, or legacy path exists.

## Recommendations

Retain projection-only refusal and the withdrawn layout until the later
applicability and complete-layout steps are discharged.
