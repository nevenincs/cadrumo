---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P10.S44'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit]]'
---

# `cross-campaign-hardening` `P10.S44`

Ran the persona-testimonial re-audit over the hardened CLI and backend
surface.

- Verified: profile setup and active-profile editing
- Verified: overview calendar read path
- Verified: Modelo 303 work creation
- Verified: ledger category catalogue discovery
- Verified: live CLI read-only help
- Verified: Renta manual registry listing
- Found: one Modelo 100 bindings-list readiness-label regression

## Description

The pass used an isolated local scratch environment under
`.vault-scratch/cross-campaign-s44` with `AEAT_LIVE_TESTS_ENABLED=0`.
No live AEAT session or real taxpayer credential was used.

The audit record is
`.vault/audit/2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit.md`.

## Finding

`uv run aeat app modelo bindings list --modelo 100 --year 2025 --missing`
rendered profile-sourced Modelo 100 bindings as `ledger source`.

The likely repair belongs to `P10.S45`: add the current `profile` source
kind to the CLI readiness mapping and cover it with a regression test.

## Tests

Manual testimonial commands completed for profile create/edit, overview
calendar, Modelo 303 work creation, ledger categories catalogue, live
help, and Renta manual listing.

`uv run aeat app ledger categories --family iva` was rejected because
the command has no `--family` option; follow-up help and catalogue
inspection confirmed the current UX intentionally lists all categories
grouped by family.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S44` closed the row.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/audit/2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P10-S44.md` passed; Git repeated the pre-existing CRLF notice for the plan.
