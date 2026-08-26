---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:871990eda9fad066e5d298c5f40474e9d9a81af81fe35b1ccc299af5e520e51c'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `S175 independent architecture review`

## Scope

The independent architecture review that Step `W03.P20.S175` requires before it may
close. Reviewed at HEAD `9ac8190a98`, cross-checked at `d1f9e6606e` and `02230a68f9`:
`dev/quality/registry_facade_family_census.py`, the 78-row
`dev/quality/registry_facade_family_census.v1.json`, and the 21-test
`dev/tests/test_registry_facade_family_census.py`.

Verdict: REJECT. `review_status` must not be flipped to reviewed.

The generator structure and the plan-Step binding logic are sound. The defects are in the
evidence snapshot's scope and in the honesty of the per-row adjudication. Both are
fixable without a rewrite, but the artifact must be regenerated and re-adjudicated.

## Findings

### Evidence snapshot ingests a gitignored mirror of the source tree

`dev/quality/registry_facade_family_census.py:231-241` walks `EVIDENCE_ROOTS` with
`rglob`. `dev/benchmarks/cli/.baseline-source-snapshot/` is a complete duplicate of the
source tree, 4919 Python files, gitignored at `dev/benchmarks/cli/.gitignore:1` and
untracked. Of 628,481 consumer entries, 278,894 (44.4 per cent) are paths inside that
mirror, across 75 of 78 rows.

What is lost: half the census names copies no disposition Step will ever sweep, and the
matrix cannot be reproduced on any other checkout, so the check reds irrecoverably in CI.
The deterministic generator with check mode is deterministic only on this machine.

Remediation: exclude gitignored paths from `_evidence_files`, then regenerate.

### The check flaps on unrelated peer commits, so there is no stable fixed point

`dev/quality/registry_facade_family_census.py:947-950` fails the document when
`evidence_measurements` differs from the live tree, and those measurements are tree-wide
scalars over all of `src/`, `dev/` and `docs/`. Observed on the same artifact with no edit
to it: red at `d1f9e6606e` on a one-edge `relative_import_edges` delta from an unrelated
peer commit, green at `9ac8190a98`.

What is lost: any commit anywhere that adds or removes one relative import invalidates a
62MB reviewed adjudication, so the gate cannot stay green long enough to be a gate.

Remediation: drop the whole-tree scalars, or scope them to the 78 candidates plus their
direct consumers. The row-level comparison at `:997-1001` already detects real drift.

### A re-export import is recorded as a defining locator

`dev/quality/registry_facade_family_census.py:696-697` adds imported names to the symbol
locations identically to a `ClassDef`, so the census cannot distinguish a canonical
defining module from a facade, which is the exact discrimination `keep_public` asserts 54
times.

Five rows point at an `ImportFrom` while carrying a `definition` node type: R06 at
`bindings.py:74`, R23 at `formula_runtime.py:58`, R52 at `queries.py:38`, R73 at
`validate_cross_revision.py:27`, R74 at `validate_references.py:28`.

R06 is the sharpest. `bindings.py` imports `AtributionMemberObservation` at line 75 from
`detail_record_bindings.py:430`, and its only other occurrence is the export list at line
248. That is a pure re-export, a standing `aeat-architecture-boundaries` violation, and
the row certifies its terminal state as `public_local_definitions_only`. The census does
not merely miss the violation; it blesses it.

Remediation: split import names into a separate re-export bucket, refuse a `definition`
result resolving to an import, re-adjudicate the five rows, and open the `bindings.py`
re-export as a real finding.

### R66 carries a fabricated locator

R66 records `build_snapshot` at line 0, while the symbol is defined at `snapshot.py:190`,
a line its own prose states correctly. The validator at `:1018-1024` checks only that the
value is an integer, so zero passes. R66 is also the sole row with no exported symbols,
and `:1051-1053` routes exactly that case around the normal locator proof.

Remediation: reject a start line below 1 and record the real locator.

### 77 of 78 review rationales are one substituted template

The Step requires failing every mechanically inferred row. `_normalized_review_prose` at
`:895-901` normalizes digits but not module names, symbol names or action text, so a
template substituting exactly those tokens yields 78 distinct strings and passes the
duplicate refusal at `:1067-1075`.

Corroborating: `semantic_owner` is a mechanical restatement of the locator in all 78 rows;
the substitutability result is `no_substitutable_owner` in 78 of 78 and
`dev/tests/test_registry_facade_family_census.py:290` hardcodes that constant as its
assertion, making the test tautological; 71 of 78 rows carry an empty competing-site
census, including both `delete` rows. Exactly one row, R01, carries genuine reasoning.

Remediation: normalize identifiers as well as digits, and re-author rationales for the 24
rows whose disposition is a real judgement call.

### Discovery queries embed the conclusion they should have discovered

70 of 78 recorded queries contain their own row's follow-on action verbatim, and
`:1064` then requires the query to appear in the rationale, checking generated text
against generated text. The Step requires discovery followed by census, not a disposition
pasted into a query field and asserted against itself.

Remediation: record the real discovery query, and refuse one containing the disposition.

### Disposition counts are hardcoded as a pass condition

`dev/quality/registry_facade_family_census.py:1116-1123` and
`dev/tests/test_registry_facade_family_census.py:493-498` both pin 54 keep-public, 9
hard-move, 13 privatize and 2 delete. The Step mandates exactly 78 rows, which is a
legitimate property of git history; it does not mandate a disposition tally.
`aeat-quality-gates` forbids a hardcoded count as a pass condition, and acting on any
finding here reds the gate until two constants are hand-edited together.

### Closing the Step will itself red the gate

`:950-951` hard-refuses any review status other than the pending value, and `:983-985`
requires S175 to remain unchecked in the plan. Both assertions must be retired in the same
commit that closes the Step. Not a defect, but it must be planned.

### The matrix writer leaves a stale temp file on exhausted retries

`:1142-1162`. The chunked write plus atomic replace is correct, and the temp suffix is
outside the evidence suffixes so a leftover cannot re-enter the snapshot. No correctness
risk. Two nits: no unlink after exhausted retries, and no fsync before replace.

## Where nothing was found

The 78-row denominator is sound: the candidate set derives from the c941 rename delta, not
a filename scan, so gating on exactly 78 is legitimate. The plan-Step binding is genuinely
strict, with all 78 follow-on identifiers unique, canonical and present, and the binding
proven against path laundering. Several tests genuinely bite, including two real mutation
proofs. 53 of the 54 keep-public rows check out as genuine canonical defining modules, so
the hypothesis that 54 was suspiciously high did not survive contact with the tree.

## Recommendations

Conditions for approval, all six required before re-review:

- Exclude gitignored paths from the evidence snapshot; narrow the generated-artifact
  predicate to the matrix itself, since it currently also drops the authority census that
  carries real consumer edges; regenerate.
- Remove or scope the tree-wide evidence measurements.
- Separate import locators from definition locators, refuse a definition result resolving
  to an import, and re-adjudicate R06, R23, R52, R73 and R74.
- Fix R66's locator and refuse a start line below 1.
- Re-author review prose for the 24 non-keep-public rows and record real discovery
  queries.
- Drop the hardcoded disposition tally from both generator and test.

The two critical findings and the R06 and R23 re-export claims were verified
independently against HEAD before this audit was persisted; all four reproduced exactly.
