---
tags:
  - '#reference'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:497e49114a33c80110762f8994d2469f70aa18e8c86cea98923fe4eaa86c1c18'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# `canonical-identifiers` reference: revision_id adjudication

Grounding for `W05.P07.S35` and `W05.P07.S36`. Produced 2026-08-11. **No code was
changed.** The row asked for twelve sites in one file; this is the measured population and
its per-concept classification, so the scheduling decision can be made against class sizes
rather than an assumed denominator.

## Why the row could not be executed as scoped

`W05.P07.S35` reads "the twelve bare `revision_id` sites" and scopes itself to a single
registry module. Measured at HEAD:

| measurement | value |
|---|---|
| annotated `revision_id` sites, production `src/` | **308** across 115 files |
| bare `str` | **130** |
| `str \| None` | 85 |
| already `CalculationRevisionId` | 24 (+16 optional) |
| already `RevisionId` | 16 |
| the row's named file holds | **1** of the 130 |

Instrument: AST over `git show HEAD:<path>` bytes - parameter annotations and annotated
assignments, tests excluded. Reading the object store rather than the working tree matters
here because the tree carries a large uncommitted registry migration.

**The 85 `str | None` sites are the declared unmeasured remainder.** They are not classified
below and no claim is made about them. Naming them is deliberate: a population defined only
by what was convenient to measure cannot converge.

## The finding that makes this an adjudication rather than a sweep

Three different concepts wear the name `revision_id`:

- the **hex-64 calculation revision** - a content-addressed id of a calculation this system produced
- the **registry revision slug** - a law-determined tag such as `2019-y-siguientes`, published by AEAT orden
- the **law-determined stamp** - the registry revision a source filing resolved to at capture time, which carry-read code re-confirms before trusting a value

That is the campaign's standing goal appearing in the **type layer** rather than the module
layer: one name, three referents. A mechanical retype would silently constrain the two
concepts it does not fit.

## Substitutability, measured before any verdict

`RevisionId` carries `min_length=1`, `max_length=128` and a lowercase ref pattern where a
bare `str` carries none, **so every retype NARROWS its site.** A narrowing is only safe if
the real population satisfies the new constraint, so that was measured rather than assumed:

```
distinct revision ids in the registry tree at HEAD : 41
  satisfy the ref pattern                          : 41
  refused                                          :  0
```

**Class A is therefore safe.** Had even one real id carried an uppercase character the
retype would have refused a legitimate value, and nothing downstream would have caught it.

## Classification

### Class A - registry revision slug, retype onto `RevisionId` (85 sites)

56 bare `revision_id`, 5 `registry_revision_id`, 5 `left_` + 4 `right_revision_id`,
3 `expected_revision_id` in the loader, 2 `target_`, 2 `year_a_` + 2 `year_b_`,
2 `selected_`, and one each of `requested_`, `resolved_`, `declaring_` and
`latest_revision_id`.

**Verdict: promotable.** Every bare `revision_id` site adjudicated sits beside `modelo`,
`filing_year` and `period` - the registry coordinate axes - or resolves a `ModeloRevision`
directly, or builds the `registry:{modelo}:{revision}` schema marker. Every one of the four
sites carrying a docstring documents a registry revision, one of them with the literal
example `2019-y-siguientes`. The adjudication was made against each site's producer, not
its name.

### Class B - hex-64 calculation revision, retype onto `CalculationRevisionId` (35 sites)

32 `calculation_revision_id`, plus 3 `new_revision_id` in the amendment actions, which build
a draft calculation revision from a baseline `CalculationRevision` and are therefore this
concept under a different name.

**Verdict: promotable.**

### Class C - the law-determined stamp (7 sites)

All 7 are `stamped_revision_id`. By shape this is a registry slug, so it retypes onto
`RevisionId`.

**Verdict: promotable, and it strengthens these sites - but the reason it is safe is not the
one it looks like.** The persisted authority already carries `min_length=1, max_length=128`
and a description confirming it holds the registry revision the source filing resolved to.
The seven bare-`str` sites are downstream projections and parameters, not the persistence
boundary. **The requirement that a missing or invalid stamp refuse at strict load is already
met where it must be met**, so retyping the projections neither creates nor closes that
guarantee.

One asymmetry to carry into execution: `RevisionId` adds a **pattern** the persisted field
does not have. Against the measured population that refuses nothing, but it means the
projections would become strictly stricter than the field they project. That is acceptable
only while the 41-id measurement holds, and it is a measurement rather than a property.

### Class D - NOT this taxonomy, must not be retyped (3 sites)

- **2 x `short_calculation_revision_id`** - a 12-character short form. Neither canonical type
  admits it: `CalculationRevisionId` requires the full 64 and `RevisionId` is a different
  concept. The selector that parses it accepts an alternation of 12 or 64 characters
  deliberately. Retyping either way refuses a live, in-use value.
- **1 x `expected_revision_id` in the secure-object SQL adapter** - this is a **storage row
  version** used for optimistic concurrency, sitting beside `namespace` and
  `current_revision_id` and producing a secure-object revision-conflict error. It is not a
  modelo revision, a registry revision or a calculation revision. It matches the name
  pattern and belongs to a different domain entirely.

**Class D is the reason a name-based sweep would have been wrong.** All three sites are
reachable by any grep for the row's own vocabulary, and all three break if retyped.

## Corroboration, and why it is worth stating

24 sites already carry `CalculationRevisionId` and 16 already carry `RevisionId` - unprompted
instances that predate this adjudication. The two-concept split is therefore load-bearing in
the tree already, not a property constructed to fit the evidence. Where a proposed
classification has no unprompted instances, it may be describing its author; here it has 40.

## Two defects found while measuring, neither actioned

1. **A stale docstring example.** The profile preflight module documents a revision tag as
   `"2024-0A"`. No such revision id exists among the 41, and that shape is **refused** by the
   registry's own ref pattern because of the uppercase character. The example teaches a shape
   the system would reject.
2. **`W05.P07.S36` instructed minting a duplicate.** It named a "new `RegistryRevisionId`
   alias" for the concept `RevisionId` already owns. Amended 2026-08-11 to retype onto
   `RevisionId` and create nothing. Recorded here because the row is this document's consumer
   and would otherwise have executed against it.

## What this document does not decide

Whether Class A, B and C become one row each, one plan, or stay as `W05.P07.S35`/`S36`. That
is a scheduling call and the class sizes above are what it needs. The 85 `str | None` sites
remain unmeasured and would have to be adjudicated on the same basis before any class could
be called complete.
