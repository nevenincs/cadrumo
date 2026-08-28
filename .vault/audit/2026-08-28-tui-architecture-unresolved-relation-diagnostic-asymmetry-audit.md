---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:29074813bfe5fb886bce251506f560bb869ec31cc478b6e96aab1dda1fa688a7'
related: []
---

# `tui-architecture` audit: `An unresolved relation drops its casilla with no diagnostic; the binding path has three`

## Withdrawn

**This audit's central claim was false and is withdrawn in full.** It asserted
that unresolved relations produce no diagnostic at any layer, in contrast to
bindings. Relations are in fact covered by two dedicated diagnostic builders, and
on the dimension this campaign cares about most — watching the over-payment
direction — the relation path is *better* instrumented than the binding path.

Nothing was changed in production code, registry data or tests at any point. The
error was confined to this audit.

## What is actually there

`application/calculations/_relation_prefill.py` partitions unresolved relations
three ways (`_unresolved_relation_ids` → `.formula_fed`, `.orphaned`, `.bound`)
and emits diagnostics for **all three** into
`CalculationSourceResolution.diagnostics`:

```python
diagnostics=_unresolved_relation_diagnostics(unresolved_relation_ids=unresolved_relation_ids, ...)
         + _unresolved_relation_diagnostics(unresolved_relation_ids=unresolved_non_formula_relation_ids, ...)
         + _absent_bound_carry_diagnostics(unresolved_relation_ids=unresolved_bound_relation_ids, ...)
```

The partition also corrects a factual claim carried in the earlier audit. The
formula-fed path drops its casilla, as measured on M180. The **bound** path does
not: an unresolved bound carry threads a **zero** into its target binding slot.
Those are two different mechanisms, and the earlier audit generalised from the one
it had tested.

### The bound-carry advisory is the over-payment watch

`_absent_bound_carry_diagnostics` exists precisely to watch the direction this
campaign was opened to find. Its docstring:

> An orphan reaches nothing; this one reaches a casilla, as a zero, and every
> carry on this path reduces the amount owed — a prior instalment already paid, a
> loss carried forward, an opening stock. So the zero does not look wrong. It
> looks like a taxpayer who had no prior filing, and it declares more tax than is
> owed.

Its message states the fact and the over-declaration consequence outright, and it
is non-blocking. It deliberately does not fire for a filer with no obligation:
those source periods are scoped out upstream against the declared activity start.
It also deliberately omits a "file the source period" instruction, on the reasoning
that the declarations register does not serve every modelo and an instruction an
agent-operator cannot satisfy is worse than none.

That is a direct, documented answer to the organising question — for this channel,
someone built the over-pay watch and wrote down why.

### The orphan advisory is grouped by root cause

`_unresolved_relation_diagnostics` groups by `(source_modelo, filing_year,
periods)` rather than emitting per relation, deliberately excluding
`source_casilla_ids` because that is the axis that varies. Its docstring records
the measurement behind the choice: on Modelo 190 for 2025 with an empty store, ten
annual-summary relations each read a different fact off the **same** absent Modelo
111 return, so the un-grouped form produced ten lines naming one root cause. A true
orphan, having no source coordinate, stays one diagnostic per relation.

## Why the earlier audit missed it

The search that produced the false negative required two terms on the **same
line** — `unresolved` and one of `notice|advisory|diagnostic|finding`. In
`_relation_prefill.py` the function name carries `diagnostics` (line 744) while
`unresolved_relation_ids` sits on the parameter line below it (746). Neither line
satisfies both terms, so a line-scoped conjunction returns nothing while the
function it was looking for sits directly under the cursor.

Two searched files, `_calculation_source_staging.py` and `_source_mesh.py`, did
not contain the coverage; the earlier audit generalised "not here" to "nowhere".
It did hedge — it recorded that an untraced consumer might already surface the
state, and scoped its claim to the staging path — but the headline claim was still
wrong, and the hedge is not a substitute for having looked.

The durable lesson: **a line-scoped grep conjunction is a filter bug generator.**
Grep the terms separately, or grep the file. An absent result from a two-term
same-line filter is not evidence of absence.

## What survives

Nothing actionable. The staging-path observation is true but uninteresting once the
resolver-path coverage is known: diagnostics are produced where the relation is
resolved, which is the correct home for them, not at the staging layer that merely
threads the ids onward. There is no asymmetry to remediate and no gate to add.
