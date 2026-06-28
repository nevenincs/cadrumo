---
tags:
  - "#adr"
  - "#ci-github-actions"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-ci-github-actions-research]]"
---
# ADR: GitHub Actions CI Workflow

## Status

Proposed

## Context

The project currently lacks automated CI, relying on manual verification by developers. This leads to cross-platform parity issues and lack of verification records on PRs.

## Decision

We will implement a GitHub Actions workflow in `.github/workflows/ci.yml` with the following characteristics:

### 1. Matrix & Platform

- **Runners**: `ubuntu-latest` and `windows-latest`.
- **Python**: `3.13`.
- **Reasoning**: Ensuring cross-platform parity is critical, as Windows is the primary dev platform but deployment may target Linux.

### 2. Tools & Actions

- **`astral-sh/setup-uv@v5`**: For `uv` and Python management.
  - `enable-cache: true` for automatic `uv` environment caching.
- **`taiki-e/install-action@just`**: For `just` installation.
- **`actions/checkout@v4`**: For source checkout.
- **`actions/cache@v4`**: For `prek` environment caching.

### 3. Workflow Steps

1. **Checkout**: Source code.
2. **Setup just**: Using `taiki-e/install-action`.
3. **Setup uv**: Using `astral-sh/setup-uv` (Python 3.13).
4. **Cache prek**: Using `actions/cache` on the `prek` cache directory.
   - Ubuntu: `~/.cache/prek`
   - Windows: `~\AppData\Local\prek`
5. **Bootstrap (CI variant)**:
   - `uv sync`
   - `uv run vaultspec-core install --upgrade`
   - `just env-setup` (non-interactive provision of `env/.env`)
6. **Lint**: `just lint`.
7. **Typecheck**: `just typecheck`.
8. **Test**: `just test` (unit only).
   - Generates JUnit report: `uv run pytest --junitxml=junit.xml`.
9. **Hooks**: `just hooks` (full repo run).
10. **Upload Artifacts**: Upload `junit.xml`.

### 4. No-Secrets Policy

- The CI workflow will **NOT** have access to any Google/AEAT secrets.
- `AEAT_LIVE_TESTS` will remain unset.
- All tests run on CI must be deterministic unit tests or synthetic-data integration tests.
- Live tests are explicitly skipped via `pytest -m 'not live'`.

### 5. Concurrency & Permissions

- **Concurrency**: Cancel in-progress runs for the same PR to save resources.
- **Permissions**: `contents: read` only.

## Consequences

- Automated verification of every PR on both primary platforms.
- Faster feedback loop for contributors.
- Prevent regression of Windows-specific bugs.
- No ability to run live tests on CI (intentional).
- Need to maintain `just` recipes compatible with both `bash` and `pwsh`.

## Refinement of `just bootstrap`

We will NOT call `just bootstrap` directly on CI as it includes `gsuite-bootstrap` which is interactive and requires credentials. Instead, we expand the bootstrap steps in the workflow.
