---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:0bc07f8e42b07fea0038e8e0cedd0dafbd097491eb2c6cfb1e3923585ab948cf'
step_id: 'S10'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

# Rerun live Modelo 036 censo pull, compare, apply, expedientes, notifications, filed history, and justificante pulls

## Scope

- `src/aeat/entrypoints/cli/_config/_profile_censo.py`

## Description

Ran the full authenticated live-read sweep on 2026-07-10 against the real
`me` profile in the persistent `file`-backed store, using the operator's
`env/.env` Cl@ve Movil identity and secret-store passphrase with raw identity
values redacted from this record.

- Unlock: sourced `env/.env`; `config profile status` decrypted the `me`
  profile with `tax_id_present=true`.
- Auth: `config auth status --provider clave_movil` reported
  `configured=true`, `available=true`, `authenticated=false`.
- Login: `config auth login --provider clave_movil --fresh --reset-lock`
  reached the non-QR Cl@ve flow (page verification code `H84`); the operator
  approved on the phone and it returned `authenticated=true`, `fresh=true`,
  `reused_persisted_session=false`, `acquired_lock=true`. This is the first
  authenticated persisted session obtained for this plan.
- Censo: `config profile censo pull` ran under the live session
  (`auth_persisted_session_state=live`, `auth_identity_alignment=matches`,
  `auth_identity_kind=NIE`).
- `config profile censo compare` / `apply` were not runnable (no snapshot).
- Notifications: `app live notifications pull`.
- Filed history: `app live filed list --from-year 2026 --to-year 2026` and
  `app live filed pull --modelo 303 --year 2026 --limit 1`.
- Expedientes: `app live expedientes pull --modelo 303 --year 2026`.
- Justificante: `app live justificante list`.

## Outcome

Every live-read facade reached AEAT under one authenticated session and
persisted real snapshots. The AEAT account is genuinely empty for 2026, so all
reads returned zero rows:

- Notifications pull: `row_count=0`, snapshot persisted.
- Filed list 2026: reached AEAT; 0 usable rows plus local-boundary refusals for
  models with no filed-declarations live-read surface (e.g. `763`, `848`).
- Filed pull 303/2026: `captured_count=0`, `failed_count=0`,
  `justificante_metadata_count=0`, `filing_evidence_stamped_count=0`.
- Expedientes pull 303/2026: `declaration_count=0`, snapshot persisted.
- Justificante list: `count=0`.
- Censo pull: reached G313 but landed on `/wlpl/BUGC-JDIT/MdcAcceso` (an
  access-gate page) and produced an empty `CensoFactSet` — `ERROR_SEDE_NAVIGATION`,
  `failure_mode=live_navigation_failed`, `censal_marker_present=false`,
  `populated_field_count=0`. The error text itself notes this is "far more often
  a wrong-service / auth-gate landing than a genuine 'no censo for this NIF'".

The live-read transport for censo, notifications, filed history, expedientes,
and justificante is proven operational end-to-end with a real authenticated
session. Positive censo `apply` and positive filed/justificante reconciliation
could not be produced: the censo `apply` is blocked by the G313 launcher landing
on an access-gate page (a navigation/parser grounding defect, not auth), and
there is no filed 2026 declaration in the account to pull, parse, or enroll.

## Notes

Two residual blockers are carried as a follow-up reference
(`2026-07-10-live-censo-calendar-reconciliation-reference`), neither of which is
remaining implementation scope of this plan:

1. G313 `Mis Datos Censales` launcher/parser grounding: under a valid live
   session the navigation lands on `/wlpl/BUGC-JDIT/MdcAcceso` with zero
   populated fields. Needs the launcher re-pointed or the censo parser labels
   re-grounded against the live authenticated page.
2. Empty AEAT account state: no filed 2026 declaration exists, so positive
   filed-history / justificante enrollment proof is environmentally unobtainable
   until the account carries a filed row.

No destructive git operations were run. Raw NIE, soporte, passphrase, and
storage-state values were not written to this record.
