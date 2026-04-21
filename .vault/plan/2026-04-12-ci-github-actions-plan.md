---
tags:
  - "#plan"
  - "#ci-github-actions"
date: 2026-04-12
related:
  - "[[2026-04-12-ci-github-actions-adr]]"
  - "[[2026-04-12-ci-github-actions-research]]"
---
# Plan: GitHub Actions CI

## Goal

Add a GitHub Actions workflow to verify PRs and pushes to `main` on Ubuntu and Windows.

## Steps

### 1. Create Workflow File

- **File**: `.github/workflows/ci.yml`
- **Triggers**: `pull_request`, `push` to `main`.
- **Jobs**: `lint-and-test`
- **Matrix**: `os: [ubuntu-latest, windows-latest]`, `python-version: ["3.13"]`.
- **Steps**:
  - Checkout
  - Setup just
  - Setup uv (enable-cache: true)
  - Cache prek
  - CI Bootstrap: `uv sync`, `uv run vaultspec-core install --upgrade`, `just env-setup`.
  - Lint: `just lint`
  - Typecheck: `just typecheck`
  - Test: `uv run pytest --junitxml=junit.xml` (unit only)
  - Hooks: `just hooks`
  - Upload JUnit report

### 2. Update Documentation

- **README.md**: Add a CI status badge.

### 3. Verification

- Run `just lint`, `just typecheck`, `just test`, `just hooks` locally on Windows (already done).
- Validate the YAML structure of the workflow.

## Acceptance Criteria

- [ ] `.github/workflows/ci.yml` exists and follows the ADR.
- [ ] Matrix includes `ubuntu-latest` and `windows-latest`.
- [ ] No secrets are used; `AEAT_LIVE_TESTS` is unset.
- [ ] `just env-setup` is used for provisioning `env/.env`.
- [ ] README has a CI badge.
- [ ] Local checks pass on Windows.
