---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:29d010425a73ebdb955a5251ebcdf6c33e5132cee9d2667fdda90d015f12ad73'
related: []
---

# `tui-architecture` audit: `Cross-modelo relations join by bare casilla id and validate existence, not meaning`

## Finding

Cross-modelo `annual_summary` relations fold a quarterly return into an annual
one by pinning a **bare source casilla id**. Registry validation asserts that the
id *exists* in the source revision and that the periods line up. It never asserts
what the id *means*. The registry already contains a casilla id whose meaning
changed across a renumbering, so the join key is one that has demonstrably moved.

There is **no live defect today**. The finding is that today's correctness is
circumstantial rather than enforced.

## Evidence

The annual informativas do not hand-enumerate their totals. Each total is
`op = copy` over a relation:

```
modelo-190-retenciones-total   op=copy   arg0.relation = modelo-190-rel-111-retenciones-anual
modelo-180-base-total          op=copy   -> modelo-180-115-base-anual
modelo-193-retenciones-total   op=copy   -> modelo-193-123-retenciones-anual
```

Those relations are `kind = annual_summary`, `aggregation.op = SUM`, and each
carries a `source_modelo` plus a literal `source_casilla_id`. M190 folds ten M111
ids (`02`, `05`, `08`, `11`, `14`, `17`, `20`, `23`, `26`, `28`); M180 folds M115
`02` and `03`; M193 folds M123 `06` and `09`.

M123 renumbered for the 2024 design, growing from 8 boxes to 14. Across that
boundary, id `06` does not merely move — it changes meaning:

| M123 revision | `[06]` | `[09]` |
|---|---|---|
| `2019-2023` | `suma_retenciones_regularizacion` | absent |
| `2024-y-siguientes` | `base_rentas_total` | `retenciones_ingresos_a_cuenta` |

So `06` names a retenciones-plus-regularización sum before 2024 and the **base**
total from 2024. M193's earliest revision is 2024 (`snapshot('193', 2023, '0A')`
raises `NoRevisionForPeriodError`), and both the 2024 and `2025-y-siguientes`
revisions fold `06` / `09`, which is correct for M123 2024+. Every live fold is
right.

What makes it right is that no M193 revision exists on the far side of the
renumbering — not a check. `_validate_relation_source_revision`
(`domain/calculations/registry/_validate_relation_sources.py`) resolves the id
through `source_casilla_id_reference_failure` and fails with "has no source
casilla id", then validates source and target periods. The string `semantic_role`
does not appear in that module. Existence and periods are enforced; meaning is
not.

## Direction

Worse than a known direction: **indeterminate**. A mis-joined fold copies whatever
figure sits at the pinned id into the target binding. Folding pre-2024 M123 `06`
into `modelo-193-123-base-anual` would put a retenciones-plus-regularización
figure into a base slot. Whether the resulting return over- or under-declares
depends entirely on the relative magnitudes, so neither the under-declaration
apparatus nor an over-payment watch would reliably catch it, and the value would
look plausible.

This is the same hazard class as the stale `casilla 158` reference recorded in
`[[2026-08-28-tui-architecture-m390-recargo-total-fourth-tier-audit]]`, but
structural rather than prose: there the comment mis-described a correct
computation; here the join key itself is the id.

## Remediation — owner's decision, not taken here

Assert `semantic_role` agreement between the source casilla and the target
binding at registry build, alongside the existing existence and period checks.
This is the campaign's own standing method — *never join on casilla id across
filing years; require `semantic_role` to agree* — expressed as a gate instead of
a discipline.

Two things to settle before implementing, neither adjudicated here:

- The source and target vocabularies are not identical (`retenciones_ingresos_a_cuenta`
  on M123 against a `modelo-193-123-retenciones-anual` binding), so the assertion
  needs a declared correspondence rather than string equality. A relation could
  carry an expected `source_semantic_role` and the validator compare that against
  the loaded source revision — which keeps the authority in registry data.
- Whether existing relations all satisfy such an assertion must be checked before
  the gate is turned on; a gate landed red is a gate someone will weaken.

Per the standing rule, a gate is unproven until it bites: any implementation needs
a deliberate break — repoint one relation at a wrong-semantics id in the source
revision and confirm the build reds — rather than a synthetic fixture.

No production code, registry data or test was changed by this audit.

## Tree-wide sweep: the hazard is latent everywhere, live nowhere

The finding above was raised from one relation pair. It has since been resolved
across the whole tree, and the answer bounds it: **no live mis-join exists.**

Method: enumerate every modelo declaring a `relations/` fragment, load each of its
revisions for filing years 2019-2026, and for each relation resolve the pinned
`source_casilla_id` against the *source* modelo's snapshot **for the same filing
year**, collecting the set of `semantic_role` values that id takes. A relation is
suspect if that set has more than one member, or contains `ABSENT`.

Ten consumer modelos declare relations (100, 180, 190, 193, 200, 202, 296, 303,
390, 714). Thirty-three carry a `source_casilla_id`; the relations on 200 and 202
carry none and are out of scope for this check. Every one of the thirty-three
resolves to exactly **one** `semantic_role` across every year both sides exist.
No divergence, no absent id.

So the M123 `[06]` meaning-change remains the only demonstrated instance of the
hazard, and no relation currently spans it. The audit's conclusion is unchanged
and now measured rather than inferred: today's correctness is real, and it rests
on no relation happening to span a renumbering — not on a check.

### Two joins are already immune, which ranks the risk

The sweep also shows the registry uses two join styles, and only one is exposed:

- **Semantic ids** — M390 folds M303 through `iva.cuota-devengada-total`,
  `iva.cuota-deducible-total`, `iva.resultado-regimen-general`; M100 folds M190
  and M193 through `decl.retenciones-total`; M100 folds M184 through
  `tipo2.renta-atribuible-importe`. These names *are* the semantics, so a
  renumbering cannot silently repoint them. They need no gate.
- **Numeric box ids** — M190 from M111 (`02`, `05`, `08`, `11`, `14`, `17`, `20`,
  `23`, `26`, `28`), M180 from M115 (`02`, `03`), M193 and M100 from M123, M296
  from M216, M100 from M130 and M131, and M714 from M100 (`0435`, `0460`, `0545`,
  `0546`). These are the exposed set, and M714's dependence on four M100 box
  numbers is the largest single exposure, M100 being the most frequently
  renumbered design in the tree.

That is a cheaper remediation than the one proposed above: a gate need only cover
the numeric-id joins, and the semantic-id joins are the pattern to migrate
toward. It is also worth noting that M390 folds M303 by semantic id — the safe
style — while its own annual total hand-enumerates boxes, which is the defect in
`[[2026-08-28-tui-architecture-m390-recargo-total-fourth-tier-audit]]`. The
relation layer is in better shape than the aggregate layer.

### What this sweep cannot see

It compares source and consumer only in years where **both** resolve, so a
meaning-change confined to a year the consumer does not cover is invisible to it —
which is the same circumstantial-safety point the finding makes, not a separate
gap. It also compares `semantic_role` strings, so a role name retained while its
meaning drifted would pass. Neither weakens the negative result for the live tree.
