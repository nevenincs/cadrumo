---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:47c46bc398659cae6162ca876f3b2e53d1865f99ee16d1b511742f1e59e72658'
step_id: 'S189'
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
     The S189 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Sol Medium sweep the three evaluation-harness consumers onto the renamed profile snapshot repository, since the application layer renamed the lifecycle repository without carrying its development-tree consumers, leaving three modules unable to import while every lane reported green, this being the first defect the newly enrolled collectability verdict caught and precisely the class it was enrolled to catch and ## Scope

- `dev/agent_eval/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Sol Medium sweep the three evaluation-harness consumers onto the renamed profile snapshot repository, since the application layer renamed the lifecycle repository without carrying its development-tree consumers, leaving three modules unable to import while every lane reported green, this being the first defect the newly enrolled collectability verdict caught and precisely the class it was enrolled to catch

## Scope

- `dev/agent_eval/tests/`

## Description

- Confirmed the break: `dev/agent_eval/tests/test_faithfulness_golden.py`,
  `test_response_provenance_golden.py`, and `test_under_declaration_golden.py`
  all imported the retired `UserProfileLifecycleRepository` from
  `cadrumo.application.user_profile`.
- Read the renamed class's constructor and method surface before sweeping, per
  the judgement this row called out.
- Traced what each broken module's `record` variable actually was, and
  confirmed the rename is NOT shape-preserving.
- Located the current production-test replacement already used by identical
  live consumers elsewhere in the tree and mirrored it exactly.
- Swept all three imports and call sites; ran the collectability harness that
  first caught the break; ran the three modules for real.

## Outcome

**The rename is NOT shape-preserving, and a mechanical find-replace onto
`UserProfileSnapshotRepository` would have produced a worse defect than the
one it fixed.** The new class's constructor keyword shape
(`bucket_id=`, `objects=`) matches the retired one, but its `save()` persists
an immutable, filing-time `UserProfileSnapshot` (`snapshot_id`,
`canonical_hash` required) keyed by `snapshot_id`, not the mutable, editable
`UserProfileRecord` (`record_revision`, `content_digest`, `facts`) all three
broken modules actually construct and pass to `save()`. A blind rename would
have imported cleanly and then raised `pydantic.ValidationError` at test run
time — the exact "worse than an honest ImportError" trap this row warned
against.

The correct current replacement for writing a live `UserProfileRecord` is not
in `application.user_profile` at all: the architecture moved record writes
behind the encrypted custody capsule (`ProfileCapsuleLifecycle` plus a
session-bound `ProfileRecordRepository`), and the test-owned door for it is
`cadrumo.tests.profile_capsule.seed_test_profile_record`. This is the exact
call already used by other live production consumers seeding a
`UserProfileRecord` under the identical `isolated_cli_runtime_profile`
fixture for the identical purpose (e.g. the CLI calculation-oracle and
projection test suites), so the sweep mirrors an established, not invented,
pattern: replaced `UserProfileLifecycleRepository(bucket_id=..., objects=
runtime_profile.repository).save(record)` with
`seed_test_profile_record(record, root=runtime_profile.storage_root,
label=...)` in all three files, dropping the now-dead import and the
now-unused `runtime_profile.repository` field read.

**Collectability verdict before: broken.** The three modules failed to
collect with `ImportError: cannot import name 'UserProfileLifecycleRepository'
from 'cadrumo.application.user_profile'`.

**Collectability verdict after: fixed and proven with the mechanism that
found it.** `just test-harness` passes 5/5, including
`test_every_test_module_in_the_tree_is_collectable` — the harness verdict this
row exists to satisfy. A direct `pytest --collect-only -m "unit or
integration"` on the three modules collects all 13 tests, zero errors.

**The swept tests do NOT yet pass their own assertions, and this is reported
rather than patched.** Running the three modules for real
(`pytest -m integration -n0 ... --timeout=900`) surfaces a distinct,
newly-discovered, tree-wide pre-existing defect unrelated to this sweep:
`seed_test_profile_record`'s capsule creation (`ProfileCapsuleLifecycle.create`
-> a Windows no-replace directory rename) targets the exact same
`<root>/buckets/<profile_id>` path that `isolated_cli_runtime_profile`'s
underlying `provision_bucket_directory` pre-creates as a raw bucket directory,
so every seed call refuses with `ProfileCustodyRecordError("profile capsule
destination already exists")`. This is NOT caused by this sweep: a scratch
probe reproducing the identical fixture-plus-seed combination fails
identically outside these three files, and the established reference pattern
this sweep mirrors (`entrypoints/cli/tests/test_modelo_calculation_through_
real_cli.py`, `test_modelo_projection.py`) is independently red on HEAD too —
masked there by an unrelated, also-pre-existing `schema_version=1` literal
that predates the canonical schema version (now 6). Neither reference file's
own docstrings, nor this campaign's plan, name this defect. It sits in
`cadrumo.tests.secure_sql` / `cadrumo.tests.bucket_layout` /
`cadrumo.tests.profile_capsule`, none of which are in this row's ownership
(`dev/agent_eval/**`), and fixing it is a materially different, wider-blast
step than sweeping three import statements onto their correct replacement.
Per this row's own instruction, a golden test failing past its import is a
separate finding, not something to patch here or paper over by adjusting the
goldens.

## Notes

Report for the dispatching session: this Step's literal deliverable (the
three modules import and collect again, proven by the exact collectability
verdict that caught the original break) is complete and verified. Full
pass-their-own-assertions is blocked by the newly-found capsule/raw-bucket
directory collision described above, which is a pre-existing, tree-wide test
infrastructure defect outside this row's scope and ownership — recommend a
separate row against `cadrumo.tests.secure_sql` /
`cadrumo.tests.bucket_layout` / `cadrumo.tests.profile_capsule` to reconcile
`isolated_cli_runtime_profile`'s raw bucket pre-provisioning with
`seed_test_profile_record`'s capsule no-replace-rename publication target.

A peer's broad commit (`8407342720`, subject naming an unrelated custody
path-identity sweep) captured this Step's file edits mid-step. No commit was
made from this Step's execution; the content is intact in the same commit,
the attribution is not, and it is recorded here because that commit's subject
says nothing about the evaluation-harness sweep.
