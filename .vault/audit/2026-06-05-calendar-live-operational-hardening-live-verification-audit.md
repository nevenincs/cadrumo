---
tags:
  - '#audit'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
  - '[[2026-06-04-calendar-live-filing-integration-live-verification-audit]]'
---

# `calendar-live-operational-hardening` Live Verification

## LIVE-001 | INFO | M190 filed-capture host repair verified by authenticated rerun

The 2024 full `filed capture-all` rerun completed against AEAT after adding the live declarations register host to the Modelo 190 read surface. The rerun queried 30 registry modelos, captured 16 observations, persisted 670 casillas, promoted 12 calculation observations, and reduced failures to one Modelo 721 boundary row.

## LIVE-002 | INFO | Modelo 721 now reports as a local unsupported boundary

`app live filed capture-all --modelo 721 --from-year 2024 --to-year 2024` returned without live session acquisition and emitted one structured failure row: `LiveApplicationInputError`, Modelo 721, year 2024, message that AEAT declarations register does not offer Modelo 721 and the registry revision declares no filed-declarations live read surface.

Follow-up verification after review fixes ran `app live filed capture-all --modelo 151 --modelo 721 --from-year 2024 --to-year 2024`; it returned without live auth, captured zero observations, and emitted two structured registry-derived unsupported-boundary rows.

## LIVE-003 | INFO | Notifications latest local facade verified

`app live notifications latest` loaded the latest persisted notification snapshot and reported one row with snapshot id `3c170c19cad77259c2dedd230feab117c6700c9a15e4818533a3e5b139b86e44`. This is local-only readback over a snapshot captured in the preceding live verification.

## LIVE-004 | INFO | Calendar and agenda readbacks verified

`app overview calendar --from 2024-01-01 --to 2026-12-31 --all-profiles` returned nine profile calendars and seven observed live events on the live IVA profile. `app overview agenda --date 2026-06-05 --horizon 45 --allow-incomplete` returned a stable local agenda envelope after the incomplete-profile override fix.

## LIVE-005 | MEDIUM | Current Cl@ve Móvil auth blocked fresh live capture attempts

Three fresh Cl@ve Móvil live attempts timed out after 120 seconds: two `filed capture-all --modelo 190 --modelo 721` attempts and one `expedientes capture-all --modelo 303 --modelo 190` attempt. The commands reached the auth preflight and Cl@ve Móvil browser route, then failed with `AUTH_AUTH_CLAVE_MOVIL_CLAVE_MOVIL_APPROVAL_TIMEOUT`. This blocks fresh verification of the new expedientes bulk command in the current session, but not command registration or local readback.
