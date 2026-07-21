---
tags:
  - '#research'
  - '#m714-limite-conjunto-irpf'
date: '2026-06-15'
modified: '2026-06-29'
related:
  - '[[2026-06-15-m714-limite-conjunto-irpf-adr]]'
---

# `m714-limite-conjunto-irpf` research: investigation backing the decision

This research captures the investigation that backed the `m714-limite-conjunto-irpf` ADR.

## Findings

The Modelo 714 (Impuesto sobre el Patrimonio) escala foundation was built this campaign:
casilla `29` (cuota íntegra) from the art. 30 Ley 19/1991 progressive escala, and
casilla `39` carrying the art. 31 80%-suelo. The downstream remained unmodelled: the
cuota íntegra (casilla `33`) must pass through the LÍMITE CONJUNTO of art. 31 Ley
19/1991 — the IP cuota plus the IRPF cuotas may not exceed 60% of the sum of the IRPF
bases imponibles — before producing the cuota a ingresar (casilla `55`).

This is the canonical example of a CROSS-MODELO fold-in: M714 needs values from the
filer's M100/IRPF return. The art. 31 rule was verified against the bundled
`ley-19-1991-art-31.html` (`ley-19-1991:art-31`, already in the patrimonio legal
catalogue). The investigation concluded the límite conjunto must be modelled as a
relation feeding the engine, not a manual input.

2026-06-29 currentization: the relation surface is no longer the blocker; current registry
schemas already carry same-year `cross_model_output` relations. The blocker is the legal
source granularity needed to avoid under-declaration. Ley 19/1991 art. 31 does not use the
broad IRPF totals alone: it excludes the savings-base part from qualifying long-term
patrimonial gains/losses, excludes the corresponding IRPF quota slice, and excludes the IP
quota part for assets not susceptible of producing IRPF-taxed income. The M100 2024/2025
registry exposes broad bases and cuotas, but not those exclusion-specific slices. The current
safe implementation remains: compute M714 casilla `29` and casilla `39`, keep the downstream
joint-limit casillas manual, and require the exclusion sources or explicit blocking inputs
before adding a casilla `55` formula.
