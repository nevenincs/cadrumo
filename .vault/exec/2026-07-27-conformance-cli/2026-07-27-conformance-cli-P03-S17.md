---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S17'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add dev-side CLI behaviour tests covering every verb, the ratchet, the vacuity refusal, and the degraded-mode labelling

## Scope

- `dev/tests/test_registry_conformance_cli.py`

## Description

- Add 31 real-behaviour tests invoking the real CLI against the real bundled registry and
  the real writer against a byte copy of a shipped modelo tree.
- Cover `report`, `coverage`, `audit` and `stamp`, both output modes, the degraded read,
  both ratchet directions, the vacuity refusal, and every stamp refusal.
- Move the screens' vacuity warning into the manager so both its branches are testable
  against real report models instead of through a patched loader.
- Mark the module `unit` plus `hex_core`, matching the sibling dev CLI test modules.

## Outcome

No mocks, stubs, patches, skips, or xfail. Every subject is the real thing: the real Typer
app through `CliRunner`, the real registry authority, the real loader, the real schema, the
real committed baseline.

The proofs are written to FLIP AN ASSERTION rather than to kill a fixture. That distinction
is not stylistic — the first review round of this campaign found a sibling gate whose
mutation proof returned an empty set, which proved the function was CALLED and pinned none
of its semantics. Four proofs here are built the other way.

The ratchet is proved by moving ONE baseline counter and watching the same command on the
same tree change its exit code, in both directions with distinct violation kinds. Nothing
about the registry changes between the passing and failing runs, so only the comparison can
be what fails.

Absence-is-not-zero is proved by taking the real report, copying one row with
`independent_check_coverage` moved from `None` to `0.0`, rendering both, and asserting the
outputs differ on exactly one line — with the specific tokens named. A renderer that
collapsed absence onto zero produces identical text and this assertion fails. The paired
test asserts the validated read DOES measure the axes the degraded read withholds, so
`n/a` everywhere cannot pass as correct behaviour either.

The oracle attribution gap is proved by injection. The gap set is empty on the tree today,
so an assertion on the live count would pass whether or not anything consumed the field —
which is exactly the finding that opened Step S29. One real `UnattributedOraclePayload` is
constructed and projected through the real builder, and the test asserts it reaches all
three surfaces that must show it: the rendered `oracle_gap` row, the coverage axis
`measured` count, and a named ratchet violation. The clean report is asserted to show none
of the three.

The stamp rollback is proved by a reload that genuinely fails. A malformed sibling fragment
is written into the revision directory AFTER a first stamp has been shown to succeed, so
the failure lands in the post-write reload — the only place the restore can be exercised —
and the test asserts the manifest went back to its pre-second-stamp bytes. Without the
restore the manifest carries the second stamp and the assertion flips.

Registry-wide counts are asserted against the committed baseline's own floors, never
against literals. A hard-coded `90` would red on the next modelo revision and teach the
next reader to delete the assertion rather than read it.

The stamp tests deliberately never touch the shipped registry. Stamping a real revision
`agent_reviewed` would write a review claim nobody made, so a fixture copies the real
modelo 130 tree byte for byte into `tmp_path` and the writer is exercised there: real
fragments, real loader, real schema, and no fabricated provenance left in the repository.

Verification, actual pytest output:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py -q -n0 -m "unit or integration" --no-header
...............................                                          [100%]
31 passed in 35.69s
```

Selector coverage was checked rather than assumed. Under the repository's DEFAULT addopts
selector (`-m 'unit and not external_tool and not os_keychain'`) the module collects all of
its tests:

```
uv run --no-sync pytest dev/tests/test_registry_conformance_cli.py --collect-only -q -n0
28 tests collected in 2.39s
```

(28 at the time that collection was taken; three further identity-refusal cases landed
after it, giving the 31 above.) The module also collects under the `test-dev-tooling` lane
expression `-m "(unit or integration) and not resident_service"`, and `dev/tests` is
already named by that lane, so the dev-tree lane-coverage gate needs no change.

`ruff check`, `ruff format --check` and `ty check` are clean on the module and the package.

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction;
grounding was by whole-file reads and `rg`.

A peer has independently authored `dev/tests/test_registry_conformance_gate.py` for Step
S19, still untracked at the time of writing. It is complementary rather than duplicative:
that module invokes `audit --check` through a real subprocess and is marked `integration`
for the CI lane, while this one exercises every verb in process and is marked `unit`. It
was left untouched.

Two tests use `model_copy` on the frozen payload models to build the mutated inputs. That
is a deliberate construction of a real model instance, not a test double: the object handed
to the renderer is the same strict type the CLI renders, differing in exactly one field.
