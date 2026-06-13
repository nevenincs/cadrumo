---
tags:
  - "#adr"
  - "#relative-imports"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-relative-imports-research]]"
---

# relative-imports adr: enforce relative imports inside src/aeat/ (**status:** `accepted`)

Date: 2026-04-17
Branch: `feature/162-relative-imports`
Issue: wgergely/aeat#162

## Status

Accepted (autonomous self-review, 2026-04-17). Executed end-to-end per
the vaultspec-system mandate; no human-in-the-loop. Code review
recorded in the matching exec summary.

## Problem Statement

`src/aeat/` mixes two import styles for its own modules: 1108
absolute occurrences (`from aeat.x.y import Z`) across 399 files, and
262 relative occurrences (`from .y import Z`) across 88 files.
The split is historical drift, not deliberate — every subpackage
contains both shapes. This costs us:

- **Relocatability** — moving a subpackage requires hunting every
  absolute reference; relative imports survive a directory move.
- **Cohesion** — absolute imports inside a subpackage hide the
  cohesion graph; reviewers cannot see "this is a sibling" at a
  glance.
- **Discipline drift** — without a lint rule, every PR can quietly
  reintroduce the absolute style. The repo currently has no
  mechanical guard.

#162 chooses to standardise on **relative imports inside `src/aeat/`**
and add a Ruff rule that fails any future absolute `aeat.*` import
inside the package tree.

## Considerations

- **Boundary respect**: `tests/` and `scripts/` live outside the
  package and must continue using absolute `aeat.*` imports.
- **Colocated tests**: `test_*.py` and `_test_*.py` files inside
  `src/aeat/` are part of the package per the existing
  *Rust-style colocated tests* pattern (CLAUDE.md), so they convert
  alongside production code.
- **Public-API discipline preserved**: the existing CLAUDE.md rule
  *"Code outside a subpackage must import only from the subpackage
  root"* survives unchanged in spirit; only the syntax shifts from
  `from aeat.domain.modelos import X` to `from ..models import X` (or
  `from .models import X`, depending on caller depth).
- **Ruff rule selection**: there is no built-in rule that *requires*
  relative imports. The closest fit is **TID251 (`banned-api`)** with
  `aeat` registered as a banned dotted-prefix and a per-file ignore
  for `tests/**/*.py` and `scripts/**/*.py`. The whole `TID` family
  must NOT be selected because TID252 would fire on the relative
  imports we are introducing.
- **Codemod determinism**: the dot-count for any conversion is purely
  a function of (file path, import target). A tiny one-shot Python
  script can compute it without AST manipulation by line-based
  regex on `^from aeat\.` and `^import aeat\.`.
- **Pre-existing violations**: a few files reach into another
  subpackage's private modules (e.g.,
  `from aeat.application.sync._wire import X` from outside `aeat/application/sync/`). These
  already violated the public-API discipline. Out of scope for #162;
  converted as-is.
- **No runtime behaviour change**: relative-vs-absolute does not
  change Python's import graph; circulars (none today) cannot be
  introduced by mere syntax conversion. Verification is the existing
  `just lint && just typecheck && just test` gate.

## Decision

1. **Adopt Ruff TID251** as the enforcement mechanism inside
   `src/aeat/`.

2. **Update `pyproject.toml [tool.ruff.lint]`**:
   - Add `"TID251"` to `select` (do **not** add bare `"TID"`).
   - Add a `[tool.ruff.lint.flake8-tidy-imports.banned-api]` block
     with `aeat` banned and a clear `msg`.
   - Extend `[tool.ruff.lint.per-file-ignores]`:
     `"tests/**/*.py"` adds `"TID251"` (alongside existing
     `"S101", "T20"`); add `"scripts/**/*.py" = ["TID251"]`.

3. **Convert every absolute `aeat.*` import inside `src/aeat/`** to
   the equivalent relative import via a deterministic line-based
   codemod. Cover every `.py` file under `src/aeat/`, including
   colocated tests (`test_*.py`, `_test_*.py`).

4. **Leave absolute imports untouched** in:
   - `tests/**/*.py`
   - `scripts/**/*.py`
   - any `pyproject.toml`/manifest string references (e.g.,
     `[project.scripts] aeat = "aeat.entrypoints.cli:app"`).

5. **Update `CLAUDE.md`**:
   - Under *Module Structure & API Rules*, add a "Relative-Imports
     Mandate" bullet stating the rule and pointing at TID251.
   - Keep the existing *Public API Discipline* bullet; clarify
     that the syntax for cross-subpackage imports is now relative
     (`from ..models import ModelCatalogue` from elsewhere inside
     `src/aeat/`).

6. **Verification gate**: the issue's acceptance criterion is
   `just lint && just typecheck && just test` passing cleanly on
   Windows and Unix. CI runs on PR open per the project's GitHub
   Actions workflow.

7. **isort interplay**: keep the existing `"I"` selector enabled. The
   codemod preserves import-block ordering line-for-line; Ruff's `I`
   (isort) pass after the conversion re-sorts any block where relative
   and absolute imports were interleaved. Run `uv run ruff check
   --fix .` once after the codemod to settle ordering, then re-run
   the verification gate.

## Out of Scope

- Fixing pre-existing public-API-discipline violations (cross-
  subpackage interior access). Converted as-is; tracked separately.
- Touching `tests/` or `scripts/` imports.
- Reorganising any module layout; this chore changes import syntax
  only.
- Running `isort`/`I` rule autofix on the converted files beyond
  Ruff's normal post-conversion pass.

## Consequences

**Positive**:
- Subpackages become relocatable without import-graph rewrites.
- Future absolute `aeat.*` imports inside `src/aeat/` fail CI on
  the very first PR that introduces them.
- Cohesion graph reads off the syntax: `from .x` is sibling,
  `from ..x` is uncle/aunt.

**Neutral**:
- Diff size is large (~1108 lines) but mechanical; reviewers can
  spot-check and trust the codemod.
- Open PRs touching `src/aeat/` will rebase through this change and
  will likely need to convert any new absolute imports they add.

**Negative**:
- A new contributor unfamiliar with relative imports may produce
  PRs that fail TID251 once. The error message documents the rule
  and the fix is mechanical.
- TID251's `banned-api` semantics are slightly off-label here (it's
  designed for "stop using `os.system`, use `subprocess`"); the
  custom `msg` makes the intent clear.

## Verification

- `just lint` (`uv run ruff check .`) reports zero TID251 violations.
- `just typecheck` (`uv run ty check src tests`) passes.
- `just test` (`uv run pytest`) passes.
- **Positive boundary check**: introduce a stray
  `from aeat.core.config import Settings` in `src/aeat/entrypoints/cli/setup.py`;
  confirm Ruff fails with the TID251 message; revert.
- **Negative boundary check**: introduce the same stray line in
  `tests/test_config.py`; confirm Ruff stays clean (per-file-ignore
  for `tests/**/*.py` covers TID251); revert.
