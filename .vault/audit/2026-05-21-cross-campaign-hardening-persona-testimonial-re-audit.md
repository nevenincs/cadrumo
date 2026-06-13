---
tags:
  - '#audit'
  - '#cross-campaign-hardening'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-persona-fleet-bug-inventory-audit]]'
  - '[[2026-05-21-persona-fleet-round2-findings-audit]]'
---

# Cross-campaign hardening persona-testimonial re-audit

Persona-style re-audit for `P10.S44`, covering the hardened CLI and
backend paths closed by the cross-campaign hardening plan.

## Scope

The pass used a local-only autonomous operator flow against an isolated
scratch environment:

- `AEAT_DATABASE_URL = sqlite:///.vault-scratch/cross-campaign-s44/aeat.db`
- `AEAT_PROFILE_BUCKET_ROOT = .vault-scratch/cross-campaign-s44/buckets`
- `AEAT_LOCAL_STORAGE_ROOT = .vault-scratch/cross-campaign-s44/local`
- `AEAT_LIVE_TESTS_ENABLED = 0`

No live AEAT session was opened and no real taxpayer credential or
secret was used.

## Commands Exercised

- `uv run aeat config profile create persona-autonomo --quiet --tax-id 00000000T --name Persona --surnames Autonomo --activity consultoria --iva-regime GENERAL`
- `uv run aeat config profile edit persona-autonomo --quiet --entity-type natural_person --irpf-income-categories actividad_economica`
- `uv run aeat --format json app overview calendar --from 2026-01-01 --to 2026-03-31 --allow-incomplete`
- `uv run aeat app modelo bindings list --modelo 100 --year 2025 --missing`
- `uv run aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2009-y-siguientes`
- `uv run aeat app ledger categories`
- `uv run aeat app live --help`
- `uv run aeat app registry manuals list --manual renta --year 2025`

## Passing Observations

- Profile create and edit completed with an active profile.
- `overview calendar` returned JSON with `taxpayer_model_declared: true`,
  `incomplete_reason: null`, and no warnings for the exercised period.
- `modelo work create` for Modelo 303 produced a 64-character work unit
  id and the localized created-work-unit message.
- `ledger categories` exposed a grouped category catalogue and usage
  guidance for passing category ids.
- `app live --help` presented the live surface as read-only observation;
  nested wallet help retained the own-name and protected-data wording.
- `registry manuals list --manual renta --year 2025` returned the Renta
  manual parts, including the autonomic-deductions part.

## Finding

### S44-001 - Modelo 100 profile-source bindings are labelled as ledger sources

Severity: major UX regression.

`uv run aeat app modelo bindings list --modelo 100 --year 2025 --missing`
showed profile-sourced Modelo 100 rows with readiness text `ledger
source`. Example rows included profile facts such as tax id, given name,
and surnames. These values are not ledger-derived inputs, so the label
misdirects an operator toward ledger work when the missing value comes
from profile facts or profile completeness.

The likely local cause is `src/aeat/entrypoints/cli/_modelo.py` mapping
`profile_fact` to `profile fact` but not the current registry source
kind `profile`. The fallback path returns `ledger source`, which is now
wrong for this binding family.

Required follow-up for `P10.S45`:

- add the `profile` source kind to the readiness mapping;
- add a CLI regression test asserting profile-sourced binding rows render
  as `profile fact`;
- re-run the affected CLI, locale, plan, and diff gates.

Resolution: `P10.S45` added the `profile` readiness mapping and a
real CLI regression test for Modelo 100 profile-sourced rows.

## Non-Finding

An operator attempted `uv run aeat app ledger categories --family iva`.
The command rejected `--family` because the current CLI exposes a single
grouped catalogue rather than a family-filtered view. Follow-up help
inspection and the catalogue output both showed grouped families and
category-id usage guidance, matching the earlier ledger catalogue
remediation intent. This is not tracked as a regression in this pass.

## Disposition

`P10.S44` found one follow-up regression. `P10.S45` folded that finding
into a small repair wave and re-ran the affected gates before the
cross-campaign hardening plan was closed.
