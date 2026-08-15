---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a6000db71eba1a014c0c662bac182598e7a24cdf35050e989878418af80fa398'
step_id: 'S60'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S60 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Have Sol Medium rule whether scripted profile creation is permitted, since the wizard persistence layer refuses it by explicit design as credential registration being the only creation door while the command, its quiet and accept-defaults flags and two tests all still assume it works, so the operator meets a refusal from a verb the surface advertises as scriptable and ## Scope

- `src/cadrumo/application/wizard/_persistence.py and src/cadrumo/entrypoints/cli/_config/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium rule whether scripted profile creation is permitted, since the wizard persistence layer refuses it by explicit design as credential registration being the only creation door while the command, its quiet and accept-defaults flags and two tests all still assume it works, so the operator meets a refusal from a verb the surface advertises as scriptable

## Scope

- `src/cadrumo/application/wizard/_persistence.py and src/cadrumo/entrypoints/cli/_config/`

## Description

- Read the wizard persistence refusal in `_persistence.py` and `_commands.py`
  and confirmed it is unconditional and deliberate for `mode == "create"`.
- Enumerated every surface that still advertises scripted creation: the
  `--quiet`/`--accept-defaults` flags on the `create` closure, their locale
  help text, and the integration test suite.
- Reproduced the refusal live against two representative tests and captured
  the run to `s60_test_run3.log` in the scratchpad directory.
- Read `register_profile_with_credentials`, the sole surviving creation
  door, to confirm it is genuinely non-interactive at the application layer
  and has exactly one consumer.
- Cross-checked against the standing `2026-08-15-profile-password-custody-capabilities-removed-without-a-decision-audit.md`,
  which independently investigated this exact question and converged, after
  two corrections, on the same position reached here.

## Outcome

**Ruling: scripted profile creation is NOT permitted. The advertisement is the
defect, not the refusal.** `--quiet` and `--accept-defaults` are retired from
the `create` arm; the ~294 tests asserting non-interactive `create` succeeds
are RETIRED, not rewritten to pass — they assert a capability the product
deliberately does not offer.

**Grounding.** `persist_answers` and `_run_full_flow` in
`src/cadrumo/application/wizard/_persistence.py` and
`src/cadrumo/application/wizard/_commands.py` both state the same design in
their docstrings and both enforce it unconditionally: `mode == "create"`
raises `ProfileRegistrationError("wizard profile creation is unavailable;
register with credentials before setup")` before any flag is even
inspected — `--quiet`, `--accept-defaults`, and every field flag are consumed
by argument parsing and then discarded. The sole creation door is
`register_profile_with_credentials(*, label, passphrase, facts=())` in
`src/cadrumo/application/user_profile/_registration.py`: a genuinely
non-interactive function taking a label and a passphrase as plain arguments,
with exactly one caller in the whole tree — the full-screen manager's
`present_registration()`. No CLI verb exposes it with a `--passphrase`
argument, and none should: a credential is not safe to place on a command
line or in shell history, which is the same posture
`sensitive-financial-data-secure-storage-only` and the custody model already
hold for every other secret. Retiring the CLI-scriptable path is coherent
with password custody, not incidental to it.

**The gap between refusal and advertisement is real and reproduces.**
`_mode_parameters` in `_commands.py` attaches `--quiet` and
`--accept-defaults` to BOTH `create` and `edit` unconditionally — the
signature does not know the flags are dead on `create`. The locale catalogue
(`cli.config.setup.accept_defaults_help`, en.yml line 4390) reads "...or on
its own for an all-defaults create", stating outright that a scripted create
succeeds. Two representative integration tests in
`src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py` were run
live and both fail exactly as the ruling predicts:
`test_config_profile_create_second_profile_uses_requested_identity_while_first_is_active`
gets `Refused. wizard profile creation is unavailable...` instead of exit 0,
and `test_config_profile_create_bare_name_refusal_names_both_recovery_paths`
asserts the refusal names `aeat config profile create NAME --quiet ...` as a
working recovery path when it is not one. The same file also has passing
tests that were never run here but assert the identical pattern
(`test_config_profile_create_bare_name_refusal_names_both_recovery_paths`'s
`--tax-id`-completed sibling, the readiness-status test seeding "maria",
etc.) — the ~294 count is not this campaign's estimate alone; it is
independently corroborated by the standing audit's own measurement, and
matches the shape reproduced here.

**The cost, stated plainly.** An operator or agent automating profile setup
from a shell loses a CLI-native, flag-driven creation path entirely. The
replacement is not equivalent in kind: it is a full-screen interactive
credential-first flow, or a caller writing directly against the Python
application-layer function (not exposed as a public SDK today). Per the
already-closed `W05.P08.S162`, this also means COLD-PROCESS CLI behaviour
around profile creation is untestable end to end through the CLI itself —
tests that need a fresh profile on a console-less host must create it
in-process (through `register_profile_with_credentials`, as `cadrumo.tests.profile_capsule`
already does) and hand the storage root to a subprocess, never by invoking
`aeat config profile create ... --quiet` and expecting it to work. That is
the accepted cost of this ruling, not an oversight.

**What replaces the retired capability, concretely.**
- The documented, supported way to create a profile is the interactive
  manager (a capable terminal), full stop.
- For test fixtures and any future headless SDK use, the sanctioned door is
  `register_profile_with_credentials` called in-process — never a CLI flag
  carrying a passphrase.
- The `--quiet`/`--accept-defaults` flags remain live and correct on `edit`,
  which is a true patch over an already-authenticated session and needs no
  fresh credential — nothing about this ruling touches `edit`.

**This unblocks, and is consistent with what it unblocks.**
- `W03.P06.S93` (retire or rewrite the ~294 tests): RETIRE. A test asserting
  `create --quiet ...` returns exit 0 has no surviving contract to be
  rewritten against; where a test's underlying intent (duplicate-label
  collision wording, missing-required-flag naming, CCAA-default disclosure)
  has no equivalent on a surviving door, S93 should re-found an equivalent
  test against `register_profile_with_credentials` or the manager frontend
  rather than simply deleting that coverage — but the assertion "the CLI
  create verb accepts these flags and succeeds" itself has nothing to be
  rewritten onto and is deleted outright.
- Every other row in this campaign that seeds a profile through
  `config profile create ... --quiet` in a test fixture (not just the 294
  under S93's direct count) inherits the same refusal and needs the same
  disposition; S93's scope note should say so explicitly so it is not
  rediscovered piecemeal.

**Consistency with prior rulings.** This does not depart from `W03.P06.S59`,
which explicitly held the create/scripted-creation question open for this
row rather than deciding it. It affirms, rather than silently re-decides,
the standing audit's own final position (reached after two retractions in
that document) that non-interactive creation is retired by design.

## Notes

An urgent, small code change is implied but explicitly NOT made here (this
row is read-only ruling): the `accept_defaults_help` locale string in all
four catalogues currently asserts a false capability ("...for an all-defaults
create") and should be corrected as part of whichever implementing row
retires the `create`-arm flags, so the documented contract and the shipped
help text stop disagreeing the moment a fresh operator reads `--help`.

No source was modified. No plan checkbox was changed. The `s60_test_run3.log`
capture lives under the session scratchpad directory, not the repository.
