---
tags:
  - '#plan'
  - '#error-code-registry'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-error-code-registry-adr]]"
  - "[[2026-04-25-error-code-registry-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
---



# `error-code-registry` `phase-a-foundation` plan

Implement issue #398 as the iteration-6 error foundation for the Kent-first
CLI: central registry, strict error envelope, shared CLI emission boundary,
static enforcement, generated documentation, and validation across lint,
types, tests, and hooks.

## Proposed Changes

Grounded by the 2026-04-25 ADR and research artifacts plus the 2026-04-24
iteration-6 reference, this work will:

- convert `aeat.core.errors` into a package with a public registry surface;
- bind a stable `ErrorCode` to every imported `AeatError` subclass;
- add envelope rendering, localization selection, and secret scrubbing;
- wrap Typer callbacks centrally from the CLI root while explicitly skipping
  `workflow run` and `workflow next`;
- add registry, envelope, decorator, and Windows encoding regression tests;
- generate `docs/error-codes.md` from the live registry and update the Kent
  coverage matrix;
- finish with the mandatory code-review pass and the four project gates.

## Tasks

- `Phase 1 - Registry foundation`
  1. Convert `aeat.core.errors` into a package and add the strict registry and
     envelope models.
  1. Replace direct base-exception holdouts that would bypass registry
     enforcement.
  1. Preserve the public `aeat.core.errors` import surface through re-exports.
- `Phase 2 - CLI boundary`
  1. Add the shared Typer callback error wrapper and stderr writer.
  1. Apply it from the CLI root to every command except `workflow run` and
     `workflow next`.
  1. Keep parser-time and full `--json` rollout concerns scoped for follow-on
     coordination with issue #399.
- `Phase 3 - Enforcement and regression tests`
  1. Add registry enforcement tests for subclass coverage, uniqueness, and dead
     categories.
  1. Add envelope tests for determinism, localization, and secret scrubbing.
  1. Add CLI boundary tests for human output, JSON output, stdout cleanliness,
     exit-code mapping, and Windows-safe encoding.
- `Phase 4 - Documentation and verification`
  1. Generate `docs/error-codes.md` from the live registry with a helper under
     `scripts/`.
  1. Update `docs/coverage/kent-capabilities.md`.
  1. Run mandatory code review plus `just lint`, `just typecheck`, `just test`,
     and `just hooks`.

## Plan Review

Review outcome: approved for execution with one explicit deferral.

- Scope matches issue #398 and the iteration-6 reference: registry first,
  envelope second, CLI wrapper third, tests/docs last.
- The plan respects the sibling branch boundary by not modifying
  `src/aeat/entrypoints/cli/workflow/run.py` or `src/aeat/entrypoints/cli/workflow/next.py` in this
  branch. Their decorator pass remains deferred until #393 merges.
- The trilingual contract is preserved through `default_message_es/en/hu`
  fields and runtime language resolution.
- The local workspace does not currently contain `.claude/rules/aeat-project-mandates.md`
  or `CLAUDE.md`; execution therefore relies on the issue instructions, the
  visible vaultspec rules, and the repo configuration that is present.
- Documentation scope is bounded: `docs/error-codes.md` and the single Kent
  capability row only. Those surfaces will use the required researcher ->
  author -> editor workflow.

## Parallelization

Registry and CLI exploration can proceed while the research artifact is being
written. Documentation work can run after the registry stabilises, using a
bounded researcher and author handoff. Final code review runs after code and
docs are complete.

## Verification

Success means:

- every imported `AeatError` subclass has a registered `ErrorCode`;
- every category in the iteration-6 taxonomy has at least one registered code;
- the CLI boundary emits human-readable stderr by default and deterministic
  JSON on stderr when a command exposes `--json`;
- stdout stays clean during error emission;
- secret-like context keys are redacted in both human and JSON forms;
- localized defaults resolve for `es`, `en`, and `hu`;
- non-ASCII error text does not raise under a simulated cp1252 stderr stream;
- generated documentation matches the live registry output;
- the mandatory reviewer finds no unresolved high-severity issues;
- `just lint`, `just typecheck`, `just test`, and `just hooks` all pass.
