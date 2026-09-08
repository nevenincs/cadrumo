---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:fe1eb6e76c7e75f6846935adf26a487318421220d966dd54acdb132a7c1558e9'
step_id: 'S115'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Deliver the both-locales condition over the locale detector's hit set as a parameterised re-run rather than a CI lane, since flipping the ambient locale only mirrors the vacuity and cannot reach a test that pins its own locale, and demonstrate it failing first -- preferring the live residual instance, else seeding synthetic in-memory source or an isolated fixture, never the shipped tree (Terra xhigh fixes and refactors)

## Scope

- `dev/quality/locale_bound_assertions.py`
- `dev/quality/tests/fixtures/locale_axis_blind.py.fixture`
- `dev/quality/tests/fixtures/locale_bound_assertions.fixture`
- `dev/quality/tests/test_locale_bound_assertions.py`

## Changes

- Extended pin-state analysis only where the runtime axis exposed false provenance: method results inherit pinning only from their receiver, non-call expressions require every named input to be pinned, and environment aliases retain their declared state.
- Added a non-collected planted runtime fixture whose English-only absence assertion passes under `es` and fails under `en`.
- Mapped detector locations to exact top-level or class-method pytest node IDs and reran each affected node under both `CADRUMO_OUTPUT_LANGUAGE=en` and `CADRUMO_OUTPUT_LANGUAGE=es`.
- Cleared the repository's default marker expression with `-m ""` for real nodes. A positive control executes an integration-marked repository node and requires `1 passed` with no `deselected` result, so removal of the override fails the gate.
- Added focused controls for every behavioral mutation found in declaration diagnostics, helper return traversal, named output propagation, method-receiver propagation, and direct or forwarded environment propagation.

## Failure demonstration

Before repairs, the complete four-catalogue sweep failed in both parameterised directions: the Spanish axis exposed seven English-only absence assertions and the English axis exposed one Spanish-only absence assertion. The runtime fixture separately proves the execution mechanism bites: `es` exits zero, while `en` exits nonzero with `AssertionError`. No defect was planted in the shipped Python tree.

An independent repository-node probe also exposed a defect in the first runtime implementation: the configured default marker collected but deselected an integration node and exited one. With the explicit empty marker expression, that same exact node executed and passed. The committed positive control protects this branch.

## Verification

- `uv run pytest dev/quality/tests/test_locale_bound_assertions.py -q -m "" -n 0` -> `63 passed in 45.56s`.
- `uv run ruff check dev/quality/locale_bound_assertions.py dev/quality/tests/test_locale_bound_assertions.py` -> pass.
- `uv run ruff format --check dev/quality/locale_bound_assertions.py dev/quality/tests/test_locale_bound_assertions.py` -> pass; two files already formatted.
- `uv run ty check dev/quality/locale_bound_assertions.py dev/quality/tests/test_locale_bound_assertions.py` -> pass.
- Banned-mock scan over the implementation and test returned no matches.

## Mutation proof

A fresh full run against the exact current detector, gate, and fixture hashes selected 475 mutants, killed 452, and left 23 survivors in 597.38 seconds. Every survivor was reviewed individually. All are semantically inert: falsey `None`/`False` defaults consumed only through truth tests; non-absence polarity labels filtered identically; equal-length parsed AST dictionary sequences under alternate strictness; a valid joined-string AST branch; fixed-point sentinel equivalents; the case-equivalent `UTF-8` codec spelling; or parser-filename-only diagnostics. No behavior-changing survivor remains, no aggregate percentage is used as a pass condition, and the external `/tmp` scratch was removed.

## Boundary

S115 delivers and proves the both-locales condition. S116 separately owns the shipped assertion repairs that make the live hit set empty; this record does not claim those repairs.
