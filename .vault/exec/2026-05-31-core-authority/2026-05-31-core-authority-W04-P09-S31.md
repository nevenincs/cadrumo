---
step_id: S31
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P09.S31 — CalendarCCAA migration (BLOCKED / DEFERRED)

## Status

**BLOCKED.** The prerequisite semantic equivalence finding from the audit is false. See S30 record for evidence.

## Block reason

CalendarCCAA (ISO codes: ES-AN, ES-MD) and CCAA (lowercase names: andalucia, madrid) use incompatible value formats and cover different member sets. The TOML holiday calendar files (`festivos-*.toml`) use `ccaa_code = "ES-MD"` format which maps only to CalendarCCAA. Deleting CalendarCCAA and migrating callers to CCAA would:

1. Break `CalendarCCAA(entry["ccaa_code"])` at line 250 of `_festivos.py` — CCAA has no "ES-MD" member.
2. Require changing TOML data files (BOE-cited, should not change format without BOE re-citation).
3. Require adding Ceuta, Melilla, País Vasco, Navarra members to CCAA (violating the foral-regime exclusion).

All three consequences violate the hard constraint "Do NOT change enum values" or break the holiday calendar system.

## Deferred to follow-up plan

A follow-up plan should scope: (a) either keep CalendarCCAA as the canonical holiday-calendar type (leaving CCAA for tax-residence), or (b) unify value formats by updating the TOML data to use lowercase names and adding a bridge method. The correct outcome is likely to treat them as intentionally distinct enums serving different domain concepts, and close MERGE-002 as "wontfix with documented rationale."

## Files touched

None.
