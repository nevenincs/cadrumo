---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S30'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W04.P04.S30 - Fresh profile password-backed smoke and live unlock blocker

## Description

- Verify that a user can create a fresh password-backed profile from the CLI without depending on the existing shared active profile.
- Confirm live and censo command surfaces are reachable after fresh profile creation.
- Record the current blocker for full authenticated AEAT censo/filed/message/justificante pulls.

## Outcome

The existing shared active profile could not be unlocked non-interactively with:

- no `AEAT_SECRET_PASSPHRASE`;
- `horatio` (`< 8` characters and refused by the passphrase policy);
- `horatio-live-test`;
- the configured development/test database password.

The cold-start creation path is functional. `aeat config profile create --help` renders without requiring a passphrase. In an isolated storage root under `var/aeat/fresh-profile-smoke-20260612`, a fresh `live-smoke` profile was created with a valid-length session passphrase, then listed successfully.

The fresh profile could reach:

- `aeat app live --help`;
- `aeat config profile censo --help`, which exposes `pull`, `show`, `compare`, and `apply`;
- `aeat app overview calendar --from 2026-01-01 --to 2026-12-31`.

The local calendar projection produced seven concrete entries across Modelos 100, 303, 390, and 721. Each row correctly kept `local=not_ready_to_file`, `aeat=not_observed`, and `justificante=false`, proving the calendar distinguishes profile-derived obligations from AEAT-submitted/justificante-verified state before live evidence is pulled.

## Verification

- `uv run aeat config profile create --help` passed without a secret-store passphrase.
- Isolated `uv run aeat config profile create live-smoke --quiet --accept-defaults --entity-type natural_person --tax-id 12345678Z --irpf-income-categories actividad_economica --name Live --surnames Smoke` passed with `AEAT_SECRET_PASSPHRASE=horatio-live-test`.
- Isolated `uv run aeat config profile list` passed and showed `live-smoke` as the active profile.
- Isolated `uv run aeat app live --help` passed.
- Isolated `uv run aeat config profile censo --help` passed.
- Isolated `uv run aeat app overview calendar --from 2026-01-01 --to 2026-12-31` passed with seven entries.
- Isolated JSON calendar output showed `taxpayer_model_declared=true`, concrete filing windows, and filing evidence still unobserved by AEAT.

## Live Verification Status

Full live authenticated pulls are still blocked on a real profile identity: the operator must provide a valid passphrase of at least eight characters and a profile tax ID matching the AEAT identity used during authentication. Without the matching tax ID, a censo pull or justificante reconciliation would not prove the required calendar/legal-situation linkage.
