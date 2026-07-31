---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:c7aa87db341eca2bfb5e654a982056392e9bdc01c0092cece996b600eb4d3a69'
step_id: 'S27'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# widen the dev-path literal detection to the realistic PROJECT_ROOT join, os.path.join, f-string and backslash forms, invert the test that pins the hole open, and mirror the missing shipped conftest case, remediating the review finding dev-path-literal-hole

## Scope

- `src/cadrumo/tests/test_dev_path_isolation.py`

## Description

- Widen the dev-path detector from a three-prefix starts-with test to four forms: the path literal (now folding the Windows backslash separator), the pathlib join onto a bare `dev` segment, call-assembled segments (`os.path.join`, the `Path(...)` factory, `joinpath`), and f-string composition.
- Make every match whole-path-segment rather than substring, and reject an absolute `/dev/...` value as a POSIX device node.
- Skip module, class, and function docstrings so prose naming a dev tool is not read as a runtime dependency.
- Invert the test that pinned the `PROJECT_ROOT` join as non-firing into a firing proof, and give every form its own firing proof and every near-miss its own silence proof.
- Mirror the shipped `conftest.py` case, proven on the dev-side detector and absent here, asserting it for both the import and the path check.
- Record in the module docstring that the import half duplicates a detector the dev tree owns, pending an ADR ruling on single-versus-dual authority.
- Rename the finder to `find_dev_path_reach_violations` and return a named record carrying the matched form, since the check no longer covers only literals.

## Outcome

The finding was confirmed exactly as reported. The shipped detector fired only on a string constant starting with `dev/`, `./dev/` or `../dev/`, and a green test asserted that `PROJECT_ROOT / "dev" / "conformance_baseline.json"` was deliberately not a violation. That inverted the real risk: a bare CWD-relative `open("dev/x.json")` breaks on the first run from any other directory and so is never written, while the `PROJECT_ROOT`-anchored join resolves perfectly in the repo checkout and fails only for wheel-installed users. `PROJECT_ROOT` is exported from the core paths module that the gate itself imports, so the working violation form was always one line away, and both this gate and the dev-side import scan stayed green on it.

The widened check was run over the live tree before the assertion was trusted, per the standing instruction not to harden first and measure after. The result on the shipped scope is zero, and the detector is provably live rather than blind: it finds 45 real dev references across the package, every one of them inside the wheel-excluded test trees, which is exactly where they are legitimate.

```
python files under src/cadrumo : 3724
shipped (wheel) modules        : 1402
excluded (test-tree) modules   : 2322

--- SHIPPED-SCOPE VIOLATIONS (gate asserts zero): 0 ---

--- WHOLE-PACKAGE HITS, no excludes (detector liveness): 45 ---
  cadrumo/tests/_inventory.py:34 [path_join] -> REPO_ROOT / 'dev'
  cadrumo/tests/_size_budget.py:72 [path_join] -> REPO_ROOT / 'dev'
  cadrumo/tests/test_dev_rename_audit_tools.py:31 [path_join] -> PROJECT_ROOT / 'dev'
  cadrumo/tests/test_import_hygiene_gate.py:104 [path_join] -> PROJECT_ROOT / 'dev'
  cadrumo/tests/test_no_skip_xfail.py:753 [literal] -> 'dev/tests/test_forbidden_skip_shapes.py'
  ... 40 further hits, all under cadrumo/tests/
```

That measurement was taken twice, at two different HEADs several peer commits apart (the package grew from 3723 to 3724 files between the runs as a peer landed a test module). The shipped count stayed at 1402 and the shipped violation count stayed at zero both times, which is what makes it a property of the tree rather than of one snapshot.

A differential probe ran the pre-fix predicate and the widened detector over identical planted bodies. Every realistic form was invisible before and is caught now, which is the mutation evidence that the new firing proofs would go silent if the widening were reverted.

```
FIRING PROOFS  - must be INVISIBLE to the old detector and CAUGHT by the new
[PASS] PROJECT_ROOT-anchored join (the realistic form)
    old detector: NO HIT  <- the hole
    new detector: [('path_join', 'PROJECT_ROOT / \'dev\' (path join onto "dev")')]
[PASS] os.path.join with a dev segment
    old detector: NO HIT  <- the hole
    new detector: [('call_join', 'join(...) with a "dev" path segment')]
[PASS] Path(...) factory with a dev segment
    old detector: NO HIT  <- the hole
    new detector: [('call_join', 'Path(...) with a "dev" path segment')]
[PASS] joinpath with a dev segment
    old detector: NO HIT  <- the hole
    new detector: [('call_join', 'joinpath(...) with a "dev" path segment')]
[PASS] f-string composed dev path
    old detector: NO HIT  <- the hole
    new detector: [('fstring', '/dev/conformance_baseline.json')]
[PASS] Windows separator literal
    old detector: NO HIT  <- the hole
    new detector: [('literal', 'dev\\conformance_baseline.json')]
[PASS] Windows relative-parent literal
    old detector: NO HIT  <- the hole
    new detector: [('literal', '..\\dev\\b.json')]
```

The near-miss half matters as much, because a detector that fires on everything would pass every firing proof above. The Spanish stems are pervasive in this codebase and a naive substring match on `dev` would have hit them; more sharply, shipped code in the secure-input module opens `/dev/tty` to read a secret without echo and is correct to do so, so a substring match would have reddened the gate on sound code and taught the next author to weaken it.

```
NEAR-MISS PROOFS - must be SILENT in the new detector
[PASS] /dev/tty (real shipped code: _secure_input.py:159)   -> silent
[PASS] /dev/null device sink                                -> silent
[PASS] devengada Spanish stem (path join)                   -> silent
[PASS] devengada Spanish stem (literal)                     -> silent
[PASS] devolucion Spanish stem (f-string)                   -> silent
[PASS] device/ (dev as a substring)                         -> silent
[PASS] locale key containing .dev.                          -> silent
[PASS] dev.example.com URL                                  -> silent
[PASS] "".join(parts) string operation                      -> silent
[PASS] ", ".join(["dev", "prod"]) label                     -> silent
[PASS] docstring naming a dev/ tool                         -> silent
[PASS] bare 'dev' string with no path context               -> silent

ALL PROOFS PASSED
```

The gate itself passes end to end, growing from 12 to 18 collected tests:

```
18 passed in 18.17s
=== PYTEST EXIT: 0 ===
```

Formatter, linter, and type checker are clean on the changed file (`ruff format --check`: already formatted; `ruff check`: all checks passed; `ty check`: all checks passed).

## Notes

Construction, not the read, is the trigger, and this is a deliberate ruling rather than an oversight. A reach is reported where the path is built, without requiring an adjacent open or read call, because demanding proof of a read would reopen the hole: a module constant assigned once and consumed elsewhere is exactly how the real baselines in the excluded test tree are written, and it would pass while depending on a dev artifact at runtime. A shipped module has no legitimate reason to name the dev tree at all.

One residual over-fire is documented in the detector rather than silently narrowed. A single-line non-docstring string that begins with a dev path, such as an assertion message, is still reported. Narrowing further by rejecting any value containing a space would let a path with a space through, and in a hard-zero boundary gate an over-fire costs a reword while an under-fire ships a broken wheel. Docstrings, which are the overwhelmingly common prose case, are skipped wholesale.

A mid-path `dev` segment in a hardcoded relative string is deliberately not matched; only a leading segment, after any relative markers, counts. Such a path cannot address the repo dev tree from any sane working directory, and the composition forms that could reach it are all covered by the join and f-string branches.

The related medium finding on duplicated detection was made safe but not resolved, as instructed. The import half of this module re-implements a detector the dev tree owns, and the two copies had already diverged: the shipped `conftest.py` case was proven on the dev side and missing here. That case is now mirrored so the two cannot disagree, and the module docstring records that the single-versus-dual authority question is deferred to an ADR ruling. Neither detector was deleted.

Two failures in the sibling import-hygiene gate are peer-owned and out of scope. They are the test-debt ratchet count and named-set assertions, both naming one file introduced by an unrelated sanitizer commit that imports a private symbol from the test inventory package. That is a different violation family from the dev boundary, the file is untouched in this working tree, and all six dev-tooling and shipped-boundary tests in that module pass. Reported rather than fixed, since editing an active peer campaign's files is out of bounds.
