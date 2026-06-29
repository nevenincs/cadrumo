---
tags:
  - '#adr'
  - '#m714-limite-conjunto-irpf'
date: '2026-06-15'
modified: '2026-06-29'
related:
  - '[[2026-06-15-m714-limite-conjunto-irpf-research]]'
---

# `m714-limite-conjunto-irpf` adr: `Modelo 714 patrimonio cuota: limite conjunto IRPF+IP (art. 31)` | (**status:** `accepted`)

## Problem Statement

The Modelo 714 (Impuesto sobre el Patrimonio) escala foundation was built this campaign:
casilla 29 (cuota íntegra) is computed from the art. 30 Ley 19/1991 progressive escala
(M714 Phase-B), and casilla 39 carries the art. 31 80%-suelo. The DOWNSTREAM remains
unmodelled: the cuota íntegra (casilla 33) must pass through the LÍMITE CONJUNTO of
art. 31 Ley 19/1991 — the IP cuota plus the IRPF cuotas may not exceed 60% of the sum of
the IRPF bases imponibles — before producing the cuota a ingresar (casilla 55). This is
the deferred M714 downstream item the centralization audit flagged, and it is the canonical
example of a CROSS-MODELO fold-in (M714 needs values from the filer's M100/IRPF).

## Considerations

art. 31 Ley 19/1991 (verified against bundled `ley-19-1991-art-31.html`, entry
`ley-19-1991:art-31` already in the patrimonio legal catalogue):

- the IP cuota íntegra + the IRPF cuotas (íntegra estatal + autonómica, minus certain
  deductions) may not exceed **60%** of the sum of the IRPF bases imponibles (general +
  ahorro), for sujetos por obligación personal;
- the base-del-ahorro part derived from the positive saldo of long-term ganancias
  (held > 1 year) is EXCLUDED from both sides of the comparison;
- a FLOOR applies: when the límite is exceeded, the IP cuota is reduced by the excess, but
  the reduction may not exceed **80%** of the IP cuota íntegra (so at least 20% is always
  paid). This is the art. 31 80%-suelo already carried in casilla 39.

The inputs are cross-modelo: the IRPF cuotas and bases imponibles live on the filer's
M100 for the same `filing_year`. This is precisely a `cross_model_output` relation per the
aggregation-taxonomy (`calculation-source-canonical-mechanism`): one canonical mechanism
per fold-in — a relation feeding the engine's `relation_values` channel, NOT a
`previous_filing` binding (same-year cross-modelo, not a prior-period carry) and NOT a
manual input.

## Constraints

The cross-modelo relation requires the filer's M100 revision to be filed/available for the
same year (the IRPF cuota/base must exist as a resolvable output), so the M714 límite is a
SECOND-PASS computation after the M100 cuota chain. The relation schema/runtime now has the
canonical `cross_model_output` surface needed for same-year fold-ins, but the current M100
registry does not yet expose the art. 31 exclusion-specific values: the base-del-ahorro part
from qualifying long-term patrimonial gains/losses, the corresponding IRPF cuota slice, and
the IP cuota part for assets not susceptible of producing IRPF-taxed income. A formula that
uses only broad M100 base/cuota totals would over-reduce the IP cuota in exclusion cases,
creating under-declaration risk. No external numeric oracle beyond AEAT worked examples
exists; any calc test must be derived from an AEAT/BOE worked example, never hand-computed
from the same formula (`no-tautological-calculation-tests`).

## Implementation

A cross-modelo relation plus a límite formula:

- Declare a `cross_model_output` relation `m714-limite-conjunto-irpf` whose source is the
  M100 same-year cuota/base outputs (IRPF cuotas íntegras + bases imponibles, with the
  long-term-ganancia exclusion projected), materialising a `relation_prefill` slot binding
  on the M714 revision (`relation-slot-bindings-declare-relation-source`: the slot declares
  `source = "relation_prefill"`, never `previous_filing`).
- Author the límite formula on casilla 55:
  `reduccion = max(0, min((cuota_IP + cuota_IRPF) − 0,60 × base_IRPF_computable, 0,80 × cuota_IP_integra))`
  then `casilla_55 = casilla_33 − reduccion`, with the 0,60 / 0,80 coefficients and the
  long-term-ganancia exclusion authored as registry parameters per revision (not Python
  literals), grounded with `legal_refs = ["ley-19-1991:art-31"]`.
- The relation and formula carry full snapshot-workflow application_links and a
  completeness-manifest entry, like the Phase-B escala.

## Rationale

Modelling the fold-in as a relation (not a binding) follows the canonical-mechanism rule:
a same-year cross-modelo value is a relation, exactly the M100←M130 / M353←M322 family.
The 80%-suelo is already grounded (casilla 39), so the límite reuses verified law. Deferring
implementation until the exclusion-specific M100/IP evidence is represented matches the
verify-before-ship discipline — the límite is not legally complete if it folds in only the
broad M100 cuota/base totals.

## Consequences

Gains: completes the M714 cuota chain to the cuota a ingresar, closing the last patrimonio
gap; exercises the cross-modelo relation surface with a real second-modelo consumer.
Difficulties: requires the filer's M100 to be available and computed for the same year
(a filing-ordering dependency); the long-term-ganancia exclusion needs the M100 ganancia
saldo broken out by holding period. Pitfalls: applying the 60% límite without the
long-term-ganancia exclusion over-reduces the IP cuota (a wrong, under-declared result) —
the exclusion is load-bearing, not optional.

## 2026-06-29 currentization

The original authoring-time relation-runtime blocker is obsolete for this gap: current
registry schemas support same-year `cross_model_output` relations. The blocker is now legal
source granularity. The bundled M100 2024/2025 registry exposes broad IRPF bases and cuotas,
but not the art. 31 exclusion slices required by Ley 19/1991: the qualifying long-term
patrimonial gains/losses in the savings base, the corresponding IRPF quota part, and the IP
quota part for non-income-producing assets. Therefore the current safe state is:

- keep casilla 29 (art. 30 cuota íntegra) and casilla 39 (art. 31 80% floor reference) as
  computed and grounded;
- keep casillas 33/40/45/55 manual until those exclusion sources or explicit blocking inputs
  are grounded; and
- reject any partial formula based only on broad M100 totals because it can silently
  under-declare by over-reducing the IP cuota.

## Codification candidates
