---
tags:
  - "#plan"
  - "#relative-imports"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-relative-imports-adr]]"
  - "[[2026-04-17-relative-imports-research]]"
---

# relative-imports plan: enforce relative imports inside src/aeat/

Implementation plan for `[[2026-04-17-relative-imports-adr]]`. Single-
phase chore: lint config + mechanical codemod + docs update +
verification. No persistence, no schema, no domain logic.

Branch: `feature/162-relative-imports`
Issue: wgergely/aeat#162

## Phase 1 — relative-imports rollout

### Step 1 — write the codemod script

Create `scripts/_relative_imports_codemod.py` (one-shot tool, deleted
in step 6). Pure stdlib. Behaviour:

- Walk every `*.py` file under `src/aeat/`.
- For each file, compute its module path: split the path relative to
  `src/aeat/` and drop the `.py` (and the trailing `/__init__.py`
  segment when present).
- Read the file line-by-line (preserve exact bytes including trailing
  whitespace / mixed encodings if any).
- Match three line shapes with regex anchored at start of line:
  - `^from aeat\.(?P<dotted>[\w.]+) import (?P<rest>.+)$`
  - `^from aeat import (?P<rest>.+)$`
  - `^import aeat\.(?P<dotted>[\w.]+)(?P<asclause>(?: as \w+)?)$`
  - `^import aeat$`
- For each match, compute the dot-prefix needed to get from the
  current file's module path to the target. Algorithm:
  1. Let `here = file.parts_relative_to_src_aeat[:-1]` (the package
     directory path of the importing file). For `__init__.py`, the
     package directory is the file's parent without the file itself;
     for non-`__init__` files, drop the file stem.
  2. Let `target = ('aeat',) + dotted.split('.')` (or `('aeat',)`
     when `dotted` is empty).
  3. Compute the longest common prefix between `('aeat',) + here`
     and `target`.
  4. `up = len(('aeat',) + here) - len(common)`; `down =
     target[len(common):]`.
  5. The relative import prefix is `'.' * (up + 1)` (one dot for
     "current package" plus one for each level up). The remainder
     after the dots is `'.'.join(down)`.
- Rewrite shapes:
  - `from aeat.x.y import Z`  → `from {dots}{down} import Z`
  - `from aeat import Z`      → `from {dots} import Z` (grep
    confirms zero occurrences in current tree, but the script
    handles it for completeness)
  - `import aeat.x.y` (no `as`) → two-pass rewrite: (1) replace the
    import line with `from {dots}{parent_of_y} import y` (when
    `parent_of_y` is empty, emit `from {dots} import y`); (2) in the
    same file, rewrite every body reference of `aeat.x.y.<attr>` to
    `y.<attr>` via word-boundary regex
    (`\baeat\.x\.y\b` → `y`). Safe for the project's actual usage
    pattern (10 colocated smoke tests; see Risks below).
  - `import aeat.x.y as alias` → replace with
    `from {dots}{parent_of_y} import y as alias` (no body rewrite
    needed; alias already binds the local name).
  - `import aeat`             → grep confirms zero occurrences in
    `src/aeat/`. The script asserts this (aborts loudly if any
    appear) so we never silently corrupt `from . import *`-style
    rewrites.
- Write the rewritten file in-place. Preserve newline style by
  reading bytes and re-emitting with the original line terminator.
- Print a per-file summary (file path, count of rewrites) and a
  final aggregate count. Exit non-zero if any aborts occurred.

### Step 2 — dry-run the codemod

Run `uv run python scripts/_relative_imports_codemod.py --dry-run`
(the `--dry-run` flag prints the planned diff without writing).
Confirm:

- aggregate count matches the research's 1108 occurrences (small
  drift is acceptable if any commits landed during the chore — log
  the actual count).
- zero aborts; if any occur, fix the script or annotate the file in
  the plan as a manual exception.

### Step 3 — apply the codemod and run isort

```bash
uv run python scripts/_relative_imports_codemod.py
uv run ruff check --fix --select I .
```

The second command lets Ruff's isort pass re-sort any blocks where
relative and absolute imports were interleaved.

### Step 4 — update pyproject.toml

Edit `[tool.ruff.lint]`:

- Append `"TID251"` to `select` (do **not** add `"TID"` bare).

Add a new top-level block:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"aeat".msg = "Inside src/aeat/, use relative imports (e.g. `from .module import X`). Absolute `aeat.*` imports are allowed only in tests/ and scripts/."
```

Edit `[tool.ruff.lint.per-file-ignores]`:

- Change `"tests/**/*.py" = ["S101", "T20"]`
  → `"tests/**/*.py" = ["S101", "T20", "TID251"]`.
- Add `"scripts/**/*.py" = ["TID251"]`.

### Step 5 — sweep `.claude/`, `.vaultspec/`, `AGENTS.md`

Grep for `from aeat.\w+ import` patterns inside `.claude/`,
`.vaultspec/`, `AGENTS.md`, and any other agent-prompt or rule files.
Replace illustrative examples with the relative-import equivalent
(`from ..models import ModelCatalogue`) so future agents learn the
new convention. Do **not** rewrite import-instruction examples that
explicitly demonstrate cross-package imports from outside `src/aeat/`.

### Step 6 — update CLAUDE.md

Under `## Module Structure & API Rules`, add a new bullet between
*Public API Discipline* and *Types*:

> - **Relative-Imports Mandate**: Inside `src/aeat/`, every
>   internal `aeat.*` import MUST use relative syntax
>   (`from .module import X` or `from ..sibling import Y`).
>   Absolute `aeat.*` imports are allowed only in `tests/` and
>   `scripts/`. Enforced by Ruff TID251 — see
>   `pyproject.toml [tool.ruff.lint.flake8-tidy-imports.banned-api]`.

Update *Public API Discipline* to clarify the syntax:

> - **Public API Discipline**: Code outside a subpackage must
>   import only from the subpackage root (e.g., `from ..models
>   import ModelCatalogue` from another subpackage's interior, or
>   `from .models import ModelCatalogue` from a top-level
>   `src/aeat/*.py`).

### Step 7 — clean up

- Delete `scripts/_relative_imports_codemod.py` (one-shot tool).
- Confirm `git status` shows changes in: `pyproject.toml`,
  `CLAUDE.md`, and the bulk under `src/aeat/`.

### Step 8 — verification gate

Run, in order:

```bash
just lint
just typecheck
just test
```

All three must exit zero. If `just lint` reports new TID251
violations, the codemod missed a line shape — fix and re-run.
If `just typecheck` reports new errors, a relative import path is
wrong — fix and re-run. If `just test` fails, a converted import
broke at runtime — fix and re-run.

### Step 9 — boundary smoke test

- Add a stray `from aeat.core.config import Settings` to
  `src/aeat/entrypoints/cli/setup.py`, confirm `just lint` fails with the
  TID251 message, then revert.
- Add the same line to `tests/test_config.py`, confirm `just lint`
  stays clean, then revert.

Document both outcomes in the exec record.

### Step 10 — commit and PR

Commit with conventional-commits header:

```
chore(imports): enforce relative imports within src/aeat/

Refs #162
```

Open the PR via `gh pr create` with body summarising the artifacts
under `.vault/research/`, `.vault/adr/`, `.vault/plan/`,
`.vault/exec/`.

## Risks

- **Drift during execution**: another PR may merge and add new
  absolute `aeat.*` imports. Mitigation: rebase main into the branch
  before step 10, re-run the codemod over any changes, then re-run
  the verification gate.
- **`import aeat.x` statements (30 lines, 10 files)**: confirmed
  via grep — every `import aeat.X` lives in a colocated
  `test_smoke.py` and follows the pattern `import aeat.X` →
  `assert aeat.X.attr`. Step 1's two-pass rewrite handles them
  mechanically (rewrites the import to `from .. import X` and
  replaces `aeat.X.attr` body references with `X.attr`). The 10
  affected files are: `auth/test_smoke.py`, `casillas/test_smoke.py`,
  `cli/test_smoke.py`, `corpus/test_smoke.py`, `llm/test_smoke.py`,
  `models/test_smoke.py`, `portals/test_smoke.py`,
  `schema/test_smoke.py`, `storage/test_smoke.py`,
  `sync/test_smoke.py`. Step 2's dry-run prints the planned
  per-file rewrites; verify spot-checks before applying.
- **Pre-existing public-API-discipline violations**: cross-
  subpackage interior access converts as-is. Out of scope per the
  ADR; flag any egregious case in the exec record for follow-up.

## Rollback

`git restore` over `src/aeat/`, `pyproject.toml`, `CLAUDE.md`. The
codemod script is deleted in step 6 so there is nothing to remove
from the repo. The `.vault/` artifacts stay regardless.
