---
tags:
  - '#research'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a39a532c0e12cdb990d43186126a95478d458a8757fdfc42ae2b5ffadd3766fd'
related: []
---

# `registry-generator` research: signal coverage

## Why this document exists

A defect affecting 2,117 filing-grade fields shipped and stayed shipped. Every gate was green
throughout. This document records why — what the existing signals actually prove, what no signal
asks, and which instruments would have caught it. It is the input to decisions about type
enforcement, cross-period checking, and where new gates belong.

The finding in one line: **every gate that exists is a fidelity gate — output equals a function of
the inputs — and none is a correctness gate. Nothing compares the output to the design it read.**

## What the gates prove today

The generators are not failing. They succeed at a question nobody asked them to be right about.

Check mode genuinely runs and passes for 19 of 32 revisions (an earlier claim that it was disabled
everywhere was wrong: the pending list holds 11 entries, not 32; the gate was run and reported 70
passing). Where it runs it proves the candidate loads through the real authority, that the
published manifest attests the same input digests, that normalised semantics match, and that bytes
match.

Its teeth are real but pointed elsewhere: eleven injected defects, every one a mutation of an
**input or an output** — semantic map, source digest, transport profile, manifest fields, member
lists, bytes. **Not one injects a defect in the design-to-output relation.** A passing check means
"this tree is what these inputs produce, and it loads". It has never meant "this tree is right".

The same shape recurs in the reproducibility suite: a fresh render is compared against the
committed tree using the inputs that produced the committed tree. That detects staleness, which is
worth having, and cannot detect a wrong input.

## The instrument that exists and reports nothing

One analysis screen measures exactly the distinction that mattered — its unit tests assert that
the signed and unsigned type tokens are told apart, and its own prose says the two notes *"differ
on sign"*. Its module states: *"The screen exits 0 whatever it finds. It reports; it does not
gate."*

A whole-tree sweep found **zero references to it from any recipe, workflow or configuration**. Its
own test asserts that the screen *finds things*, not that the corpus is clean — so the pass
condition is detection, and nothing turns a finding into a failure.

It is not alone. **Eighteen screens are registered in that package, and the register gates nothing.**

That is the meta-signal, and it may be the most valuable output of this work: the screens are a
triage stage with a documented promotion path, which is a defensible design. What is missing is
any check that a screen reporting a non-zero, actionable population **has been promoted to a
gate**. A triage queue with no drain fills.

## Cross-period checking does not exist

The entire cross-revision comparison surface is five attributes of the casilla definition: label,
section, domain data type, semantic role, legal references.

**Every export-field wire axis — sign, length, decimals, padding, justification, value policy,
allowed values — is never read by any cross-revision comparator.** The justification vocabulary
could not express a shape change even if they were in scope: it offers evolved-label,
evolved-references, repurposed and retired, with no notion of a changed type or width.

The named continuity machinery does less than its names suggest. The staging helper compares
nothing — it copies predecessor casilla facts so a strict gate is answerable, and **explicitly
excludes both export surfaces**, so a predecessor's wire shape is not even present. Two continuity
screens report and do not gate. The strict policy is triple-opt-in and live on four of 128
revisions.

The repository already knows: *"Nothing in the registry states that one wire type may render as
another while a third would be a defect. Every transition is currently accepted because no rule
exists to reject one… the gate comes after the table, not before it."*

### The cross-period signal, measured — and its honest bound

The proposal is sound: a field whose typed shape changes between revisions without a corresponding
change in the official design is a suspect; fields stable across revisions are higher confidence.
It needs no join to an official document, so it can run over the authored surface too, which no
other instrument reaches.

Measured over 1,753 identities joined in two or more revisions: 1,458 stable on all nine axes, 295
with at least one change, of which two thirds are migration or convention artefacts, 88 look like
real regulatory change, and **12 are genuine suspects** — 8 surviving a key-artefact discount.

**But the bound must travel with the signal.** Sign is 100% stable across all 1,753 identities —
and the axis is *exercised on 23 of them*. Of 2,279 signed fields, 2,229 sit in one modelo that has
exactly one export revision and therefore contributes zero comparisons. Thirty-two modelos ship
monetary fields and zero signed fields.

So on this corpus **agreement is not evidence — it is mostly the absence of evidence. Divergence
is the only informative side.** The honest output is a ranked suspect list, not a defect count.

A second caveat cuts against an intuitive reading of the same data. Hand-authored layouts churn
*less* than generated ones (5.6% versus 12.0% of identities) — which sounds reassuring, but low
churn is also what copy-forward looks like. Eight modelos join at 100% with near-zero change across
up to five revisions. **A layout duplicated forward unchanged shows perfect agreement while
silently failing to track real regulatory change**, converting changes that should exist into
invisible absences. The instrument cannot distinguish "correctly stable" from "never updated".

## Type enforcement does not reach the generator

The type-check gate is configured at maximum strictness — every rule an error — over a scope that
**excludes the entire registry pipeline and all tests**. The exclusion is an honest, named
burn-down with per-area diagnostic counts and an explicit admission path, not a silent baseline.
But the consequence stands: no checker opens the generator.

Two further facts bound what stricter typing can buy:

- The wrong values are **not defaults**. The field is required at both the schema and the
  generator's own parameter; twelve sites pass it explicitly. A required field with no default is
  precisely what "fail hard on a missing value" produces — and it produced this anyway, because
  what was missing was never a value, it was a *reading*.
- Construction goes through validation from a dictionary, which **erases the declared type**. A
  probe confirmed the direct keyword form errors while the dictionary form is silent. So enriching
  the schema field would catch none of the twelve sites even inside a checked scope. Only changing
  the generator function's own parameter bites.

The project's own configuration argues the same point from the other side: a checker rule was
rejected on the grounds that *"its premise — that an annotation is enforced at run time — is
false in Python"*, while the no-silent-under-declaration rule requires validation at the boundary.
Runtime validation, not static strictness, is this codebase's enforcement culture, and it is right
for a corpus that is read from disk.

## Gate design constraints this project has already established

Any new signal must satisfy rules the codebase enforces on itself:

- **No frozen counts, no baselines, no allowlists.** A floor must be an invariant or a named set.
  A worked example landed during this work: a numeric floor was replaced by a named site map so
  that retiring a site is an explicit removal, and it was *proved* stronger — a substitute site
  passes any count-based floor while leaving the real one unguarded.
- **A floor with no planted defect is unproven.** Plant on constructed input, never by mutating
  the working tree.
- **Join through the pipeline's own anchor machinery**, never a coordinate join. A naive
  coordinate join on this corpus produced a confident number that was pure noise.
- **A gate that fails on the day it lands cannot be cleared by the change that adds it.** For a
  defect of this size the landable instrument is a *generator refusal*, which fails closed and
  cannot be overwritten by the next regeneration; the gate follows afterwards, green.

## What would actually close this

Ranked by leverage, from the reviewers' own recommendations:

1. **Gate the contradiction, not the value.** A field whose type column and content cell imply
   different integer widths must refuse, naming modelo, revision, field and both readings — the
   treatment ambiguous content already receives. This is the general form, so it catches the next
   instance rather than this one.
2. **Record the pair in the attestation.** Make the provenance manifest carry each field's source
   type alongside its emitted sign. The mismatch then becomes a diffable, reviewable fact in the
   artefact instead of something only a bespoke sweep can see — and it makes the authored surface
   auditable by the same means once it carries manifests.
3. **Check the reading against something the generator did not produce.** Extend the conformance
   vector mechanism from pinning the generated tree's own digest to pinning **official worked
   examples** — real published fixed-width records containing a known negative amount, decoded
   through the shipped codec and compared field by field. The bundled corpus already holds
   twenty-two worked-example payloads across several modelos, so the gap is the comparison, not
   the material.
4. **Wire the live drift detector.** It already exists and runs; nothing invokes it. This is the
   cheapest high-value signal available.
5. **Promote or retire the screens.** Eighteen registered screens gate nothing; the one
   that measured this defect is among them.

## The gap this work did not examine

**How the backend consumes the registry has not been looked at at all.**

Everything above concerns producing a dependable artefact. Nothing here establishes what the
consuming application does when handed a registry that is internally inconsistent, temporally
incoherent, or partially adjudicated — whether it refuses, degrades, or proceeds. Specifically
unexamined:

- whether the authority rejects a revision whose declarations contradict its predecessors;
- whether a calculation reading a field can tell an adjudicated value from an undetermined one;
- whether filing-grade paths distinguish "the registry is silent" from "the registry says zero";
- whether any consumer would notice the corpus going stale against a republished design.

The rigour argued for above is worth little if the consumer accepts whatever it is given. This is
the first lane to open next, and it should be scoped before the decision record is finalised — the
rulings on refusal semantics belong on both sides of that boundary.

## Confidence

VERIFIED: the check-mode correction and the run that established it; the screen wiring sweep; the
cross-revision comparison surface and its vocabulary; the type-check scope and the validation
probe; the cross-temporal measurement and its exercised-axis bound.

INFERRED: that no gate outside the registry package protects the sign axis — the search covered
the pipeline and the domain registry, not the whole application tree. That gap overlaps the
unexamined backend question above.

## Findings

- Every existing gate compares generator output against a function of the same inputs, so it can
  prove reproducibility but not fidelity to the official document.
- The design-to-shipped join is already serialized in every provenance manifest and is read by no
  gate; the TOML loader ignores the manifest by design.
- No cross-revision comparator covers export wire shape: the existing one compares label, section,
  data type, semantic role and legal references only.
- Static type checking does not reach the generator: `dev/registry` is outside every checker's
  scope, and construction through `model_validate` from a dict literal erases the declared type.
- Reporting screens exist with no promotion or retirement path; the register already distinguishes
  findings screens from census screens.
- How the consuming application behaves given an incoherent registry was not examined.

## Sources

- `dev/registry/tests/test_generated_export_trees.py`, `dev/registry/tests/test_generated_tree_publication.py`
- `src/cadrumo/domain/calculations/registry/_cross_revision_divergence.py`
- `dev/quality/types.py`, `pyproject.toml` (`[tool.pyrefly]`, `[tool.basedpyright]`)
- `dev/registry/analysis/screens.py`, `dev/registry/analysis/type_convention_notes.py`
- `dev/registry/pipeline/generated_tree_dispositions.toml`
