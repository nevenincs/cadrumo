---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:68a3cda25bdb442a53c2be57cb7d8b729cc9daaf241530e161af3e5ea010252a'
step_id: 'S10'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# Add a standing real-site regression restoring an actual twin at every discovered module and confirming the verdict names it

## Scope

- `src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py`

## Description

The discovery gate passing proves that today's tree is clean. It does not prove
the check would still fire if a twin came back, because the twins it was written
against were rebound in the same change. The only real-site evidence was the
test-first red observed before the rebinding, which is historical and leaves
nothing standing in the repository.

A detector can be right on shaped input while missing the site that matters, so a
regression that plants a synthetic twin somewhere convenient would not close
this.

## Outcome

A standing regression restores an actual twin at every module the sweep found,
using that module's own live namespace and its own attribute names, and requires
the verdict to report that attribute by name.

Both declaration shapes are covered, chosen from what each site really holds: a
plain module-level constant at most sites, and a container entry at the registry
binding validator, which is where four twins hid from an attribute-only scan.

The verdict was extracted into one implementation shared by the gate and the
regression, so the regression cannot pass against a weakened copy of the rule it
exists to exercise.

The twin is built by runtime slice concatenation, because both a one-element join
and a str call hand back the original object under CPython's optimisations, which
would make the restored defect no defect at all. Two internal assertions require
the twin to compare equal and to be a distinct object, so a restoration that
silently failed cannot read as a pass.

Bare-numeric tokens are excluded from restoration. CPython interns them, so a
restored twin of one is the same object and there is no defect to catch;
asserting a red there would be asserting the impossible, and the limitation stays
documented rather than tested away.

The sibling width validator's total-ruling shape was read and deliberately not
copied. Totality solves a closed set of entries each needing a DIFFERENT ruling,
where omission is silent. Here the rule is uniform for every module, so
completeness comes from discovery over the tree, and a ruling mapping keyed by
module would reintroduce exactly the enumeration this remediation removed. The
principle that no entry escapes unruled is honoured by the sweep; the real-site
test form is the part that transferred.

## Verification

Eleven real-site cases pass, one per discovered module.

Proven non-vacuous by mutation aimed at the TEST MODULE's own helper rather than
at a production symbol, because the assertion reads that helper directly and a
production-aimed mutation would not be read here at all. With the restoration
neutered so the clone carries the authority's own objects, all eleven cases red.
Recorded under both scheduling modes: red with parallelism disabled and red under
the project's default parallel options. Green with the mutation removed.

Four guards make a vacuous pass impossible: the site must offer a dotted token,
the site must be clean before restoration, the restored attribute must still
exist under its name, and the verdict must name exactly that attribute.

Linter and type checker clean.

## Notes

Raised by the coordinator after the earlier rows landed. The gap was real: the
earlier proof was real-site but ephemeral, and nothing in the repository carried
it forward.
