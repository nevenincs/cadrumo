---
tags:
  - '#adr'
  - '#modelo-verify-nonzero-guards-residuals'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-residuals-research]]"
  - "[[2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
---

# `modelo-verify-nonzero-guards-residuals` adr: `M202 casilla-33 minimum floor and M714 edges stay documented non-guards` | (**status:** `accepted`)

## Problem Statement

The `modelo-verify-nonzero-guards` campaign (closed, 32/32) shipped ADVISORY silent-under-declaration guards for M200/M131/M202/M123/M151/M714/M210 but left three edges as documented non-guards pending prerequisites: M202 casilla 33 (INCN >= EUR 10M pago-fraccionado minimo), and the two M714 edges (base-imponible -> base-liquidable, total-cuota-integra -> cuota-a-ingresar). The `2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit` routed these forward for a grounded guard-or-non-guard decision. This ADR records it. No shipped guard is re-litigated.

## Considerations

- M202 c33 binding provision is now identified: LIS Disposicion Adicional Decimocuarta (23%/25% of resultado positivo PyG, INCN >= EUR 10M), in force 2024/2025, absent from the bundled corpus; c33 legal_refs cite only framework art-40/29/30/105.
- The INCN exists as profile fact `taxpayer.incn_prior_12_months` (binding), but the verify-predicate evaluator receives only casilla_values + text_values -- no binding/profile-fact channel.
- `casilla_equals_implies_nonzero` gates text-equality, not a numeric threshold; INCN is not a casilla.
- c33 IS consumed (clave 34 = max(32, 33)) -- not a dead casilla (contrast the fixed clave-26 case).
- M714 base-liquidable is legitimately zero via art. 28 minimo exento (EUR 700k, CCAA-variable).
- M714 cuota-a-ingresar is legitimately zero via art. 31 limite conjunto floor + art. 32/33 + CCAA bonificacion up to 100% (Madrid/Andalucia).

## Considered options

For each edge: (a) author an `implies_nonzero` ADVISORY now; (b) keep deferred as documented non-guard + canary; (c) build the prerequisite then guard.

- M202 c33: (a) rejected -- no false-positive-free antecedent expressible today; `implies_nonzero(["04","33"])` fires on every sub-EUR-10M filer. (c) is the eventual path (value channel + numeric-threshold operator + on-form base). (b) chosen now.
- M714 base -> base-liquidable: (a) rejected -- fires on every filer below the CCAA-variable minimo exento who files by the EUR 2M gross-assets gate. (b) chosen; (c) = compute base-liquidable with a CCAA minimo-exento table.
- M714 total-cuota -> cuota-a-ingresar: (a) rejected hardest -- fires on the NORM in Madrid/Andalucia (100% bonificacion). (b) chosen; (c) low value (zero stays legitimate even fully modelled).

## Constraints

- ADVISORY-only convention holds; no BLOCKING here.
- c33 grounding must use the live consolidated LIS DA-14a text (STC 78/2020 struck the RDL-2/2016 origin; AEAT applies it for 2024/2025 -- cite consolidated text, per `legal-grounding-verifies-bundled-authoritative-corpus`).
- No production edits beyond the guard-independent c33 legal-grounding correction; the guards themselves stay deferred.
- Guarding any edge needs out-of-scope engine/DSL work (a profile-fact/binding value channel into the predicate evaluator; a numeric-threshold predicate operator; CCAA parameter tables).

## Implementation

Three decisions, all keep-deferred (documented non-guard), each pinned by a canary test citing the research. One guard-independent action for M202 c33: author the DA-14a legal-catalogue entry + consolidated-corpus excerpt and add it to casilla 33 legal_refs (fixes a `registry-calculation-legal-grounding` gap). Record the c33 guard prerequisite stack (binding/profile-fact value channel into the predicate evaluator; a numeric-threshold predicate operator `fact >= literal => nonzero`; an on-form resultado-positivo-ajustado base or acceptance of clave 04 as approximation). Record the M714 prerequisites (a CCAA minimo-exento table for base-liquidable; the full deduccion/bonificacion chain for cuota-a-ingresar).

## Rationale

An advisory that fires on routinely-legitimate zeros trains operators to ignore it (`ledger-iva-advisory-only-on-cuota-bearing-categories`). All three edges have confirmed, common legitimate-zero populations, so a guard would be not just noisy but miseducating -- the honest outcome is keep-deferred with grounded rationale + canary, the M714 precedent this campaign already set. The net-new advance is naming and grounding the DA-14a provision, enabling the c33 legal_refs correction independent of any guard.

## Consequences

- Gains: the c33 legal-grounding gap is identified and fixable now; the guard prerequisites are made concrete; canaries force a re-visit when a prerequisite lands.
- Difficulties: a real c33 guard needs a DSL+plumbing feature plus off-form base modelling; the M714 guards need CCAA-parameter derivations.
- Pitfalls avoided: no falsely-confident advisory on large legitimate-zero populations (Madrid/Andalucia IP filers; sub-minimo-exento patrimonio filers; sub-EUR-10M sociedades).

## Codification candidates

None beyond `no-silent-under-declaration`; these are its deferred-edge worked examples.
