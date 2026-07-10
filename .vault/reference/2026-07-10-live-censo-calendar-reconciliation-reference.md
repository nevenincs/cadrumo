---
tags:
  - '#reference'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace live-censo-calendar-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `live-censo-calendar-reconciliation` reference: `live censo G313 launcher blocker`

<!-- Brief description of what was researched and what sources were consulted.

Include any concrete references to files, line numbers, modules, etc. This is
the information that coding agents will consult during implementation. -->

## Summary

On 2026-07-10 the live-censo-calendar-reconciliation plan finally obtained a
real authenticated Cl@ve Movil session against the operator's `me` profile and
ran the full live-read sweep (S10) plus the calendar projection (S11). The
read transport is proven end-to-end; two residual blockers remain, and NEITHER
is remaining implementation scope of the reconciliation plan. This reference
carries them so they do not rot.

## Blocker 1 — G313 `Mis Datos Censales` launcher lands on an access gate

Under a valid live session (`auth_persisted_session_state=live`,
`auth_identity_alignment=matches`, `auth_identity_kind=NIE`),
`config profile censo pull` reached AEAT G313 but the navigation landed on
`landing_path=/wlpl/BUGC-JDIT/MdcAcceso` (`landing_host=sede.agenciatributaria.gob.es`)
— an access/auth-gate page — and the parser produced an empty `CensoFactSet`.

- Error: `ERROR_SEDE_NAVIGATION`, `failure_mode=live_navigation_failed`,
  `censal_marker_present=false`, `populated_field_count=0`.
- The error message itself states this is "far more often a wrong-service /
  auth-gate landing than a genuine 'no censo for this NIF'".
- Consequence: `config profile censo compare` and `config profile censo apply`
  cannot run (no snapshot), so positive censo-backed calendar enrolment
  (`censo.enrolment_unverified` cleared) is not producible.

This supersedes the older, vaguer "AEAT G313 returned no readable censo"
diagnosis from the `2026-06-12` blocker audit: the account-empty framing was
wrong; the launcher is landing on the wrong page. Next action is to capture the
authenticated landing HTML, confirm the es13 Mis Datos Censales content markers,
and either re-point the launcher navigation or re-ground the censo parser
labels against the live authenticated page. The censo-sync application logic
(`_censo_sync.py`) and the CLI verbs (`_profile_censo.py`) are unchanged by this
finding; the defect is in the outbound AEAT G313 launcher/parser.

## Blocker 2 — AEAT account is empty for 2026

Every live-read facade succeeded and persisted real snapshots, all returning
zero rows: notifications (`row_count=0`), filed list 2026 (0 usable rows),
filed pull 303/2026 (`captured_count=0`, `justificante_metadata_count=0`,
`filing_evidence_stamped_count=0`), expedientes 303/2026 (`declaration_count=0`),
justificante list (`count=0`).

Because no filed 2026 declaration exists in the authenticated account, positive
filed-history / justificante enrollment and positive submitted /
justificante-verified calendar rows are environmentally unobtainable. This is
account state, not a code gap: the read path is proven operational and the
calendar correctly refuses to fabricate submitted state (strict calendar
REFUSES on `censo.enrolment_unverified`; `--allow-incomplete` shows local
obligation rows only). Positive proof becomes producible once the account
carries a filed row to reconcile against.
