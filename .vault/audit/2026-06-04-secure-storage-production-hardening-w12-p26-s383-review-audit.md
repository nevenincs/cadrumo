---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:8a01781d7ce8cf533804d01c11e7c346a7325045c48b5a1c829b6c2dd83a50d0'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S383` Review

## S383-001 | PASS | Modelo CLI resolves visible work targets through application selectors

The modelo CLI is wired to the application selector/addressing services for natural modelo/year/period work targets instead of forcing copied opaque ids for the common path. Ambiguous, missing, and conflicting targets are rendered as typed refusals.

## S383-002 | PASS | Projection commands are split into a focused CLI module

Projection and comparison command registration is delegated to the projection CLI module while preserving localized help and `BadParameter` rendering. The projection command tests pass against the real CLI runner.

## S383-003 | PASS | Natural-key workflow coverage is real behavior

The natural-key tests create a real isolated profile, create Modelo 130 work, calculate, verify, and export through visible keys. They do not mirror business logic in the test body.

## S383-004 | PASS | Validation

- `uv run --no-sync ruff check ...`
- the historical check

Disposition: close `AFR-281`.
