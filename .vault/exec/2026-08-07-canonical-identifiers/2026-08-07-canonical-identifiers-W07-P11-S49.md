---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c9039bb4140fc5d931c0271aef230bfb96acb3d6ab4b9d0a10c27331ca113cf3'
step_id: 'S49'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# author and run dev/identifier_noun_census.py, an AST sweep matching field docstrings against a noun-vocabulary heuristic independent of the original suffix heuristic

## Scope

- `dev/identifier_noun_census.py`
- `dev/tests/test_identifier_noun_census.py`

## Description

- Author a census reading a field's DOCUMENTATION rather than its name, over a pinned revision.
- Mark every record with whether the original suffix sweep would also have found it, so the difference between the two heuristics is computable in one pass.
- Cover it with contract tests including three negative controls.
- Run it against the pinned tree and record the output table below.

## Outcome

**The census output, which is this row's named gate:**

```
documented_identifier_fields         162
bare_str                             103
missed_by_suffix_heuristic           101
missed_by_suffix_heuristic_and_bare   69
```

**The 589 denominator is confirmed a floor by measurement rather than by argument.** The
census finds `Deuda.clave_liquidacion` and marks it invisible to the suffix sweep — the
exact field the decision record names as proof the original count could not report its own
completeness. The instrument finds the case it was built for, in the category that proves
the point.

**A second, previously unnoticed proof of the same floor.** The receipt verification-code
fields are ALSO invisible to the suffix heuristic, because the field is named exactly
`csv` and that name does not end in the `_csv` suffix the original sweep matched. So the
original census missed TWO of the four AEAT-issued concepts this campaign enrolls by name,
not one. Nobody had observed this.

## Notes

**What the 101 is and is not.** It is a candidate set with a material false-positive rate,
not 101 missing enrollments. The Spanish authentication provider's name matches the *clave*
vocabulary; delegated-access prose matches *identity*; an encryption algorithm field
matches *identifier* incidentally. Triage into the namespace set, a new namespace, or an
explicit exclusion is a separate row and is deliberately not hidden inside the scanner — a
scanner that adjudicated would make its own false positives invisible.

**A pinned revision is required rather than optional, and this is a correctness property
not a convenience.** This repository is written to by many agents at once. During this
row's own execution the working tree went from over nine hundred modified files to under a
hundred. A census over a moving tree cannot be re-derived, and the table above is quoted
as a gate — a number nobody can reproduce is not a gate. Both sibling censuses under the
same tooling directory demand a revision for the same reason, which is how the requirement
was discovered rather than invented.

**Grounded before authoring, and the grounding changed the design three times.** A
semantic search located an existing identity scanner in the tooling tree and it was read
rather than assumed equivalent: it hunts checksum-valid identifier VALUES in file content
as a security canary and is deliberately value-free, which is a different concept from a
field census and therefore not this work's canonical home. The real precedent is the
sibling action-envelope census, whose siting, record shape, command-line surface and test
convention this follows instead of inventing one. Its pinned-revision source reader is
imported rather than re-implemented, read-only, without editing a module another campaign
owns.

**Landed in three commits rather than one**, none of them run by this executor: the script,
then its tests with a reformat, then a lint-driven branch flattening. The row's deliverable
is a script and its measured output, both of which exist and agree with the table above, so
nothing is lost — but the split is recorded rather than presented as a single clean landing.
