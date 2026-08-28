---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:6f3c6c8f7ccf4a1e040e3e4a26ffddef12051d0bf6c49bc57c08e992e737859a'
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
