---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:886880eed05300240e212ee151cdb90c42ce491b093ed761ae6673185114683d'
step_id: 'S159'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose through the canonical registry facade a registry-native atomic capture of the law-selected inspection or snapshot and its process-incarnation-local ABA-safe monotonic generation, plus current-generation validation, without any ModeloWorkspace dependency, alternate loader, private grammar, shim, alias, fallback, or re-export bridge

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `and focused authority concurrency/reset tests`

## Description

- Ground the registry capture surface in the approved architecture plan, registry API gate amendment, S126 record, and S128 composition reference before changing the canonical authority.
- Add one frozen `RegistryAuthorityCapture` record and one `capture_law_selected_projection` authority operation that preserves the existing inspection-or-graded-snapshot choice, captures under the authority lock, and isolates the returned projection from the authority cache.
- Allocate generations only for authority incarnations; invalidate old native capture coordinates on every cache reset so a stale authority cannot relabel an old A state as a current A state after reset.
- Promote `RegistryAuthorityCapture` through the canonical registry package facade and add focused public-facade, concurrency, isolation, reset, ABA, and no-Workspace/one-home tests.

## Outcome

The registry owns one public native capture/current-generation surface. Cache warmup and validation bookkeeping leave its generation stable; a reset invalidates the old instance and a newly loaded authority receives a strictly later generation. No lower-layer Workspace type, alternate loader, projection adapter, or alternate capture home was introduced.

## Verification

- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_authority.py src/cadrumo/domain/calculations/registry/__init__.py src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
- `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
- `uv run --no-sync pytest -q -o addopts= src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
- Final exact census: one production definition of `RegistryAuthorityCapture`, one production `capture_law_selected_projection` home in `._authority`, one canonical `__init__` promotion, and zero `ModeloWorkspace` mentions in the registry authority or facade.

## Notes

The shared worktree advanced while this Step was in progress. The source and facade edits were swept into concurrent commit `8c845ab92f`; this Step does not amend, rewrite, or restage that commit. Its focused tests and traceability record land separately.
