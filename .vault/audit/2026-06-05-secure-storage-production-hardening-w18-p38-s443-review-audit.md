---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W18-P38-S443]]'
---

# `secure-storage-production-hardening` `W18.P38.S443` Review

## S443-001 | PASS | Selector storage custody is delegated

`src/aeat/application/modelo/_selectors.py` resolves active-bucket defaults through the core active profile pointer and loads work-unit/calculation-revision catalogues through repository protocols. It does not construct secure repositories, inspect manifests directly, read raw environment variables, or persist data.

## S443-002 | PASS | Error and validation contracts are enrolled

Selector errors derive from the modelo/core AEAT error hierarchy and are declared in the central application error registry. Focused selector/work-addressing tests, natural-key CLI tests, error-registry tests, ruff, and `python -m aeat.locales audit` passed.

Disposition: close `AFR-295` as `manifest-discovery`.
