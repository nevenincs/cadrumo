---
tags:
  - '#reference'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:af4ff5e5523a1f1b5b4d8bdb316a0356f1e4716b1e1b80117a0ace6f7eeea424'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# `canonical-identifiers` reference: revision_id adjudication

Grounding for `W05.P07.S35` and `W05.P07.S36`. Produced 2026-08-11. **No code was
changed.** The row asked for twelve sites in one file; this is the measured population and
its per-concept classification, so the scheduling decision can be made against class sizes
rather than an assumed denominator.

## The population

Instrument for every count below: AST over `git show HEAD:<path>` bytes - parameter
annotations and annotated assignments, tests excluded. Reading the object store rather than
the working tree matters because the tree carries a large uncommitted registry migration.

| measurement | value |
|---|---|
| annotated `revision_id` sites, production `src/` | **308** across 115 files |
| bare `str` | 130 |
| `str \| None` | 85 |
| **adjudicated here** | **215** |
| already `CalculationRevisionId` | 24 (+16 optional) |
| already `RevisionId` | 16 |
| the row's named file holds | **1** of the 130 |

`W05.P07.S35` reads "the twelve bare `revision_id` sites" and scopes itself to a single
registry module. The optional half was adjudicated on the same basis rather than deferred,
because a class landed over half a population reports closed while it is not.

## The finding that makes this an adjudication rather than a sweep

Four different concepts wear the name `revision_id`:

- the **hex-64 calculation revision** - a content-addressed id of a calculation this system produced
- the **registry revision slug** - a law-determined tag such as `2019-y-siguientes`, published by AEAT orden
- the **law-determined stamp** - the registry revision a source filing resolved to at capture time, re-confirmed before a carry is trusted
- the **secure-object row version** - an optimistic-concurrency token in the encrypted store, belonging to a different domain entirely

That is the campaign's standing goal appearing in the **type layer** rather than the module
layer. A mechanical retype would silently constrain the three concepts it does not fit.

## Classification

| class | retype to | bare `str` | `str \| None` | total |
|---|---|---|---|---|
| **A** registry revision slug | `RevisionId` | 85 | 27 | **112** |
| **B** hex-64 calculation revision | `CalculationRevisionId` | 35 | 25 | **60** |
| **C** law-determined stamp | `RevisionId` | 7 | 1 | **8** |
| **D** MUST NOT TOUCH | nothing | 3 | 32 | **35** |

### Class A - registry revision slug (112)

Every bare `revision_id` site adjudicated sits beside `modelo`, `filing_year` and `period` -
the registry coordinate axes - or resolves a `ModeloRevision`, or builds the
`registry:{modelo}:{revision}` schema marker. All four sites carrying a docstring document a
registry revision, one with the literal example `2019-y-siguientes`. The optional half is
concentrated in work addressing, the registry authority and snapshot construction, and the
workflow resume resolvers.

**One caution for whoever executes it:** the registry authority's `snapshot` and
`select_revision` take an optional `revision_id`. The revision-resolution rule permits a
stored id to be **asserted equal** to the law-determined resolution and forbids it being
**injected as the selector**. A retype must preserve whichever semantics those call sites
already have - this document classifies the type, it does not audit the direction.

### Class B - hex-64 calculation revision (60)

Includes 3 `new_revision_id` in the amendment actions, which build a draft from a baseline
`CalculationRevision` and are therefore this concept under a different name - invisible to a
name-based sweep.

### Class C - the law-determined stamp (8)

7 bare fields and parameters, plus exactly 1 optional - a save-path parameter that derives
the law-determined value when omitted.

**The defect this class was searched for does not exist.** No model or dataclass field
declares an optional `stamped_revision_id`, so the required-non-empty rule is not violated
anywhere. The persisted authority already carries `min_length=1, max_length=128` and a
description confirming it holds the registry revision the source filing resolved to; the
bare sites are downstream projections, not the persistence boundary. Retyping them neither
creates nor closes that guarantee.

One asymmetry to carry into execution: `RevisionId` adds a **pattern** the persisted field
does not have, so the projections would become stricter than the field they project. Safe
against the measured population, and only against it.

### Class D - NOT this taxonomy, must not be retyped (35)

**14 short-form sites.** `short_calculation_revision_id`,
`short_current_calculation_revision_id`, `short_filed_calculation_revision_id` - a
12-character abbreviation. Neither canonical type admits it: the hex-64 alias requires the
full 64 and the slug is a different concept. The selector that parses it accepts an
alternation of 12 or 64 characters deliberately. Retyping either way refuses a live value.

**21 secure-object row versions.** An optimistic-concurrency token for the encrypted store,
reachable through `expected_revision_id`, `previous_revision_id` and `current_revision_id`,
and through the revision-chain machinery that derives, verifies self-consistency and builds
ancestor ids. Not a modelo, registry or calculation revision. Every one of these matches any
grep for the row's own vocabulary, and every one breaks if retyped.

**Class D is 16% of the population and was 2% before the optional half was measured.** That
ratio is the argument for measuring it first.

## Two instrument failures, both caught, both worth keeping

1. **A path-based filter cannot find a concept declared outside its path.** Bucketing
   secure-object sites by `/storage/sql/` and filename missed **five** `to_secure_object_write`
   methods in the profile persistence adapters and the bucket protocol - all returning
   `SecureObjectWrite`, all unambiguously the storage concept. They were recovered by reading
   each site's producer, which is the discipline this document claims to apply, applied to
   its own output. A denominator inherits the shape of the instrument that produced it.
2. **The bare-`str` pass alone would have understated Class D by a factor of ten.** Optionality
   is where the divergent concepts concentrate, because a short form is absent until
   calculated and a row version is absent on first write. Landing Class A on the bare half
   would have looked complete and left 32 must-not-touch sites unexamined.

## Substitutability, measured before any verdict

`RevisionId` carries `min_length=1`, `max_length=128` and a lowercase ref pattern where a
bare `str` carries none, **so every retype NARROWS its site.** A narrowing is safe only if
the real population satisfies the constraint, so that was measured:

```
distinct revision ids in the registry tree at HEAD : 41
  satisfy the ref pattern                          : 41
  refused                                          :  0
```

**This is a measurement with an expiry, not a property.** All 41 satisfy the pattern *today*.
A future revision id carrying a single uppercase character would make a landed retype refuse
a live value, silently, at a boundary nothing else guards. Whoever lands Class A owns that
exposure and should say so in the commit message rather than in this document alone.

## Corroboration, and why it is worth stating

24 sites already carry `CalculationRevisionId` and 16 already carry `RevisionId` - unprompted
instances predating this adjudication. The concept split is therefore load-bearing in the
tree already, not a property constructed to fit the evidence. Where a proposed classification
has no unprompted instances it may be describing its author; here it has 40.

## Two defects found while measuring, neither actioned

1. **A stale docstring example.** The profile preflight module documents a revision tag as
   `"2024-0A"`. No such revision id exists among the 41, and that shape is **refused** by the
   registry's own ref pattern because of the uppercase character. The example teaches a shape
   the system would reject.
2. **`W05.P07.S36` instructed minting a duplicate.** It named a "new `RegistryRevisionId`
   alias" for the concept `RevisionId` already owns. Amended 2026-08-11 to retype onto
   `RevisionId` and create nothing.

## What this document does not decide

Whether A, B and C become one row each, one plan, or stay as `W05.P07.S35`/`S36`. That is a
scheduling call and the class sizes above are what it needs. **There is no longer an
unmeasured remainder** in the annotated population: all 215 bare and optional sites are
classified. The 93 sites already carrying a canonical type are correct as they stand and
need no work.
