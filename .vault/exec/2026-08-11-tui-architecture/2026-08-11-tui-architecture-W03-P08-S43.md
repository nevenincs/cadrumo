---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f8d23866d18299f1cd7b2b88aaf84a5e4b7d4fe23d5940a6bbc6b9357544885e'
step_id: 'S43'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose profile mutation and lifecycle operation definitions through the user-profile application facade

## Scope

- `src/cadrumo/application/user_profile/__init__.py`

## Description

Audit the lazy user-profile facade against the canonical operation-definition owner.
Confirm both builders have one lazy owner mapping and production composition imports them only through the public facade.
Restore canonical ordering of the builder exports without adding eager imports, aliases, shims, or duplicate definitions.

## Outcome

- The lazy facade exposes `build_user_profile_operation_definitions` and `build_user_profile_operation_registrations` from `._operation_definitions`.
- Each builder has one lazy manifest entry and one public export entry.
- Production composition consumes the facade and does not import the private owner.
- No eager-load regression, compatibility bridge, or operation redeclaration was introduced.

## Verification

- `uv run pytest -q -m integration src/cadrumo/application/user_profile/tests/test_operation_definitions.py src/cadrumo/entrypoints/tests/test_operation_composition.py`: 12 passed.
- Lazy-boundary and censal-facade unit proofs: 5 passed.
- `uv run ruff check src/cadrumo/application/user_profile/__init__.py src/cadrumo/application/user_profile/_operation_definitions.py`: passed.
- `git diff --check -- src/cadrumo/application/user_profile/__init__.py`: passed.
- Independent read-only review: approved with no findings; live RAG and exact census found one owner, one mapping/export per builder, zero foreign private-owner consumers, and fresh-process proof that the lazy owner remains unloaded until resolution.

## Notes

The owner and lazy facade mappings already existed after the production-composition cohort. This step completes their public-facade and style evidence without re-declaring the operation population.
