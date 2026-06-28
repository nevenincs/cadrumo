---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S19'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# run local pre-commit and check-all validations to verify harness health

## Scope

- `justfile`
- `scripts/audit_complexity.py`
- `scripts/audit_semantic.py`
- `pyproject.toml`

## Description

- Fixed `_renta_ledger.py` module docstring lines 6-7: wrapped cross-references to stay under the 120-character line limit, resolving pre-existing E501 warnings.
- Fixed `_ledger_filing_snapshot.py` module docstring line 21: removed `# noqa: E501` inline suppression by wrapping the `LedgerFilingStalenessVerdict` cross-reference across two lines.
- Fixed `scripts/audit_complexity.py`: removed unused `os` import, renamed ambiguous generator variable `l` to `ln`, and placed `# noqa: S603` / `# noqa: S607` suppression comments on the exact subprocess lines that trigger each diagnostic.
- Applied `ruff format` to 18 files that had accumulated formatting drift during the campaign (conftest files, registry modules, audit scripts).
- Added `torch` to the deptry `DEP002` ignore list in `pyproject.toml`: `torch` is a direct project dependency required by the resident vaultspec-rag semantic search service and is not imported inside `src/aeat`, making this a known-correct false positive.

## Verification Results

| Gate | Result | Notes |
|---|---|---|
| `check-style` | ✅ pass | All ruff checks passed |
| `check-format` | ✅ pass | 2241 files formatted |
| `check-imports` | ✅ pass | 4 architectural contracts kept, 0 broken |
| `check-relative-imports` | ✅ pass | exit 0 |
| `check-dependencies` | ✅ pass | No dependency issues found |
| `check-semantic` | ✅ pass | `no semantic leak violations detected` |
| `check-types` (ty + pyright) | ⚠️ pre-existing | 2391 diagnostics across adapter/test files not touched by this campaign; present at HEAD before campaign |
| `check-pre-commit` (prek) | ⚠️ pre-existing | Fails on same `ty check src/` diagnostics; hook was already failing at HEAD |
| `audit-complexity` | ℹ️ informational | Correctly reports pre-existing cyclomatic and cognitive complexity violations; zero-noise filtered output working as designed |

## Outcome

All checks owned by this campaign pass. Pre-existing `ty check` failures across adapter and test boundary files are not introduced by this campaign and remain open work for other campaigns.
