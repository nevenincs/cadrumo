---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]"
---

# `cli-workflow-redesign` audit: state-architecture testimonial regression

The campaign's final verification - a real-operator persona pass over
the profile / auth / overview flows the state-architecture campaign
rebuilt (plan steps W05.S22 and W03.S15). Method: the testimonial
playbook - CLI + `--help` only, isolated `AEAT_LOCAL_STORAGE_ROOT`,
verbatim command log, honest first-person testimonial.

Persona: "Marta", an autónoma managing two business profiles.

## Confirmed wins (verified from an operator's seat)

- **Rename holds.** `Cafe Luna` -> `Cafe Luna Centro` survived list,
  status, show, switch-in and switch-out with all data intact and the
  internal `profile_id` stable. The rename-corruption defect class the
  campaign set out to eliminate is gone, confirmed by a user.
- **`auth status` and `auth test` agree** - byte-identical output, no
  contradiction. The W04 read-projection fix verified.
- **Accented and spaced display names work end to end** (`José Diseño`,
  `Cafe Luna`) across create / list / show / status / switch. The W01
  decoupled-label decision verified.
- **Profile switching is reliable**; the duplicate-name and
  unknown-name refusals are clear and actionable.

## Findings

### MAJOR - `profile delete` tombstone leaked into the live surface

A deleted (tombstoned) profile still appeared in `profile list`, was
switchable and became the active profile, was reported
`readiness ready, issues=0` by `show`, and kept its display name
reserved against reuse - the last point violating the identity ADR's
"tombstoned names reusable" constraint. Actioned as plan Wave W06:
the leak fix landed in `b99081a76`; a review-driven revision
(integrity drift-check + torn-write hardening) followed.

### POLISH - one English line in the Spanish dashboard

`overview status` emitted "No modelo work units have been started
yet." in otherwise-Spanish output - W04 left locale catalogues with
scaffold-placeholder stubs. Fixed in `b99081a76` (real translations
filled in en / es / ca / hu).

### MINOR - `profile create` with a bare name refuses instead of guiding

`aeat config profile create "Cafe Luna"` is refused with a message
referencing `--quiet` that the operator never passed, rather than
launching the wizard the help advertises. This is wizard-UX behaviour
outside the state-architecture campaign's structural scope; handed to
the broader CLI-UX backlog as a testimonial finding, not fixed here.

## Status

The five structural waves W01-W05 are verified sound from an operator's
seat. The one MAJOR is being closed as W06. The MINOR is a tracked
hand-off. The campaign's core objective - a profile management backend
where identity is stable, rename cannot corrupt, and the surfaces
agree - is met.
