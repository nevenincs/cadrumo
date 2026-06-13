---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W05.P15.S52'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W05.P15.S52 - Mirrored Official Data Security Disposition

## Scope

- `src/aeat/_data/SECURITY.md`

## Documentation Workflow

Used the `vaultspec-documentation` skill. The document is classified as a
reference note for maintainers and reviewers. Its wireframe is:

- title: bundled data security disposition;
- section: what classes of bundled data `_data` contains;
- section: required controls for private data, provenance, integrity metadata,
  and fixture labels;
- section: reviewer questions for legally sensitive data changes.

The scope is intentionally one page because this row documents a scan-policy
boundary, not a user workflow.

## Work

Added a root `_data` security disposition that explains why the tree is
excluded from production Semgrep, what classes of bundled data it contains, what
private data must never be committed there, and which provenance/integrity gates
remain authoritative for registry and corpus artifacts.

## Verification

- `rg -n "Security disposition for bundled data|Required controls|Review rule" src/aeat/_data/SECURITY.md`
- `uv run --no-sync pytest src/aeat/_data/corpus/test_corpus_provenance.py`
- `just audit-security`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Outcome

The documentation makes the S51 `.semgrepignore` exclusion reviewable without
weakening production security scanning. Existing dirty registry TOML work under
`src/aeat/_data` was not modified by this slice.

The corpus provenance gate passed with 2 tests. The production Semgrep lane
completed successfully and still reports 11 findings while scanning 891 tracked
files and skipping 17,241 files through `.semgrepignore`.
