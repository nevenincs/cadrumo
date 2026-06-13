---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S60
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P15.S60

## Outcome

Improved the unknown-casilla error path in `_normalise_casilla_key`.

When a bare numeric token matches no casilla in the revision, the error now
lists the available PREFIX segmentos (`Available prefixes for this revision:
DP200014, …`) so the operator knows the qualified key shape for the revision.

New locale keys added via scaffold:
- `cli.app.modelo.work.casilla_bare_numeric_ambiguous`
- `cli.app.modelo.work.casilla_bare_numeric_unknown`

Prose filled for all four locales (en/es/ca/hu). Locale audit: all ok.

## Commit

`c73d60493` — W03.P15.S59+S60: bare-numeric --casilla normalisation + improved unknown-casilla error
