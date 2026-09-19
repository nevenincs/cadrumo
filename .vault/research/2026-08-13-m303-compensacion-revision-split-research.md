---
tags:
  - '#research'
  - '#m303-compensacion-revision-split'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8bd846e09f8a621e4358532b4fe540d205a6145fd353db74463c50355dbc675e'
related:
  - "[[2026-08-13-registry-suite-red-at-head-audit]]"
---

# `m303-compensacion-revision-split` research: `M303 compensacion carry across the 2024 revision split`

AEAT split ejercicio 2024 into two Modelo 303 revisions, and the registry followed
in commit `4395a2db04` on 2026-08-10. Since then the relation consistency gate has
reported twelve offences against `modelo-303-rel-self-compensacion-anteriores`,
the *cuotas a compensar de periodos anteriores* carry — the IVA wallet mechanism
that rolls a negative period's credit into the next return.

The question this document grounds is whether that carry is broken. **The evidence
says it is not.** The runtime resolves the carry correctly across the split; the
consistency check does not, because it encodes an assumption the split retired —
one filing year, one revision. The failing gate is reporting on its own stale
model rather than on the registry.

**This is not an all-clear, and should not be read as one.** Two of the three
claims here are now observed rather than inferred: a probe confirms every link of
the carry chain resolves to exactly one revision, and code tracing confirms no
fold consumer pins a source revision. But the remaining gap is the one that
matters most — **no test drives a real 2024 2T credit across the boundary into a
3T return and checks the resulting figure**, and none exists to be pointed at.
What this document establishes is that the reported offences do not evidence a
broken carry, that the check which raised them cannot express a split year, and
that revision resolution is unambiguous at every link. It does **not** establish
that the compensación is computed correctly — only that this particular alarm is
not the reason to think otherwise. The one surviving limit is under "What was not
established" and is load-bearing, not boilerplate.

This matters beyond the one gate. The first pass of the companion audit read the
check's error text as a description of a production defect and recorded an
over-payment risk against real filings. That verdict was wrong and is corrected
there. What the ADR must settle is narrower than "fix the carry": it is how the
consistency check should express a filing year that carries more than one
revision. The related worry — that some *other* consumer of relation fold
requirements might still assume one revision per year — was investigated and
closed; none does, and the correct pattern already exists in the tree, as recorded
below.

## Findings

### The runtime carry resolves across the split, because it never names a revision

The fold requirement is keyed by modelo, year and period — not by revision id.
`relation_source_requirements` at
`src/cadrumo/domain/calculations/registry/_relations.py:134` calls
`_derive_offset_source_anchor`, keeps the returned `period_year_delta`, adds it to
the source year at `_relations.py:139`, and emits a `RegistryFoldRequirement`
carrying `(source_modelo, source_year, source_periods, source_casilla_id, ...)`.

The consumer resolves observations from that triple.
`_gather_observations_for_snapshot` at
`src/cadrumo/application/calculations/_relation_prefill.py:144` iterates
`requirement.periods`, builds `Period.from_year_and_code(requirement.filing_year,
period)`, and pulls the stored casilla observations for that modelo, year and
period. Which revision half produced the source period never enters the lookup.

So for a 3T target, the runtime asks for M303 2024 2T observations. Those exist
regardless of whether `2024-hasta-08-y-2t` or `2024-desde-09-y-3t` produced them,
and revision resolution stays law-determined per period, which is what the
standing registry-authority rule requires. The 2T→3T carry across the split
resolves. The 1T target, whose prior quarter is the previous year's 4T, resolves
too, because the runtime applied the year delta.

### The check fails on two faults, neither of which the runtime shares

**It discards the year.** `apply_period_offset` at
`src/cadrumo/domain/calculations/registry/_period_offset_math.py:28` returns
`(year_delta, derived_period)` and documents the delta as "negative = prior year";
for 1T at offset -1 it yields `(-1, "4T")`. `_derive_offset_source_anchor` at
`_relations.py:344` preserves that pair, but the convenience wrapper
`_derive_offset_source_period` at `_relations.py:339` returns `anchor[1]` and drops
the delta. `test_relation_consistency.py:123` calls the wrapper. The check
therefore hunts for 1T's prior quarter inside filing year 2024 and reports
`['4T'] not accepted by 303/2024-hasta-08-y-2t` for a source that correctly lives
in 2023.

**Its period assertion is unsatisfiable for a split year.**
`_relation_consistency_errors` at `test_relation_consistency.py:51` gathers
*every* revision matching the selector — for `filing_year_delta = 0` against 2024,
both halves — and then `_offset_derived_period_errors` requires each candidate
revision, taken alone, to accept every derived period.
`2024-hasta-08-y-2t` accepts `{1T, 2T}` and `2024-desde-09-y-3t` accepts
`{3T, 4T}`, so any relation spanning the year fails against both by construction.
This is what produces the offences attributed to 2023, 2025, 2026-y-siguientes and
2009-y-siguientes as well: their `filing_year_delta` now lands on a year holding
two revisions, and each is checked independently.

The two faults compound, which is why the error text reads so convincingly like a
registry defect: it names real revision ids and real period codes, and every
individual clause is true of the check's model.

### The registry fragments are not obviously wrong

Both halves declare the same relation shape —
`source_period_offset_from_target = -1`, `source_revision_selector.filing_year_delta = 0`,
`period_alignment.mode = "previous_quarter"`, `aggregation.op = "copy"` — at
`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/relations/0001-relations.toml`
and its `2024-desde-09-y-3t` sibling, differing only in `target_periods`
(`["1T", "2T"]` and `["3T", "4T"]`) and `source_refs`.

`RelationRevisionSelector` at
`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:602` offers `year`,
`year_from`, `year_to` and `filing_year_delta`, and its validator refuses mixing
absolute bounds with a delta. There is indeed no axis naming a sibling revision
within a year. The first pass treated that as the defect. On the runtime evidence
above it is not one: because the fold never resolves a revision, the selector only
ever needs to identify a source *year*, and `filing_year_delta = 0` does that
correctly. The missing axis is a real expressiveness limit, but nothing in the
carry currently needs it.

### No fold consumer pins a source revision, so the concern cannot resurface elsewhere

This was carried as open in the first draft and is now closed. All three
`RegistryFoldRequirement` consumers address their source the same way — modelo,
year and period — and none resolves a source revision.

`_requirements_from_relation` and `_requirements_from_previous_filing` at
`src/cadrumo/application/calculations/_cross_period_clean_state.py:592` and `:578`
each build `Period.from_year_and_code(requirement.filing_year, period)` and emit a
`CrossPeriodDependencyRequirement` keyed by `(source_modelo, filing_year, period)`.
`_requirement_strictly_before_activity_start` at
`src/cadrumo/application/calculations/_binding_prefill.py:623` uses the same
construction, and only to compare date spans. No revision id appears on the source
side of any of the three paths.

The one place a `revision_id` *is* passed —
`_cross_period_clean_state.py:176` — is the **target** side of an inventory walk,
not a fold source, and it is worth reading because it is the correct handling of a
split year and a working model for the check repair. It iterates
`modelo.revisions.values()`, keeps each revision whose `period_selector` includes
the filing year, and then enumerates **that revision's own**
`period_selector.periods` (`:167-171`), passing `revision_id` to
`authority.snapshot(...)` alongside the law-determined triple as an assertion
rather than a selector — the shape the standing registry-authority rule requires.
Because each revision is only ever paired with the periods it declares, the
assertion always agrees, and a two-revision year is handled without special
casing.

That is precisely what the failing consistency check does not do: it pairs *every*
candidate revision with the *union* of derived periods and demands each accept all
of them. The correct pattern already exists in the tree, one package over.

### The stamp re-confirmation resolves one unambiguous revision at every link, observed not inferred

This was the last limit that could have turned the clean bill back into a real
defect, and it is now closed by observation rather than by reading the code. The
failure mode it guarded against was specific: if `revision_carry_outcome` could
not re-confirm a 2T source stamp, the carry would be silently **dropped** rather
than mis-valued.

The re-confirmation resolves purely from the law-determined triple.
`revision_carry_outcome` at
`src/cadrumo/application/calculations/_revision_carry_gate.py:45` calls
`authority.snapshot(source_modelo, filing_year=..., period=...)` at `:77` with **no
`revision_id` argument**, then refuses on indeterminate resolution or a divergent
stamp and passes a matching one. So the whole question reduces to whether that
resolution is unique per source context.

A read-only probe against the bundled authority resolved every link of the
compensación chain. `2024` `1T` and `2T` resolve to `2024-hasta-08-y-2t`; `3T` and
`4T` resolve to `2024-desde-09-y-3t`; `2023` `4T` resolves to `2023` and `2025`
`1T` to `2025`. Laid out as the carry actually walks it, target against
law-resolved source:

- 2024 1T (`2024-hasta-08-y-2t`) ← 2023 4T (`2023`)
- 2024 2T (`2024-hasta-08-y-2t`) ← 2024 1T (`2024-hasta-08-y-2t`)
- **2024 3T (`2024-desde-09-y-3t`) ← 2024 2T (`2024-hasta-08-y-2t`)**
- 2024 4T (`2024-desde-09-y-3t`) ← 2024 3T (`2024-desde-09-y-3t`)
- 2025 1T (`2025`) ← 2024 4T (`2024-desde-09-y-3t`)

Every link lands on exactly one revision, including the bolded 2T→3T sibling
crossing that the retracted verdict claimed could not resolve, and both year
boundaries. Since a producer stamps from the law-selected snapshot it already
holds, and that selection is unique, a 2T observation is stamped
`2024-hasta-08-y-2t` and re-confirms to `2024-hasta-08-y-2t`. The stamp matches
and the carry proceeds.

One honest edge, with no present consequence: an observation persisted *before*
commit `4395a2db04` would carry the retired pre-split revision id, which would now
diverge and be refused on carry. Under the project's pre-release data posture
nothing released wrote such a record, so this is noted for completeness rather
than as a live risk.

### What was not established

One thing remains open.

*(One item formerly listed here — whether the stamp re-confirmation selects the
right half — has since been closed by observation and moved to its own section
below.)*

Whether the runtime carry actually produces the right number end to end. Nothing
here ran a 2024 2T→3T compensación through calculate; the argument is structural,
from the code path. A regression driving a real credit across the boundary is what
would settle it, and none exists.

### Nothing in this suite was made to pass by moving an expectation

Worth stating plainly, because it is the difference between two very different
situations and it is easy to lose inside a 157-failure count. Across every cluster
examined — this relation check, the M100 maternidad binding, the IVA deduction
authority and selector tightenings, the M232 and M390 export-layout gaps — **no
test expectation was altered to match what the engine computes.** The failures are
gates that stopped agreeing with the code and were left red, not gates that were
quietly re-pointed at the code's current answer.

That matters for how much the remaining red can be trusted. The project's standing
prohibition on moving an expectation to meet the engine was not violated here, so
the failing assertions still encode what someone believed correct at authoring
time. This is the "we broke something and noticed" case, not the "we broke
something and hid it" case. The distinction survives the correction recorded above:
even where the check turned out to be the stale party, it was stale *honestly* —
it kept asserting its original model rather than being bent to agree with the new
one.

### The 2018 split is a different problem and should not ride this one

The audit's first pass suggested ruling once for 2024 and 2018 together. The
evidence separates them. `test_revision_span_matches_published_designs.py` reports
`2018 should carry two distinct Modelo 303 designs (AEAT split it mid-course) but
0 distinct payload(s) survived enumeration`, and separately `2015 is covered by a
bundled design but attributed to nothing`. Those are registry **coverage** gaps —
published AEAT designs with no revision modelling them — whereas the 2024 finding
is a **check** defect against a split the registry already models. Folding them
into one decision would attach a data-authoring task to a test fix and let the
larger one hide the smaller.

## Sources

`src/cadrumo/domain/calculations/registry/_relations.py:134`,
`_relations.py:139`, `_relations.py:339`, `_relations.py:344`

`src/cadrumo/domain/calculations/registry/_period_offset_math.py:28`

`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:602`,
`_schema_surfaces.py:698`

`src/cadrumo/domain/calculations/registry/tests/test_relation_consistency.py:51`,
`test_relation_consistency.py:123`, `test_relation_consistency.py:156`

`src/cadrumo/application/calculations/_relation_prefill.py:144`,
`_relation_prefill.py:145`, `_relation_prefill.py:157`

`src/cadrumo/application/calculations/_binding_prefill.py:623`,
`_cross_period_clean_state.py:167-171`, `_cross_period_clean_state.py:176`,
`_cross_period_clean_state.py:578`, `_cross_period_clean_state.py:592`

`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/relations/0001-relations.toml`
and the `2024-desde-09-y-3t` sibling fragment

Commit `4395a2db04` (2026-08-10), which introduced the split revisions

`src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`
for the 2015 and 2018 coverage gaps

`src/cadrumo/application/calculations/_revision_carry_gate.py:45`,
`_revision_carry_gate.py:77`

Revision-resolution probe: read-only, run against `bundled_authority()` on
2026-08-13 at commit `3241d5a173`, resolving `snapshot('303', filing_year, period)`
for 2023 4T, 2024 1T-4T and 2025 1T. Results reproduced in full in the
stamp-re-confirmation section above. The probe wrote nothing and is reproducible
from the four values it prints.

Unverified, and named as open above: the **end-to-end numeric behaviour** of the
carry across the 2024 boundary. One regression driving a real credit from a 2024
2T negative settlement into the 3T return would settle it; none exists today.
