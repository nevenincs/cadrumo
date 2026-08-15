---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ba92474e6fb395f6826cda5253dba0c4cca725fea16067f74f4a17297a06f8ac'
step_id: 'S129'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether a bucket carrying a manifest and no profile record is still a reachable torn state worth testing, since listing and resolution are capsule-only so such a bucket is invisible to every operator path, which would make the premise of the tests named for it obsolete rather than merely awkward

## Scope

- `src/cadrumo/entrypoints/cli/tests/_profile_lifecycle_support.py`

## Description

- Read `_profile_lifecycle_support.py` whole and enumerated its four
  consumers by grep before changing anything.
- Traced every resolution path `stage_bucket_manifest`'s four consuming tests
  exercise (`config login NAME`, `config profile show NAME`,
  `config profile create NAME`, `config repair profile --profile NAME`) back
  to `resolve_login_target` / `resolve_profile_bucket`, confirming all route
  through the same committed-capsule-only projection this campaign already
  ruled on (`S73`).
- Ran the four consuming tests to observe the current, actual failure mode
  rather than reasoning from the code alone.
- Retired `stage_bucket_manifest` and its four consuming tests, with the
  reason recorded here and in the support module's docstring.

## Outcome

**Ruling: the torn state is unreachable, in the same sense `S73` already
established for a pre-capsule bucket, and the tests built on it are retired
as obsolete.**

`stage_bucket_manifest` never actually staged "a bucket carrying a manifest
and no profile record" as a resolvable identity: `open_test_profile_session`
(the only thing it calls before writing the manifest stub) opens a raw
`BucketSession` over a derived key and never calls
`ProfileCapsuleLifecycle.create`, so no custody capsule is ever committed for
the staged bucket. The stub manifest and the derivable session key exist on
disk, but the bucket carries no committed capsule at all -- the literal
pre-capsule case `S73` measured.

Two independent lines confirm unreachability:

1. **Static trace.** Every consumer's resolution path
   (`config login` -> `login_profile` -> `resolve_login_target` ->
   `resolve_profile_bucket`; `config profile show` / `create` / `repair
   profile` -> `_resolve_profile_by_label` -> `read_profile_bucket`) bottoms
   out in `CommittedProfileRepository`, which enumerates only
   `list_current_profile_custody_capsule_ids`. A bucket with no committed
   capsule is invisible to every one of these doors -- not merely to listing,
   which is all `S73` traced.
2. **Live reproduction.** Running the four consuming tests
   (`test_config_login_reports_manifest_without_profile_record_through_lifecycle_boundary`,
   `test_config_profile_show_does_not_suggest_retired_activation_for_missing_record`,
   `test_config_profile_create_refuses_manifest_only_profile`,
   `test_repair_profile_named_active_clear_active_clears_pointer`) shows all
   four RED right now, each failing inside `stage_bucket_manifest` itself
   with `ValueError: badly formed hexadecimal UUID string` --
   `open_test_profile_session` now requires a canonical UUID identity (part
   of the label-to-identifier migration `S62` made), but the four call sites
   still pass the raw label `"operator"` as the bucket id. The helper cannot
   even construct its intended state anymore.

The sense of "reachable" used: reachable BY AN OPERATOR through a CLI verb,
in production. A test helper that manufactures on-disk bytes directly (as
`stage_bucket_manifest` did, and as `forge_colliding_capsule_label` still
legitimately does elsewhere for a different, genuinely-untestable-otherwise
backstop) does not establish reachability in that sense -- the question is
whether any operator action produces the state, and per points 1-2 above,
none does: capsule creation is the only production door that commits a
capsule, and it always writes the initial record alongside (per `S62`'s
finding on `CommittedProfileRepository`), so a committed-capsule-with-no-record
state has no production writer either. The genuinely real, differently-shaped
`missing_profile_record` health status (`workflow/_profile_health.py:437-448`,
committed capsule + active pointer + record load returning `None`) is a
distinct state from the one these tests staged, is not what any of the four
tests constructed, and is not addressed by this ruling -- noted below as a
real, separate gap.

**Fate of each affected test: deleted outright, per `no-legacy-compatibility`
(delete, don't neuter).** All four tests exist solely to exercise
`stage_bucket_manifest`'s manufactured state; none carries a second,
independent assertion worth splitting out. Deleting them does not strand
coverage: `--clear-active` pointer-clearing remains covered by
`test_config_custody_profile_lifecycle.py`,
`test_profile_lifecycle_navigation.py` and `test_repair_bootstrap_exempt.py`
against genuinely reachable states (dangling pointer, tombstoned profile),
and `config profile create` against an existing profile remains covered by
`test_config_profile_create_refuses_existing_profile` (same file, seeded via
the real `seed()` capsule path).

`stage_bucket_manifest` itself was deleted from
`_profile_lifecycle_support.py`, along with its two now-dead imports
(`load_settings`, `provision_bucket_directory`), and the module docstring's
"and one torn-bucket stager" line was corrected to record what happened and
why.

## Notes

**Consumer set of `_profile_lifecycle_support.py`** (grepped tree-wide
before editing): `test_profile_lifecycle_verbs.py` (`distinct_nif`, `seed`,
formerly `stage_bucket_manifest`), `test_profile_lifecycle_navigation.py`
(`create_profile_via_cli`, `seed`), `test_profile_setup_incomplete_surface.py`
(`create_profile_via_cli`), `test_profile_rename_maintenance_events.py`
(`create_profile_via_cli`). Only `test_profile_lifecycle_verbs.py` imported
`stage_bucket_manifest`; the other three are unaffected by this Step.

**Real gap, not fixed here (out of scope for a ruling Step):** no test in the
tree constructs the genuine `missing_profile_record` state (a committed
capsule with a missing or unreadable record row) through a real reachable
construction and drives a CLI verb against it; existing coverage only
roundtrips the payload model and asserts a healthy profile does NOT report
it. Building that construction is new coverage, not a ruling on an existing
torn state, and belongs in its own Step.

**Verification is confounded by unrelated, concurrent tree instability.**
Running the CLI config test package (`test_profile_lifecycle_verbs.py`,
`test_profile_lifecycle_navigation.py`,
`test_profile_setup_incomplete_surface.py`,
`test_profile_rename_maintenance_events.py`) after these edits shows 44
failed / 10 passed, but every failure traces to `application/wizard`
("wizard profile creation is unavailable; register with credentials before
setup") or the custody envelope authentication path -- both outside this
Step's ownership and both under active concurrent edit per `git status`
(uncommitted changes in `application/bucket_maintenance`, all four locale
files). A control run against a completely untouched file in the same
package, `test_config_custody_profile_lifecycle.py`, reproduces the identical
failure pattern (5 failed / 1 passed, same refusal messages), confirming the
breakage is tree-wide and pre-existing, not caused by this Step's edits.
Collection is clean (54 tests collected, no import errors, no lingering
`stage_bucket_manifest` reference outside this module's own docstring), and
none of the 44 failures is one of the four deleted tests or references
anything this Step touched.
