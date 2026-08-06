---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:ba8f5c48e5fa8109e3b89d7c509ded03c898a0c0f0d4b8a8a05ee128792f56ec'
step_id: 'S41'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# consolidate the boundary detection onto the single hygiene scanner authority the ADR chose, deleting the duplicated inline import detector and its stale pending-ruling heading while keeping the injectable-root proof local

## Scope

- `src/cadrumo/tests/test_dev_path_isolation.py`

## Description

- Confirm the defect at HEAD: the boundary gate carried a second implementation
  of the `dev.*` import detector inline, under a section headed "Duplicated
  import detector (pending ruling)", plus a `_is_shipped_module` documented as
  mirroring the scanner's predicate "without importing it".
- Establish that the path-literal family existed ONLY in the boundary gate, so
  consolidating the import half alone would have left one detector in each
  place - the same fork under a different split.
- Move the whole path-reach family into `dev/import_hygiene_scan.py` as
  Family 6, beside the import family it completes: the four-value form enum,
  the violation record, every helper, and `find_dev_path_reach_violations`,
  reusing the scanner's existing `DEV_TOOLING_ROOT` rather than a second copy
  of the directory-name constant.
- Wire Family 6 into the scanner's text report, its magnitude summary, and its
  JSON payload, so both halves of one boundary are reported together.
- Widen the scanner module docstring to name itself the single authority for
  the boundary and to record why a consumer's own `dev.*` import is not a
  violation.
- Rewrite the boundary gate to import the shipped-module predicate, the wheel
  exclude reader, and BOTH detector families from the scanner, deleting every
  local copy.
- Delete the stale "pending ruling" section and the "re-implemented inline" and
  "mirrors the logic without importing it" claims; replace them with a section
  recording the ruling, the reasoning that was disposed of, and the division
  that survives - shared detection, local proof.
- Keep the vacuity floor, every firing proof, every silence proof, and the
  shipped-`conftest.py` case, retargeted at the shared detector and its return
  shapes.
- Probe every discriminating branch of the consolidated detector by removing it
  and re-running, rather than assuming form coverage implies branch coverage.
- Add the three isolating fixtures the probe proved missing, and record the
  completeness standard they imply in the module docstring.

## Outcome

One authority, two families, both halves of the boundary reported and gated
from the same code. The boundary gate lost 563 lines of duplicated detection
and kept all of its proofs.

The path family was MOVED, not mirrored. Leaving it in the gate while
consolidating only the import half would have satisfied the letter of the
ruling and reproduced its cause: two places to fix, one of which a future
author would miss. Family 6 now sits directly after Family 5 because they are
one rule in two syntaxes - a shipped module reaching an unshipped tree by code
or by data - and adjacency is what makes a fix to one visibly incomplete
without the other.

Every detection form survives the move, verified individually rather than
assumed: the root-anchored `PROJECT_ROOT` join, `os.path.join`, the `Path`
factories and `joinpath`, f-string composition in both the interpolated-root
and leading-segment shapes, the relative markers, the Windows backslash
separator, and the absolute-POSIX exclusion that keeps a device path out.

Verification, actually run and quoted:

- Zero real violations on the current tree, from the consolidated detector:
  `py files scanned: 3729`, `shipped modules : 1403 (vacuity floor 500)`,
  `FAMILY 5 real violations (dev.* import) : 0 []`,
  `FAMILY 6 real violations (dev/ path)    : 0 []`.
- The scanner run end to end confirms the same from its own reporting surface:
  `=== FAMILY 5: shipped modules importing the unshipped dev tooling: 0 total ===`
  and
  `=== FAMILY 6: shipped modules building a path into the dev tree: 0 total ===`.
- Boundary gate at the consolidation commit, DEFAULT selector:
  `18 passed in 26.99s`; unfiltered and serial (`-n0 -m ""`) to defeat a
  marker-selection false pass: `18 passed in 81.87s`. After the branch-proof
  commit: `21 passed in 15.76s` and `21 passed in 14.23s` respectively. The
  counts match across selectors in both states, so no test is being silently
  held out of the default lane.
- The scanner's own suite, unaffected: `13 passed in 1.11s`.
- Every form fired and every near-miss stayed silent when driven directly
  through the consolidated detector: literal `1 hit(s) ['literal']`, relative
  markers `2 hit(s)`, backslash separator `2 hit(s)`, anchored join
  `1 hit(s) ['path_join']`, `os.path.join` `1 hit(s) ['call_join']`, the
  `Path`/`joinpath` factories `2 hit(s) ['call_join', 'call_join']`, both
  f-string shapes `1 hit(s) ['fstring']` each; and `0 hit(s)` for `/dev/tty`
  and `/dev/null`, for `devengada` and `devolucion`, for `device/` and
  `dev.example.com`, for the string joins, and for docstring prose. The import
  half fired on `from dev.X import y`, bare `import dev`, and the dynamic
  literal target, and stayed silent on both `cadrumo` forms. The excluded test
  tree returned `[]` for both families with every violating form present. The
  shipped package-root `conftest.py` fired on BOTH:
  `[('cadrumo/conftest.py', 'dev')]` and
  `[('cadrumo/conftest.py', 'path_join')]`.

Three production mutations prove the proofs are load-bearing rather than
decorative, each applied to the consolidated detector, run, and reverted:

- Reducing the segment test to a substring test killed 7 tests, including the
  LIVE-TREE gate `test_no_shipped_module_reaches_a_dev_path` - so the
  near-miss precision is load-bearing on real shipped code, not only on
  planted fixtures.
- Neutering the path-join branch killed 2, the anchored-join proof and the
  shipped-conftest case.
- Neutering the import-target predicate killed 4, all three import firing
  proofs and the shipped-conftest case.

After reverting all three the gate returned to `18 passed in 16.28s`, and the
scanner diff returned to exactly the additive hunk set it had before the
mutations, with zero mutation residue in the file.

**Those three mutations were not enough, and the self-review that followed is
the more useful half of this record.** Killing a whole detector proves the
gate is wired; it says nothing about whether each BRANCH is individually
pinned. Six further mutations, one per discriminating branch, were run against
the consolidated detector. Three flipped a test as they should: dropping the
relative-marker skip, dropping the interpolated-f-string tail, and dropping the
docstring skip each killed exactly one. THREE FLIPPED NOTHING - the whole gate
stayed green at 18 passed with the branch removed:

- the `join` arity-of-two guard, because `"".join(parts)` has no bare `"dev"`
  argument to match and the two-argument path forms are permitted by the guard
  anyway, so neither existing fixture could tell whether the guard was there;
- the newline rejection, because every prose fixture was a docstring and was
  skipped by node id before the newline check was reached;
- the left-hand operand of a path join, because the anchored-join fixture only
  ever put the segment on the right.

All three were faithfully preserved from the pre-consolidation detector, so
this is inherited rather than introduced - but a branch nobody can flip is a
branch the next refactor deletes with the suite still green, which is precisely
the risk this Step exists to remove. Leaving them unproven would have shipped a
consolidation that looked complete and was not.

Three isolating fixtures now pin them, each derived from what the branch is FOR
rather than from what the code does: `"x".join("dev")` (a one-argument join
whose sole argument IS the bare constant), a multi-line non-docstring module
constant, and `"dev" / PROJECT_ROOT`. Expected behaviour was confirmed against
the specification before the assertions were written - the first two silent,
the third firing as `path_join`.

Re-probed after the fixtures landed: each of the three mutations now fails
exactly one named test, `1 failed, 20 passed` in every case, where all three
were `18 passed` clean before. The module docstring records the standard this
implies - every discriminating branch must flip a test; form coverage alone
does not deliver that.

Landed as two commits: `6ed41c74b7` (the consolidation) over the explicit
pathspec pair `import_hygiene_scan.py` and `test_dev_path_isolation.py`, and
`3357998d7f` (the three branch proofs) over `test_dev_path_isolation.py`. The
second is a separate commit rather than an amendment because the first was
already reachable in a shared worktree, and the split is what makes the
self-review visible in history instead of dissolved into the change it audits.

## Notes

The mandatory semantic-discovery probe was WAIVED by explicit operator
direction for this step: the semantic index is broken and its service stopped,
with a standing instruction not to start, restart, or reindex it. Discovery was
carried by `rg` plus whole-file reads of both detector modules, the pre-existing
hygiene gate, and both review records.

Two tests in the pre-existing hygiene gate are RED and are NOT owned by this
Step: `test_test_only_underscore_reaches_do_not_exceed_test_debt_count` and
`test_test_only_underscore_reaches_are_exactly_the_named_test_debt_set`. Both
fail on one signature - a sanitizer test module importing `SRC_CADRUMO` from
the shared test inventory. Attribution, checked rather than assumed: that file
is committed at HEAD by a sanitizer campaign and is absent from the test-debt
baseline, so the failure predates this work; this Step touched neither that
file, nor the inventory module it reaches, nor the baseline. The failing
assertions belong to Family 1, and this Step's scanner diff is purely additive
after Family 5 - every hunk an insertion, and zero changed lines in the import
walk, the Family-1 fold, the test-module partition, the owning-package
resolution, or the facade discovery those assertions run through. The same
review round already recorded this class of red as sanitizer-campaign-owned.
Left for its owner rather than fixed here, and recorded so the next reader does
not re-attribute it.

The gate now imports `dev.*`, which is the change most likely to look like a
boundary violation to a future reader. It is not one, and the reasoning now
sits in the module docstring rather than only here: the module is
wheel-excluded, so its imports cannot follow the package to an installed user,
and a scanner's own imports have no bearing on the shipped surface it measures.
The pre-existing hygiene gate has imported the same scanner from the same tree
for as long as it has existed; this Step adds a second consumer, not a new
precedent. The excluded-test-tree silence proof pins that scope, so widening
the family to test trees would red a test rather than pass quietly.

The stale heading was deleted rather than corrected in place. It did not merely
describe the duplication - it instructed the reader that neither detector was
to be removed and that dropping a check would be the wrong resolution. Left
standing above a consolidated gate it would have re-asserted the rejected
design as doctrine to the next author, which is a worse outcome than the
duplication it described.
