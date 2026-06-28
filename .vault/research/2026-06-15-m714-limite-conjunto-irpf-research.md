---
tags:
  - '#research'
  - '#m714-limite-conjunto-irpf'
date: '2026-06-15'
modified: '2026-06-15'
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
