---
tags:
  - '#adr'
  - '#m714-limite-conjunto-irpf'
date: '2026-06-15'
modified: '2026-06-15'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace m714-limite-conjunto-irpf with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, or deprecated. A new ADR starts as proposed; it moves to
     accepted or rejected when the decision is made, and to deprecated
     when a later ADR supersedes it.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

Parent-feature stability: BLOCKED at authoring time by the in-flight peer
`bindings-interface-hardening` refactor (`BindingAggregationOp`) that has the registry in a
non-loading state — the relation-prefill resolver and the calculate mesh are the exact
surface being refactored, so neither the relation nor its formula can be added or
gate-verified until that lands. The cross-modelo relation also requires the filer's M100
revision to be filed/available for the same year (the IRPF cuota/base must exist as a
resolvable output), so the M714 límite is a SECOND-PASS computation after the M100 cuota
chain — and the M100 cuota chain itself was only just grounded this campaign
(`gravamenes_res` per-box). No external numeric oracle beyond AEAT worked examples exists;
any calc test must be derived from an AEAT/BOE worked example, never hand-computed from the
same formula (`no-tautological-calculation-tests`).

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
implementation behind the engine refactor and the M100 cuota availability matches the
verify-before-ship discipline — the límite is meaningless until the M100 cuota it folds in
is itself computed and the relation surface is stable.

## Consequences

Gains: completes the M714 cuota chain to the cuota a ingresar, closing the last patrimonio
gap; exercises the cross-modelo relation surface with a real second-modelo consumer.
Difficulties: requires the filer's M100 to be available and computed for the same year
(a filing-ordering dependency); the long-term-ganancia exclusion needs the M100 ganancia
saldo broken out by holding period. Pitfalls: applying the 60% límite without the
long-term-ganancia exclusion over-reduces the IP cuota (a wrong, under-declared result) —
the exclusion is load-bearing, not optional.

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

<!-- Example:

- **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
