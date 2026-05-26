---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-profile-uuid-identity-adr]]"
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook]]"
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

## 2026-05-21 W03.S15 rerun

The W03.S15 profile-flow rerun used the real CLI in an isolated
`AEAT_LOCAL_STORAGE_ROOT` at `var/tmp/state-w03-s15-profile-persona`.
The sequence covered cold `profile status`, two `profile create`
commands, `profile list`, `profile rename`, named `profile show`,
`profile switch`, active `profile status`, `profile delete --yes`,
post-delete list and switch refusal, tombstone inspection, and
tombstoned-label reuse.

Results:

- `cafe-luna` renamed to `cafe-luna-centro` without changing the
  operator-visible UUID reported by `show` and `status`.
- Switching between `cafe-luna-centro` and `studio-sol` succeeded and
  `status` reported the active display label.
- Deleting `cafe-luna-centro` tombstoned the profile; `list` omitted
  it and `switch cafe-luna-centro` refused with exit code 2.
- Named `show cafe-luna-centro` still inspected the retained tombstone
  and rendered `readiness tombstoned`.
- Creating a new live `cafe-luna-centro` profile succeeded with a new
  UUID, proving tombstoned display-name reuse remains closed.

### Gate finding - direct `profile_app` duplicate-create boundary

The real CLI persona pass raised no behavioral finding, but the
focused profile lifecycle suite caught a direct-subapp regression:
duplicate `profile create` attempts leaked
`ProfileAlreadyRegisteredError` and left `result.output` empty when
tests invoked `profile_app` directly. Operators invoking through the
root CLI already received the decorated boundary; the defect was the
testable profile-subtree surface.

Repair: decorate `profile_app` after the profile and census verbs are
registered, without decorating the broader direct `config` app. That
keeps existing direct `config` exception tests intact while making the
profile lifecycle surface render duplicate-create refusals.

Verification:

- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `uv run pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py -q`
- `uv run pytest src/aeat/entrypoints/cli/_config/test_apoderado.py src/aeat/entrypoints/cli/test_profile_census_verbs.py -q`
- root CLI duplicate-create smoke with an expected exit-2 refusal

The focused suite passed: 42 passed. The compatibility suite passed:
14 passed. The root duplicate-create smoke rendered `Refused.` and
exited 2.

## 2026-05-21 W05.S22 final gate

The W05.S22 final verification gate ran after W03.S15. It covered the
full CLI tree, the full domain registry tree, registry verification,
cross-store secure-object integrity, and a real CLI testimonial batch
across profile, auth, overview, and Modelo work verification.

Gate blockers found and actioned:

- The application registry topic test exposed stale output-language
  caching under `override_settings`. The cache key now includes the
  override settings values that affect language resolution instead of
  relying on object identity.
- The full domain registry suite exposed a Modelo 303 reviewability
  regression: the single-file TOML had grown past the 2,000-line
  limit. Modelo 303 now uses directory-mode fragments for manifest,
  revision metadata, casillas, and export-layout records.

Verification:

- Full CLI tree: 629 passed, 8 third-party deprecation warnings.
- Full domain registry tree: 1,826 passed.
- Registry CLI/application/i18n focused gate: 87 passed.
- State/profile projection focused gate: 105 passed.
- Modelo 303 fragmentation focused gate: 19 passed.
- `aeat app registry verify`: `Verificado=True`.
- `aeat config repair integrity objects`: 7 readable, 0 unreadable
  across 7 namespaces.
- `python -m aeat.locales audit`: ca/en/es/hu ok.
- `python -m aeat.locales scaffold --check`: ca/en/es/hu ok.

The W05 testimonial run created profile `w05-operator`, verified
profile status, confirmed `auth status` and `auth test` agree on the
active profile and auth readiness, showed `overview status --verbose`
reporting the in-progress Modelo work unit, calculated and verified a
Modelo 111 revision, and confirmed secure-object integrity after the
workflow. A repeat `work verify` correctly refused the now verified
revision because only draft revisions can be verified.
