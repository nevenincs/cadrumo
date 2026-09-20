---
tags:
  - '#plan'
  - '#lud-authority'
date: '2026-09-20'
tier: L1
related:
  - '[[2026-09-20-lud-authority-adr]]'
modified: '2026-09-20'
body_schema: body-v2
body_hash: 'sha256:995efe84d1ab6b408c6b4f6495b48ae6b496250bcd8471312664e8c99d0801d0'
---

# `lud-authority` plan

## Description

Approved 2026-09-20 - the operator explicitly waived further approvals and requested end-to-end delivery, commit, push, PR creation, and CI closure.

Implement the accepted startup ownership policy in `2026-09-20-lud-authority-adr`. S01 sharpens the existing canonical storage materializer. S02 composes that boundary with canonical published-authority resolution at normal CLI startup, enrolls changed modules in logging and strict type checks, and provides minimal integration coverage. The decision is grounded by `2026-09-20-lud-authority-reference`; no additional architectural choice remains open.

## Steps

- [x] `S01` - Distinguish derived storage defaults from explicit directory dependencies and prove both paths; `src/cadrumo/core/storage_materialization.py and owning tests`.
- [ ] `S02` - Compose authority and storage preflight into normal CLI startup with logging, strict typing, and focused integration coverage; `application provisioning and CLI startup surfaces`.

## Parallelization

S01 precedes S02 because CLI startup consumes the finalized materializer contract. Read-only discovery and test/config inventory may run concurrently, but one principal writer owns implementation and commits.

## Verification

Focused core tests prove missing defaults are created idempotently, missing explicit overrides refuse through a core-derived exception, existing explicit directories pass, and non-directory occupancy still refuses. Focused application/CLI tests prove normal startup provisions defaults, refuses unavailable explicit paths, requires the shipped or overridden authority, and leaves metadata invocations isolated. Ruff, the configured strict per-module type checker, logging enrollment gates, the owning test suites, full project quality gates, and Vaultspec plan/check gates must pass or have pre-existing failures reported precisely. Final integrated review must contain no critical or high finding.
