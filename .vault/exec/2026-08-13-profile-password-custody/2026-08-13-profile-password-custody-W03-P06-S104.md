---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:1c8eadea3518fcbba2619f2b970324d0747ec5ab8905a6c886e1154603ec3da0'
step_id: 'S104'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule per family whether the capabilities the capsule cutover removed should be restored, the sandbox and archive families being wiring rather than building because their application layer survived, the four single profile verbs being unassessed, and the subject-access-request surface being recoverable from history rather than greenfield since its test module still asserts a working implementation and the cutover commit is what deleted it

## Scope

- `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/entrypoints/cli/_config/`

## Description

- Read `bucket_maintenance`'s current `__init__.py`/`_service.py` (163 lines,
  down from a service that once carried archive/restore/sandbox mutation)
  and its own docstring inventory of what was removed and what survives.
- Located the cutover commit (`7c062ed17e`, "make the custody capsule the
  sole profile authority") and read its full diffstat and the deleted
  content of `_sandbox.py`, `_bucket_archive.py` and `_profile_bundle.py`.
- Read `ProfileCapsuleLifecycle` in
  `src/cadrumo/application/user_profile/_lifecycle.py` to establish which
  primitives (`create`, `restore`, `rename_label`, `select`, `prepare_delete`/
  `confirm_delete`/`delete`) genuinely survive as reusable building blocks.
- Confirmed `config profile --help` lists no `delete`, `duplicate`, `rename`,
  `archive`, `restore`, `subject-access-request`, `export`/`import`, or
  sandbox verb today.
- Ran the live `subject-access-request` test module and captured the
  `Unknown command 'subject-access-request'` failure to
  `s104_sar_test.log` in the scratchpad directory.
- Checked `ProfileSetupState` in `domain/user_profile/_values.py`: only
  `INCOMPLETE`/`COMPLETE` exist; no archived/dormant state axis survives.
- Cross-checked every finding against `W03.P06.S59` (the seventeen-subtree
  ruling), `W05.P08.S134`/`S154` (the deletion-surface ruling and its
  retention-producer precondition), `W03.P06.S66` (the bundle-transfer
  ruling), and the standing capabilities-removed-without-a-decision audit.
- Received a parallel per-verb assessment from a peer session (referred to
  here as "S34") covering the same four verbs, and verified its four claims
  directly against source rather than accepting them on report: the
  retention-floor guard function, the live `--help` refusal for `rename`/
  `delete`/`archive`, the `_profile_inspect.py` docstring citing a deleted
  sibling module, and the orphaned `RenameBucketCommand` import. All four
  confirmed as stated; incorporated below with attribution.

## Outcome

**Per-family verdicts below. None collapses to a single answer, and two
correct the plan row's own premise where the code disagrees with it.**

### Sandbox family — RESTORE IF DEMANDED, and it is BUILDING, not wiring

The row states sandbox is wiring "because its application layer survived."
That premise does not hold under inspection. `_sandbox.py` (838 lines,
`create_sandbox`/`discard_sandbox`/`archive_sandbox`/`restore_sandbox`/
`merge_sandbox`, a `SandboxMergeScope` enum, five typed command/result pairs
and five domain-specific error types) was deleted wholesale in the cutover
with no successor of its own. What survives is only the generic capsule
`create`/`restore`/`select`/`delete` primitives on `ProfileCapsuleLifecycle` —
the same primitives every other family in this ruling draws on, not
sandbox-specific logic. Sandbox was a full branch-and-merge workflow (stage
trial edits off a source profile, discard or archive the branch, merge a
scoped set of changes back), and none of that composition logic exists
anywhere in the tree today. **Restoring it means re-authoring roughly the
838-line surface on top of the surviving primitives, not wiring an existing
implementation to a verb.** If there is a real operator demand for
trial-edit branching, it is a genuine build; if there is not, retire it
formally and do not carry the five orphaned error types and command/result
models as residue.

### Archive family — RETIRE, and it is BUILDING too, for a sharper reason

Also framed by the row as wiring; also does not hold, and the evidence is
stronger here than for sandbox — and specifically for archive INSPECT,
independently corroborated by "S34"'s parallel assessment: `ProfileCapsuleLifecycle`
has no inspect or soft-tombstone method, the still-live `_sealed_archive_reader.py`
adapter has zero production callers, and `entrypoints/cli/tests/test_profile_archive_roundtrip.py`
is six of seven tests red against the removed surface. `bucket_maintenance/__init__.py`'s
own current docstring states directly: "bucket archive (reversible dormancy),
bucket restore, sealed-archive export/import/inspect... have no successor
primitive at all." That is corroborated a third way: the cutover commit's
own message states `UserProfileStatus` and its tombstone/reactivate arms
gave way to `ProfileSetupState`, which today carries exactly two members
(`INCOMPLETE`, `COMPLETE`) — there is no ARCHIVED or DORMANT state left on
the domain record to restore "reversible dormancy" onto. Restoring bucket
archive is not wiring a surviving implementation to a verb; it is
reintroducing a status axis that was deliberately eliminated in the same
architectural simplification this whole campaign is built on, which is a
domain-model change, not a CLI-exposure change. **Recommend RETIRE formally,
with the honest note that this is a decision to make (there is genuinely no
route to name today), not a fact this record is merely recording.** The
replacement route for "I no longer need this profile but might later": keep
it as-is (a complete, unlisted profile costs nothing extra to retain) or
delete it outright once `W05.P08.S154` lands; there is no operator need this
specifically serves that `list`/`delete` cannot.

**Residue: already cleaned inside `bucket_maintenance` itself, still live
outside it.** "S34"'s parallel pass already deleted the fourteen producerless
Rename/Delete/Archive/Restore/Export/Import/Inspect pydantic Command/Result
classes from `bucket_maintenance/_contracts.py` and corrected a stale module
docstring describing the removed sandbox lifecycle as live — verified: the
package's `_contracts.py` (143 lines) and `__init__.py` (68 lines) carry none
of that residue today. Do not re-nominate it. What remains live and orphaned
is OUTSIDE `bucket_maintenance`, in this row's other scoped directory:
`entrypoints/cli/_config/_profile_bundle_flow.py` (dead export/import
wizard-flow code with zero callers — this is `W03.P06.S66`'s subject, not
re-decided here), `entrypoints/cli/_config/_profile_inspect.py` (its
docstring still names `._bucket_archive` as a sibling module, confirmed at
line 10, though `_bucket_archive.py` was deleted whole by the cutover
commit), and `application/tests/test_config_reset_concurrency.py` (imports
`RenameBucketCommand`, confirmed absent from source — only stale `.pyc`
cache files reference it, alongside two rename-service test modules also
already deleted from source). Any orphaned `archive`/`restore`/`inspect`
payload-schema or error-registry entries in `_config_payloads.py` follow the
same shape `W03.P06.S59` already resolved for its sixteen residue verbs —
not re-swept here since this row's scope was `bucket_maintenance/` and
`_config/`, and `S59` already owns that specific sweep pattern.

**Note:** sealed-archive export/import/inspect (a backup-file transport, the
`_bucket_archive.py` verbs) is a DIFFERENT capability from the per-profile
recovery-artifact export/import already rowed and wired in `W03.P05.S14`/
`S15` against `adapters/persistence/storage/custody/_recovery_artifact.py`
(467 lines, a real, guarded, already-existing production module). Do not
conflate the two: `S14`/`S15` is live work on a surviving primitive; this
archive-family verdict concerns the separate, primitive-less bucket-archive
concept.

### The four single profile verbs — delete, duplicate, rename, bundle export/import

Not uniformly unassessed, contrary to the row's framing; disposition per verb:

- **rename — WIRING, genuinely trivial, ZERO CLI callers confirmed live.**
  `ProfileCapsuleLifecycle.rename_label(*, profile_id, label,
  expected_label_revision, expected_content_digest)` is a complete,
  already-used primitive (the label-authority CAS path the commit message
  describes: "renames advance it under root-then-profile locking, and a
  same-UUID substitution is refused"). Every argument is resolvable from a
  loaded record. `aeat config profile rename --help` returns
  `Error: No such command 'rename'.`, run live and confirmed. Exposing
  `config profile rename` is a Typer wrapper over an existing call, sized
  identically to the other single-verb work `W03.P06.S16` already scopes.
- **delete — WIRING, already ruled, NOT newly unassessed, and the blocking
  guard is a LIVE deliberate protection, not a stray refusal.**
  `W05.P08.S134` already established this is deliberate replacement (not
  collateral loss): the old primitives are gone on purpose,
  `ProfileCapsuleLifecycle.prepare_delete`/`confirm_delete`/`delete` is the
  re-pointed, journalled, crash-resumable successor, and the re-pointing has
  landed. `aeat config profile delete --help` returns
  `Error: No such command 'delete'.`, confirmed live — there is no
  single-target delete CLI verb anywhere; the sole production caller of the
  delete primitives is the all-profile `config reset start --yes` flow. What
  blocks a genuine single-target verb is `_refuse_erase_inside_the_retention_floor`
  in `application/config_reset.py:688`, fed by the retention-snapshot chain
  from closed rows `S137`/`S155`/`S157` — a LIVE guard, not a retired one,
  and it is the direct, confirmed cause of six failing tests in
  `application/tests/test_config_reset.py`. Its named successor owner is the
  already-open `W05.P08.S154`, direction already set (grow the retention
  contract; do not narrow the legally-grounded refusal message).
  `W03.P06.S16` is already the row that exposes a single-target verb once
  `S154` lands, and that verb deserves its own single-target safety argument
  when it is built — deleting one profile is a different blast radius from
  deleting all of them, and S16 should say so rather than assume the
  all-profile guard transfers unchanged. This ruling does not re-decide
  `S134`; it confirms `S104` should not re-litigate a verb another row
  already ruled.
- **duplicate — near-wiring, small composition, no primitive of its own.**
  No `duplicate`/`clone` primitive exists anywhere in the tree (checked
  `application/user_profile`; every hit is unrelated label-collision
  vocabulary). Nothing was deleted here either — this capability may never
  have existed as a standalone verb. It composes cleanly from two surviving
  primitives: read the source profile's facts (`record_to_path_values`) and
  call `register_profile_with_credentials(label=new_label, passphrase=...,
  facts=source_facts)`. Sized as new-but-small: no domain-model change, no
  new persistence shape, one new CLI verb plus the fact-copy composition.
  Restore if there is operator demand for it; if not, no residue to delete
  since nothing currently claims it.
- **bundle export/import — WIRING, and this verb's final disposition
  belongs to `W03.P06.S66`, not this row.** The application layer survives
  intact (`application/user_profile/_bundle.py`, `_bundle_export.py`,
  `_bundle_encryption.py`, all live and exported today), and the old
  897-line `_profile_bundle.py` CLI wiring (which also carried the
  subject-access-request verb, see below) is fully recoverable from history
  at `7c062ed17e~1`. A narrower live equivalent already proves the
  application layer works today: `_manager_actions.py`'s `export_action`/
  `_run_export` is a working, if narrower, in-manager export with its
  transport hardcoded. `S66` is the more specific, already-open ruling on
  this exact surface (it additionally directs deleting two tests that "prove
  nothing" by asserting only a non-zero exit code on an unregistered verb) —
  this record's role is to confirm bundle export/import is WIRING-tier, not
  building, consistent with `S66`'s own framing, and defer the disposition
  specifics (which tests, which verb shape) to `S66`.

### Subject-access-request — RECOVERABLE FROM HISTORY, confirmed, and it carries
### a compliance obligation this ruling cannot discharge on its own

Confirmed live: `aeat config profile subject-access-request` is genuinely
absent (`Unknown command 'subject-access-request'`, reproduced against
`test_profile_subject_access_request.py`, six of six tests failing — one
group on the unresolved verb directly, the rest additionally on the
`create --quiet` refusal `W03.P06.S60` rules on separately, since the test's
own fixture creates its subject profile non-interactively). The verb and its
domain data lived in the SAME deleted `_profile_bundle.py` module as bundle
export/import (897 lines, deleted whole by the cutover commit), while the
serializer it depends on — `UserProfilePortableExport` and its supporting
`_bundle_export.py`/`_bundle.py`/`_bundle_encryption.py` — survives intact
in `application/user_profile`. So "recoverable from history" is precise, not
approximate: the domain model and the encryption/export machinery were never
touched; only the CLI verb wiring around them was deleted, and the deleted
wiring is legible in git history for whoever restores it.

**This ruling does NOT resolve the compliance question, and says so
explicitly rather than guessing.** The row and the standing audit both
frame SAR as a data-protection (GDPR-shaped) obligation rather than a
convenience; that framing is plausible on its face (an operator's own
personal-data export request) but this record found no accepted ADR, legal
review, or scope document in `.vault/` establishing WHICH obligation applies,
to which jurisdiction, on what timeline, or whether the retired verb was
ever a complete discharge of it in the first place (the old test module
proves the verb produced a parseable archive with named data categories; it
does not prove that constituted legal sufficiency). **Recommend this be
escalated to the operator for an explicit ruling on the obligation's scope**,
separately from the code-restoration question. What this record CAN say with
confidence: restoring the verb is cheap (wiring, not building — the same
tier as rename and bundle export), so cost is not a reason to defer the
compliance question, and "no operator has asked for it" is not a sufficient
answer to a legal obligation even if it were established, per the row's own
instruction. Until the obligation's scope is ruled, "no operator demand"
must not be read as this ruling's basis for retiring SAR — this ruling takes
no retirement position on SAR precisely because the compliance question is
open above it.

## Notes

Two corrections to the plan row's own framing are load-bearing findings on
their own, independent of the per-family verdicts: sandbox and archive are
NOT wiring (evidenced by the deleted 838-line sandbox module and the
docstring-stated absence of any archive successor, respectively), and delete
is NOT unassessed (it was already ruled in `W05.P08.S134` and sequenced
behind `W05.P08.S154`). Both are reported rather than silently corrected in
place, per the standing instruction to say so explicitly when disagreeing
with a load-bearing prior.

No `entrypoints/mcp/` directory exists in the current tree at all (checked
directly; `src/cadrumo/entrypoints/` contains only `cli/`,
`schema_surface.py` and `tests/`), so the MCP-surface angle `W03.P06.S59`
scoped itself against no longer has a target to sweep for any of these
families — noted for whoever next touches MCP tool registration, not chased
further here since it was out of this row's scope.

No source was modified. No plan checkbox was changed. The
`s104_sar_test.log`, `s104_profile_help.log`, and `s104_test_run.log`
captures live under the session scratchpad directory, not the repository.
