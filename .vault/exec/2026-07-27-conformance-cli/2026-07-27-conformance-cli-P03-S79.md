---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:a2ab3f46fac9612f0c1d5f00a09e3233ea50356dfd91cf6743a35f949dd789fb'
step_id: 'S79'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# retire the dev registry matrix package whose manager recomputes ten capability fields the public build_support_matrix already returns on ModeloEntry, sweeping its test-lane entry, its tests, the two shipped docstrings that cite it as their mirror and the planted-import fixtures naming it

## Scope

- `dev/registry/matrix`
- `justfile`
- `dev/registry/conformance/__init__.py`
- `dev/registry/conformance/cli.py`
- `src/cadrumo/domain/calculations/registry/_support_matrix.py`
- `src/cadrumo/domain/calculations/registry/tests/test_support_matrix.py`
- `src/cadrumo/tests/test_dev_path_isolation.py`

## Description

- Sweep the whole tree for the package path, the dotted module name and all
  three exported symbols before deleting anything, rather than trusting the
  inherited list.
- Delete the package and its bytecode residue.
- Drop its entry from the developer test lane.
- Re-point the two sibling citations in the surviving dev CLI at surfaces that
  exist.
- Reverse the two shipped docstrings that named dev scaffolding as their origin
  of truth.
- Retarget the boundary gate's planted-import fixtures at a surviving dev module
  and prove the retarget keeps the detector armed.
- Confirm nothing dangles: sweep again, and confirm the module no longer
  imports.

## Outcome

### The sweep found more than the row listed, and one item the row got backwards

The row named four things to sweep. The sweep found seven files outside the
package, and the extra ones are the interesting ones.

The two SHIPPED docstrings were the sharpest. The support-matrix module said its
capability detection "mirrors `dev.registry.matrix`", and the support-matrix TEST
module said it "mirrors the coverage shape of
`dev/registry/matrix/tests/test_manager.py`". Neither is an import and neither is
a runtime path read, so the boundary gate this campaign hardened does not fire on
either — but a shipped module naming developer scaffolding as its origin of truth
is that boundary stated backwards, and it had a concrete cost: the two docstrings
declared each OTHER as mirrors, so a reader arriving at either was told the
authority was somewhere else, in a loop. Both now state where the predicates are
proved. A third instance of the same shape sat inside a test docstring, crediting
the retired module's manager tests with the dormant-modelo enumeration; it is now
described as what it is, the registry's own set read off the tree.

The planted-import fixtures were the subtlest. They name the retired module as a
STRING inside synthetic files written to a temporary directory, so they keep
passing after the deletion — passing while naming a module that does not exist,
which is exactly the kind of reference that survives long enough to mislead
somebody. They are retargeted at the surviving conformance package.

The row also listed "its tests" as a sweep target, which understates it: the
tests were deleted with the package, but the developer test LANE in the task
runner still named their directory, and a lane naming a path that no longer
exists is a broken recipe rather than a stale comment.

### Why retire rather than delegate

The ruling was taken and recorded in a prior Step; this one carried it out and
re-verified its premise against the tree rather than assuming it. Every one of
the retired manager's ten fields is produced by the shipped `build_support_matrix`
on `ModeloEntry` from the same primitives and by the same expressions, including
the latest-revision selection helper and both export-format membership tests. Its
single `report` verb rendered a table the operator support-matrix verb already
renders from the shipped authority, and the conformance `report` verb already
carries the same probe for every revision as a strict superset — with a
registry-root flag and row-level degraded-mode labelling the matrix had neither
of.

Delegation would have closed four of the ten fields and left the latest-revision
selection — the axis the whole matrix is keyed on — still forked on the dev side,
and the per-revision fold it would have delegated to carries no extractor boolean
at all, only a count, so two fields could not have been sourced from it.

### Verification

The retirement's own proof is that nothing dangles, so the sweep is the
assertion. Run after the deletion, over the whole tree including hidden files and
excluding only the git database and the decision corpus:

```
rg 'dev\.registry\.matrix|dev/registry/matrix|build_capability_matrix|
    ModeloCapabilityRow|render_matrix_table' .
EXIT=1   (ripgrep: no matches)

python -c "import importlib.util as u; print(u.find_spec('dev.registry.matrix'))"
dev.registry.matrix importable: False
```

The one change that could silently disarm something is the fixture retarget, so
it carries a mutation. Pointing the planted import off the dev family entirely
makes the scanner find nothing, and the assertion flips:

```
E   AssertionError: the scanner failed to catch a planted static dev import; it detected []
E   assert [] == [('cadrumo/shipped_module.py', 'dev.registry.conformance', False)]
FAILED ...::test_import_scanner_catches_planted_static_dev_import
1 failed in 25.67s
```

Reverted, and the whole boundary gate re-verified:

```
uv run --no-sync pytest src/cadrumo/tests/test_dev_path_isolation.py -q --no-header
23 passed in 65.82s (0:01:05)

uv run --no-sync pytest src/cadrumo/tests/test_dev_path_isolation.py \
    src/cadrumo/domain/calculations/registry/tests/test_support_matrix.py -q --no-header
32 passed in 131.11s (0:02:11)
```

Full-tree collect after the retirement, and the generated stubs:

```
uv run --no-sync pytest --collect-only -q src/cadrumo dev
16285/20063 tests collected (3778 deselected) in 146.87s (0:02:26)

uv run --no-sync python -m dev.docs.apidocs scaffold --check  -> exit=0
Stub tree is conformant. No drift detected.
```

No source module was added or removed under `src/cadrumo`, so no stub delta was
expected and none appeared; the check was run to confirm that rather than to
assume it.

Style and lint on every touched file:

```
uv run --no-sync ruff check ...           -> All checks passed!
uv run --no-sync ruff format --check ...  -> 8 files already formatted
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. It was neither
started, restarted, reindexed nor probed. Grounding was whole-file reads of the
retired package and of the shipped authority it forked, plus ripgrep sweeps over
the whole tree — including the task runner, the packaging manifest, the CI
workflows and the two audit baselines, none of which named the package.

The package was removed with `git rm -r`, which stages the deletion; the
untracked bytecode directories left behind were removed by path after the tracked
files were gone, and the now-empty directories with them. No recursive delete was
run against a path holding tracked content.

INCIDENT, and it cost about fifteen minutes. Staging the retirement failed on a
`.git/index.lock` left by a peer. Elapsed time cannot distinguish residue from
contention, so the lock was characterised with an exclusive `CreateFileW` open
with the share mode set to zero: the open succeeded, which means no process held
a handle. The file was zero bytes and eleven minutes old. It was removed only
after re-running the handle test and confirming the size and modification time
had not moved between the check and the removal, so a peer starting a genuine git
operation in the interval would have aborted the removal rather than lost its
lock. Waiting it out was rejected because the retirement's deletions were already
staged in the shared index, where a peer's pathspec-less commit would have swept
them.

Peer campaigns landed work throughout, including on the registry schema and
verification-predicate modules. The staged set was diffed immediately before the
commit and carried only this Step's hunks across seven files plus the seven
deletions.
