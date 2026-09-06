---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:7cd9c1b082bd207ba826734e3cdafac61ecff61d904450066346115c116beab5'
step_id: 'S483'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Re-verify every gate closed in this campaign still holds after the concurrent writers commits and confirm the export tree blocker is unchanged, since a rename on this worktree was reverted five times before and a closed gate is only closed until someone else edits its surface

## Scope

- `dev/locales`, `dev/docs`, `src/cadrumo/entrypoints`, `src/cadrumo/domain`
  (verification only; nothing changed)

## Changes

NOTHING WAS CHANGED. Every gate closed in this campaign still holds: 599 tests
pass across the eight suites, run serially.

    dev/locales/tests/test_language_flag_help_honesty.py                 (S466)
    entrypoints/cli/tests/test_json_error_contract.py                    (S467)
    entrypoints/cli/tests/test_parse_error_envelope_names_its_command.py (S468)
    dev/docs/tests/test_static_frame_reasons.py                          (S470)
    entrypoints/cli/tests/test_documented_command_conformance.py         (S475)
    entrypoints/cli/tests/test_bootstrap_exempt_entries_resolve.py       (S476)
    domain/calculations/registry/tests/test_export_split_part_rendering.py (S477)
    entrypoints/cli/tests/test_config_reset_lifecycle.py                 (S478)

WHY THIS IS WORTH A FIRING RATHER THAN AN ASSUMPTION. A closed gate on this
worktree is closed only until someone else edits its surface. The
`direction_state` rename was reverted by the other writer FIVE times before they
adopted it themselves, and three of the gates above were broken in the first
place by a single import-promotion sweep that deleted the data files they read
(S470, S475). "I fixed it" is a claim about a past state of a tree that several
people are committing to.

THE EXPORT-TREE BLOCKER IS UNCHANGED. No regeneration has landed since
`62b0375ffb refactor(registry): canonicalise the closed vocabularies`, and
`m390-2022` still has no export directory. The two reasons S472 gave to stop
both still hold.

## Notes

THE CAMPAIGN IS NOW DECISION-BLOCKED, and I want to be exact about what that
means rather than call it done.

Closed and verified: fourteen scanner blind spots, the em-dash directive, the
click render funnel, two deleted-baseline recoveries, a retired-probe consumer,
a stale spine assertion, a fixture naming a command that does not exist, a
bootstrap exemption, two Modelo 200 repeated-slot questions, and a seeded
profile that production cannot produce.

Not closed, and not mine to close:

* THE PRUNE. 132 catalogue extras, every one carrying a not-declared verdict
  from the live authority that owns its namespace (S461, S463, S482), and none
  carrying a dotted literal anywhere in source (S481). This is the only thing
  between `test_codebase_to_locale_parity` and the two `test_audit` gates and
  green.
* THE EXPORT TREES. 27 trees whose drift is a serializer rewrite with no change
  in parsed meaning (S474), on a surface an active writer is publishing to, plus
  `m390-2022` needing a `_CHECK_MODE_PENDING` reason that is an operator
  judgement about an AEAT revision's official standing.
* THE TWO CUSTODY CASES, environment-limited on this host: the Windows
  credential store is unreachable from this logon session, proved below Cadrumo
  with a bare `keyring` probe (S479).

I have not found further gates that evidence can close. If more exist, they are
on surfaces neither the `dev/` nor the `src/` sweep reached, and I would rather
say that than report a clean tree I have not established.
