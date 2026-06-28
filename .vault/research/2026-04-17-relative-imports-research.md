---
tags:
  - "#research"
  - "#relative-imports"
date: 2026-04-17
modified: '2026-04-17'
related: []
---

# relative-imports research: enforce relative imports inside src/aeat/

Foundational research for Issue #162 (`area:config`, `domain:infra`,
`type:chore`). Inventories every absolute `aeat.*` import inside
`src/aeat/`, identifies the boundaries that must remain absolute
(`tests/`, `scripts/`), and surveys Ruff's `flake8-tidy-imports` plugin
to pick a concrete enforcement mechanism. Output feeds the relative-
imports ADR that selects the lint rule, defines the per-file-ignore
matrix, and locks in the codemod strategy.

## Methodology

Read-only research. Sources: (1) `git ls-files` walk over `src/aeat/`,
`tests/`, and `scripts/` with regex grep for `^from aeat[. ]` and
`^import aeat`, (2) the existing `[tool.ruff]` block in
`pyproject.toml`, (3) existing `CLAUDE.md` "Public API Discipline" rule,
(4) Context7-fetched Ruff documentation on `flake8-tidy-imports`
(`/astral-sh/ruff`, queried 2026-04-17), (5) prior-art ADRs under
`.vault/adr/` for the project's pattern of selecting individual Ruff
rules. No code changes during research.

## Findings

### 1. Absolute-import inventory

Counted with `rg -n '^(from aeat[. ]|import aeat)'`:

| Tree                | Files | Occurrences | Disposition          |
| :------------------ | ----: | ----------: | :------------------- |
| `src/aeat/**/*.py`  |   399 |        1108 | **Convert** to relative |
| `tests/**/*.py`     |     3 |           4 | **Keep absolute**    |
| `scripts/**/*.py`   |     2 |          10 | **Keep absolute**    |

Existing relative imports inside `src/aeat/`: 262 occurrences across 88
files — adoption is partial; this chore brings the rest in line.

### 2. Subpackage map (src/aeat/)

Top-level modules and subpackages under `src/aeat/`:

- root modules: `__init__.py`, `_paths.py`, `_test_auth.py`,
  `_test_env_io.py`, `config.py`, `env_io.py`, `errors.py`,
  `logging.py`, `py.typed`
- subpackages: `auth/`, `browser/`, `casillas/`, `cli/`, `corpus/`,
  `deadlines/`, `filing/`, `financial/` (with `categories/`,
  `invoices/`, `providers/`, `transactions/`, `vat/`),
  `i18n/`, `inbox/`, `justificante/`, `llm/`, `manuals/`, `mcp/`,
  `models/`, `normatives/`, `portals/`, `schema/`, `setup/`,
  `status/`, `storage/`, `submission/`, `sync/`, `testing/`,
  `workflow/`

Every subpackage `__init__.py` re-exports its public API per the
existing CLAUDE.md "Public API Discipline" rule
(*Code outside a subpackage must import only from the subpackage root*).

### 3. Conversion shapes

Three shapes covering all 1108 occurrences:

- **Same-package sibling**:
  `from aeat.application.sync._wire import X` inside `src/aeat/application/sync/_runner.py`
  → `from ._wire import X`

- **Same-package nested**:
  `from aeat.domain.financial.transactions._models import X` inside
  `src/aeat/domain/financial/transactions/_service.py`
  → `from ._models import X`

- **Cross-subpackage** (importing a sibling subpackage from another
  subpackage's interior):
  `from aeat.core.config import Settings` inside `src/aeat/entrypoints/cli/setup.py`
  → `from ..config import Settings`

  `from aeat.domain.modelos import ModelCatalogue` inside
  `src/aeat/entrypoints/cli/modelos/__init__.py`
  → `from ...models import ModelCatalogue`

The dot-count equals the file's depth below `src/aeat/` minus the
common-ancestor depth with the imported module. A mechanical codemod
can compute this from the source file path and the module path.

### 4. Boundary cases that must remain absolute

- **`tests/` (project root)** — outside the package; pytest discovers
  via `pythonpath = ["src"]`. 4 occurrences across 3 files
  (`tests/test_config.py`, `tests/test_docs.py`,
  `tests/live/test_google_fixtures_smoke.py`).

- **`scripts/`** — entry-point scripts run with `uv run python
  scripts/...py`; they execute outside the `aeat` namespace.
  10 occurrences across `scripts/provision_google_fixtures.py` and
  `scripts/teardown_google_fixtures.py`.

- **`pyproject.toml [project.scripts] aeat = "aeat.entrypoints.cli:app"`** — string
  reference, not an import statement. Unaffected.

### 5. Colocated tests inside src/aeat/

Per CLAUDE.md: *Unit tests live inside each module's directory
(Rust-style colocated tests)*. Files matched by `test_*.py` and
`_test_*.py` under `src/aeat/` are part of the package and **MUST**
adopt relative imports too — they were created to be cohesive with
their module of test, and adding them to the converted set keeps the
boundary consistent: "everything inside `src/aeat/` is relative,
everything outside is absolute".

### 6. Ruff enforcement mechanism

Ruff exposes the `flake8-tidy-imports` plugin under the `TID` selector:

| Rule    | Name                       | Direction                                          |
| :------ | :------------------------- | :------------------------------------------------- |
| `TID251`| `banned-api`               | Forbids configured dotted names                    |
| `TID252`| `relative-imports`         | **Bans** relative imports (parents/all)           |
| `TID253`| `banned-module-level-imports` | Forbids configured imports outside functions    |

The issue text references "TID252 set to prefer relative imports".
This is the **opposite** of the rule's actual behaviour: TID252 with
`ban-relative-imports = "parents"|"all"` *forbids* `from .` /
`from ..` imports. There is no built-in Ruff rule that *requires*
relative imports inside a package.

The closest fit is **TID251 (`banned-api`)** with `aeat` registered as
a banned dotted-prefix and a per-file ignore for `tests/` and
`scripts/`:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"aeat".msg = "Use relative imports inside src/aeat/."

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py"   = ["TID251"]
"scripts/**/*.py" = ["TID251"]
```

`banned-api` does dotted-prefix matching: `aeat` blocks `import aeat`,
`from aeat import X`, `from aeat.foo import Y`, and
`from aeat.foo.bar import Z`. Per-file-ignore disables TID251 for the
two boundary trees.

**Critical**: do not select the whole `"TID"` family — that pulls in
TID252 which would flag every `from .` import we are about to write.
Pin the selection to `"TID251"` exactly.

### 7. Existing Ruff configuration

`pyproject.toml` selects `["E","W","F","I","N","UP","B","S","T20","SIM","RUF"]`
with `target-version = "py313"`, `line-length = 120`,
`src = ["src", "tests"]`. Per-file-ignores already exist for
`tests/**/*.py = ["S101", "T20"]` plus several `src/aeat/**` cases.
The new TID251 entries slot into that block without churn.

`scripts/**/*.py` has **no** existing per-file-ignore. We add one for
`TID251`.

### 8. CLAUDE.md alignment

The existing rule *"Code outside a subpackage must import only from
the subpackage root (e.g., `from aeat.domain.modelos import ModelCatalogue`)"*
is unchanged in spirit. Under the new mandate the same example becomes
`from ..models import ModelCatalogue` when invoked from
`src/aeat/<other_subpackage>/...`, or `from .models import ...` when
invoked from a top-level `src/aeat/*.py`. The discipline (subpackage-
root imports only) survives; only the syntax shifts.

### 9. Potential blockers

- **`__init__.py` re-exports**: many subpackage `__init__.py` files
  re-export `from aeat.<self>.<module> import X`. These rewrite cleanly
  to `from .<module> import X`.

- **Cross-subpackage interior access**: a few files reach into another
  subpackage's private modules (e.g.,
  `from aeat.application.sync._wire import X` from outside `aeat/application/sync/`). These
  already violate the public-API discipline. **Out of scope** for
  #162 — convert as-is to `from ..sync._wire import X`. A separate
  audit may file follow-ups.

- **Type-checking under `ty`**: `ty` resolves both relative and
  absolute imports for `src`-layout projects. Ruff docs confirm
  relative imports work when `pyproject.toml` is the package root.
  No `ty` configuration changes required.

- **Circular imports**: relative-vs-absolute does not change Python's
  import graph. If circulars exist today, they continue to exist; if
  not, conversion does not introduce them. Verification is `just lint
  && just typecheck && just test`.

## Recommendation

Adopt **Ruff TID251 with `aeat` banned and `tests/`/`scripts/`
per-file-ignored** as the enforcement mechanism, and execute a
mechanical codemod over `src/aeat/**/*.py` to convert all 1108
occurrences using path-relative dot-count computation. Update
`CLAUDE.md` "Module Structure & API Rules" to add a "Relative-Imports
Mandate" bullet pointing at the new lint rule.
