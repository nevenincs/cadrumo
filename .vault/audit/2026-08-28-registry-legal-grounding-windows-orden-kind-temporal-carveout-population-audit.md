---
tags:
  - '#audit'
  - '#registry-legal-grounding-windows'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:4fc6173b6def707d0f392754d9c884a58dbf634f36ff9b12e54a8e73a3b23eff'
related:
  - "[[2026-08-28-registry-legal-grounding-windows-m303-transitional-rate-citation-audit]]"
---

# `registry-legal-grounding-windows` audit: `The orden carve-out holds the modulos coefficients, not just form approvals`

## Scope

## Findings

## Recommendations

## How this was reached

Two corrected recommendations in successive audits shared a cause: a citation's
temporal validity is invisible to a numeric comparison. That produced a general
question — which revisions span a legal handover? — and the sweep found only
**four** instances, all in one revision, modelo 131's `2019-2023`, citing four
annual módulos ordenes each governing one year inside a five-year span.

They load, which is the interesting part.

## Why they load, and what sits in the carve-out

`_legal_window_covers_devengo` applies the strict devengo test only to
`_SUBSTANTIVE_LAW_KINDS`:

> `ley`, `real_decreto`, `real_decreto_legislativo`, `real_decreto_ley`,
> `reglamento`, `directiva`, `acuerdo_internacional`

`orden` is deliberately excluded and gets the presentation-window-tolerant overlap
check instead, for a stated and correct reason: the orden ministerial approving a
modelo form is legitimately published after the tax year closes, and a devengo-only
test would reject every such citation in the tree.

The docstring then warns, in its own words, not to widen or narrow that set
without re-running its severity probe, because "a carve-out here is exactly where
this gate can go quietly vacuous".

This audit adds the population actually sitting in it. Of **437** value-bearing
cited parameters, **417** carry at least one substantive-law reference and are
devengo-tested. **20** rest entirely on `orden`-kind grounding:

| modelo | count | what they are |
|---|---|---|
| 131 | 18 | `modulos-coeficientes-*`, `reduccion-general-*`, `coeficiente-incremento-asalariados-*`, `coeficiente-tramos-asalariados-*`, `indice-exceso-*`, `cuantia-exceso-*` for 2024, 2025 and 2026 |
| 360 | 2 | refund thresholds, already open separately |

## The observation

Those eighteen are not form approvals. They are the coefficients that determine
**rendimiento neto** under estimación objetiva — the índices, the general
reduction, the asalariados increments, the excess thresholds. An Orden HAC/HFP de
módulos is substantive in effect: it fixes the numbers the liability is computed
from, and it does so annually.

So the instruments whose year-to-year correctness matters most are the ones whose
year is never checked against devengo.

## Direction, and the state today

**The pairings are correct at HEAD.** Each parameter is named for its year and
cites that year's orden: the `-2024` rows cite `orden-hfp-1359-2023`, `-2025` cite
`orden-hac-1347-2024`, `-2026` cite `orden-hac-1425-2025`. Nothing is mismatched.

What is absent is enforcement. A `-2026` coefficient citing the 2024 orden would
satisfy the overlap test wherever the windows touch, and a wrong-year coefficient
moves rendimiento neto in whichever direction that year's índices differ — with no
gate to refuse it and no advisory to surface it.

## Not a recommendation to widen the set

The docstring forbids widening `_SUBSTANTIVE_LAW_KINDS` casually, and admitting
`orden` wholesale would reject the form-approval citations the carve-out exists to
protect — it names thirteen such pairs verified in an earlier probe. That is the
two-rules tension again, and this audit reports rather than resolves it.

If an owner wants the coefficients devengo-tested, the shape that avoids the
collision is a distinct kind for a coefficient-setting orden, leaving
form-approval ordenes on the tolerant path. That is a schema change with a
severity probe attached, not an edit.

No production code, registry data or test was changed by this audit.
