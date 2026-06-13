---
tags:
  - "#research"
  - "#profile-lifecycle-disaster"
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-operator-blind-fumbler-testimony-audit]]"
  - "[[2026-05-19-operator-blind-newcomer-testimony-audit]]"
  - "[[2026-05-19-operator-blind-dual-testimony-audit]]"
  - "[[2026-05-19-operator-blind-returning-testimony-audit]]"
  - "[[2026-05-19-operator-testimonial-audit]]"
  - "[[2026-05-19-profile-lifecycle-disaster-research]]"
---

# profile-lifecycle-disaster axis E: failure-mode operator experience
Research axis E for the profile-lifecycle-disaster recovery campaign.
Maps every observable failure mode to its operator-facing manifestation today,
proposes the operator-grade replacement behaviour, and identifies the missing
wiring that allows twenty of twenty-eight failure modes to surface as the
catch-all unexpected-internal-error with no actionable suggestion.

## Failure mode catalogue

### Group A: session lifecycle failures

A1 cold-start: no profile, no pointer file, no session.
Command: any verb that touches the SQLAlchemy engine.
Today: NoActiveBucketSessionError propagates to command_error_boundary,
is not an AeatError subclass so wraps as CliUnexpectedBoundaryError.
Operator sees: The command failed due to an unexpected internal error.
Suggestion printed: Run aeat config repair.
Following the suggestion runs repair, which crashes with the same error.
Proposed: detect no-profile state before engine construction.
Route to CliRefusedBoundaryError: No profile found.
Run aeat config profile create NAME to get started.

A2 active-profile pointer file present but bucket directory absent.
Today: Settings.aeat_database_url resolves from the pointer, engine URL points
to a path that does not exist, SQLAlchemy raises OperationalError.
Reaches CliUnexpectedBoundaryError. Operator has no recovery path.
Proposed: check bucket directory existence before engine construction;
route to CliRefusedBoundaryError with suggestion to run profile create or repair.

A3 pointer file present, bucket directory present, manifest absent.
Today: show verb calls read_profile_bucket which returns None,
raises CliRefusedBoundaryError(Unknown profile). This is the correct surface
but the wrong message: the profile was created successfully from the operator
perspective so unknown is confusing. The real cause is a half-written create.
Proposed: distinguish never-created from corrupted using the pointer file;
emit: Profile storage is incomplete. Run aeat config repair to recover.

A4 session expired during long-running command.
evaluate_idle(session, now, configured_minutes) exists in _idle_timeout.py
and returns IdleEvaluation(expired, remaining_seconds). It is never called
in production. BucketSession.is_expired(now) is implemented but never polled.
Today: if a session were ever activated (it is not), expiry would never be
detected and stale keys would remain in the buffer indefinitely.
Proposed: poll is_expired before each encrypted-column operation;
on expiry raise BucketLockedError and surface as CliRefusedBoundaryError:
Session expired after N minutes of inactivity.
Run aeat config profile switch NAME to re-unlock.

A5 activate_session never entered by production CLI root.
The contextmanager in _active_session.py is called only by test fixtures.
EphemeralMasterKeyProvider.__enter__ and UnsecuredMasterKeyProvider.__enter__
both call activate_session but neither is invoked by the CLI root callback.
Today: every encrypted-column operation in production raises NoActiveBucketSessionError.
This is the root cause of F1 in the synthesis audit.
Proposed: CLI root callback enters get_master_key_provider().__enter__() via
ctx.with_resource(); this enters activate_session as a side effect.

A6 SIGKILL during session: lock file orphaned.
_AtexitRegistry._release_all() releases the bucket lockfile at interpreter shutdown
but is bypassed by SIGKILL and OOM kills.
Today: BucketBusyError is not reachable in production (session never activated).
When session is wired, a SIGKILLed process leaves .lock with its PID.
acquire_lock calls _reclaim_if_stale: if the PID is not alive it reclaims the lock.
If the PID is alive it waits wait_seconds then raises BucketBusyError(bucket_id, holding_pid).
Proposed: BucketBusyError is already structured with bucket_id and holding_pid;
surface as CliRefusedBoundaryError: Profile NAME is locked by process PID.
If that process is not running, delete the .lock file and retry.

A7 concurrent profile switch from two terminals.
Today: not reachable. When session is wired, two terminals activating the same
bucket will race on the lockfile. The loser receives BucketBusyError.
Proposed: same surface as A6.

A8 unsecured backend with AEAT_ALLOW_UNENCRYPTED unset.
UnsecuredMasterKeyProvider raises UnsecuredModeRefusedError when
AEAT_SECRET_STORE_BACKEND=unsecured but AEAT_ALLOW_UNENCRYPTED is falsy.
UnsecuredModeRefusedError inherits StorageError -> AeatError so it is forwarded
as a structured error. But the message does not tell the operator to set AEAT_ALLOW_UNENCRYPTED=1.
Proposed: add suggestion field: Set AEAT_ALLOW_UNENCRYPTED=1 to permit unsecured mode.

A9 KDF version mismatch on key unwrap.
MasterKeyKdfVersionError raised by _check_kdf_version in FileFallbackMasterKeyProvider.
It inherits MasterKeyUnavailableError -> AeatError so is forwarded as structured.
Message contains no recovery path.
Proposed: suggestion: The key-derivation version has changed.
Run aeat config auth migrate-kdf to re-wrap the master key.

A10 passphrase too short.
PassphraseTooShortError raised by _validate_passphrase_strength.
It is an AeatError so it is forwarded as a structured error.
Proposed: already reasonable; confirm suggestion field references minimum length.

### Group B: profile create/read disagreement failures

B1 profile create exits 0, profile show raises Unknown profile.
Root cause: wizard create path calls register_active_profile which writes the
UserProfileRecord and the pointer file but never calls
_provision_bucket_directory_idempotent. read_profile_bucket returns None.
show raises CliRefusedBoundaryError(Unknown profile: NAME).
Today: exit 2, clean refusal, but completely mysterious to an operator who
just watched create succeed.
Proposed: atomic create transaction (axis B contract); once manifest is written
show will find it.

B2 duplicate profile create: second create NAME finds manifest, should refuse.
Today: wizard/_persistence.py:91 checks read_profile_bucket(profile_name).
Since wizard create never writes manifest, second create finds None and calls
register_active_profile again. _lifecycle.py raises ProfileAlreadyExistsError.
This propagates out of repository.update and reaches CliUnexpectedBoundaryError.
ProfileAlreadyExistsError is an AeatError subclass so it is forwarded as structured,
but the message says nothing helpful.
Proposed: manifest-scan check is the authoritative duplicate gate.
If manifest exists: CliRefusedBoundaryError: Profile NAME already exists.

B3 profile list shows only one profile regardless of how many were created.
config_list calls _profile_state().load() (session required) then shows only
the active SecureObjectRepository record. Does not call list_profile_buckets().
list_profile_buckets() is session-free (pure filesystem scan) but never reached.
Proposed: list must call list_profile_buckets() directly; no session required.

B4 profile switch: UserProfileRecord written, pointer written, but no manifest.
switch calls service.read(profile_id) which reads from SecureObjectRepository.
If the wizard create path wrote the record (but not the manifest), switch succeeds.
show then fails because show reads manifest.
The three verbs create/switch/show each consult a different artefact.
Proposed: collapse to manifest as single source of truth for existence;
UserProfileRecord is supplementary metadata, not the existence gate.

B5 profile show with unknown name (not in manifest scan).
Today: read_profile_bucket returns None -> CliRefusedBoundaryError(Unknown profile: NAME).
This is already correct operator experience. Preserve.

B6 profile create with path-traversal name (../evil).
read_profile_bucket catches ValueError (path containment) and returns None silently.
The create verb then proceeds without the duplicate-name check passing.
Proposed: validate name at the CLI boundary before any disk operation;
raise CliRefusedBoundaryError for names containing path separators.

B7 settings AEAT_DATABASE_URL empty on cold start.
Settings model_validator raises StorageError: aeat_database_url is empty; set AEAT_DATABASE_URL.
Operator has no idea what AEAT_DATABASE_URL is or how to derive it.
Proposed: model_validator detects no-profile state and raises CliRefusedBoundaryError
with message: No profile is active. Run aeat config profile create NAME to begin.

B8 repair reset-state: escape hatch welded shut.
repair_reset_state calls reset_workflow_state() which calls workflow_state_repository()
which constructs SecureObjectRepository which calls get_active_master_key()
which raises NoActiveBucketSessionError before any reset can occur.
The recovery verb requires the session it is meant to clear.
Proposed: reset_workflow_state must bypass session; it should delete the SQLite
file directly (os.unlink) and the pointer file (os.unlink) without touching
the encrypted-column path.

B9 profile delete hangs without output.
config_profile_delete with no NAME argument blocks on a TTY prompt
without flushing the prompt text first (stdout buffering).
Proposed: flush stdout before any blocking prompt.
Also: trash-rename pattern mandated by the ADR is absent from config_profile_delete.

### Group C: key-provider failures

C1 OS keychain locked (screen locked).
KeyringMasterKeyProvider raises MasterKeyKeychainLockedError.
It inherits MasterKeyUnavailableError -> AeatError so forwarded as structured.
Message does not tell operator to unlock screen or authenticate keychain.
Proposed: suggestion: Unlock your OS keychain or screen lock, then retry.

C2 keyring library not available.
KeyringMasterKeyProvider.probe_backend raises KeyringUnavailableError.
Forwarded as structured. Message does not suggest AEAT_SECRET_STORE_BACKEND=file.
Proposed: suggestion: Install the keyring package or set AEAT_SECRET_STORE_BACKEND=file.

C3 file-fallback passphrase mismatch.
FileFallbackMasterKeyProvider raises MasterKeyPassphraseMismatchError.
Forwarded as structured AeatError. Message: passphrase did not match.
No reference to complete_recovery (re-wrap under new passphrase).
Proposed: suggestion: If you have the correct passphrase retry.
To reset the key, run aeat config auth recover.

C4 key material file missing.
MasterKeyMaterialMissingError raised when the wrapped-key file is absent.
Forwarded as structured. No recovery path in message.
Proposed: suggestion: The master key file is missing.
If you have a backup, restore it. Otherwise run aeat config auth recover.

C5 torn key state: partial mint interrupted.
FileFallbackMasterKeyProvider._get_master_key detects torn state:
tmp file exists but canonical path does not.
Today: torn state detection exists in _get_master_key but there is no production
path that resumes or cleans up the partial write.
Proposed: torn-state detection should call complete_recovery automatically
if the operator can provide the passphrase, otherwise surface as CliRefusedBoundaryError
with path to the tmp file and instructions to restore or delete it.

### Group D: log and diagnostic failures

D1 repair logs MemoryError.
repair_logs reads the entire log file into memory with path.read_text().splitlines()[-count:].
MemoryError is a BaseException subclass; command_error_boundary catches Exception,
so MemoryError propagates uncaught to Typer which prints a raw traceback.
Proposed: read log file with a streaming tail (seek to end, read last N KB).

D2 six UserWarning lines on every invocation.
Registry validation emits six UserWarning lines on stdout before any verb executes.
Proposed: demote to logging.WARNING (captured by log handler, not printed to stdout).

D3 10-minute silent hang on cold start.
Root cause is F11 from synthesis audit: aeat.domain.vat import fails.
The registry validation subprocess runs first (no progress output) then the
ModuleNotFoundError surfaces after 10+ minutes.
Proposed: fix the broken import (rename aeat.domain.vat -> aeat.domain.iva callers).
Independent of session lifecycle fix.

D4 help-text placeholders shipped.
aeat --help shows literal Heading and Paragraph two roots tokens.
aeat config --help lists profile view which raises No such command.
Proposed: regenerate help-card strings; remove dead verb references.

## Per-failure today-vs-proposed table

| ID | Failure | Today surface | Proposed surface |
|----|---------|---------------------------------|----------------------------------|
| A1 | cold-start no profile | CliUnexpectedBoundaryError; repair suggestion (broken) | CliRefusedBoundaryError; suggestion: profile create |
| A2 | pointer present, bucket absent | CliUnexpectedBoundaryError; OperationalError | CliRefusedBoundaryError; suggestion: repair |
| A3 | pointer present, manifest absent | CliRefusedBoundaryError Unknown profile (confusing) | CliRefusedBoundaryError Profile storage incomplete |
| A4 | session expired | Not reachable (session never wired) | CliRefusedBoundaryError; re-switch suggestion |
| A5 | session never activated | CliUnexpectedBoundaryError on every encrypted op | CLI root enters provider context; session active |
| A6 | SIGKILL orphaned lock | Not reachable | CliRefusedBoundaryError; PID and lock path in message |
| A7 | concurrent switch race | Not reachable | CliRefusedBoundaryError; same as A6 |
| A8 | unsecured mode refused | Structured; no AEAT_ALLOW_UNENCRYPTED hint | Add env-var suggestion to error |
| A9 | KDF version mismatch | Structured; no suggestion | suggest migrate-kdf verb |
| A10 | passphrase too short | Structured; reasonable | Confirm min-length in suggestion |
| B1 | create/show disagreement | CliRefusedBoundaryError Unknown profile | Fixed by atomic create (manifest written) |
| B2 | duplicate create | CliUnexpectedBoundaryError wrapping AeatError | CliRefusedBoundaryError; manifest-scan gate |
| B3 | list shows one profile | Only active record; no manifest scan | list calls list_profile_buckets(); session-free |
| B4 | create/switch/show three sources | Three artefacts consulted | Manifest as single existence truth |
| B5 | show unknown name | CliRefusedBoundaryError (correct) | Preserve |
| B6 | path-traversal name | Silently proceeds | CliRefusedBoundaryError at name-validation boundary |
| B7 | AEAT_DATABASE_URL empty | StorageError; no next step | CliRefusedBoundaryError; suggest profile create |
| B8 | repair reset-state welded | NoActiveBucketSessionError; circular | reset_workflow_state bypasses session; deletes files |
| B9 | delete hangs | Blocks without output | Flush stdout; implement trash-rename pattern |
| C1 | keychain locked | Structured; no unlock hint | Add unlock-screen suggestion |
| C2 | keyring unavailable | Structured; no fallback hint | Suggest AEAT_SECRET_STORE_BACKEND=file |
| C3 | passphrase mismatch | Structured; no recovery hint | Suggest auth recover |
| C4 | key material missing | Structured; no recovery hint | Suggest backup restore or auth recover |
| C5 | torn key state | Unhandled partial state | Auto-detect; surface path; suggest recover |
| D1 | repair logs MemoryError | BaseException uncaught; raw traceback | Streaming tail read; no full-file load |
| D2 | UserWarning on every invocation | Six lines before verb output | Demote to logging.WARNING |
| D3 | 10-min silent hang | Broken import + silent registry validation | Fix aeat.domain.vat callers |
| D4 | help-text placeholders | Literal template tokens in output | Regenerate; remove dead verb references |

## Recovery-path verification

Every documented recovery verb on the chore/eliminate-shims branch was traced
against its production call graph. All six are either welded shut or dead.

aeat config repair reset-state --yes
Calls repair_reset_state -> reset_workflow_state -> workflow_state_repository()
-> SecureObjectRepository.__init__ -> get_active_master_key()
-> NoActiveBucketSessionError. Cannot reset state it cannot read.
Status: welded shut.

aeat config repair (bare)
Calls repair_wizard which calls workflow_state_repository().load().
Same path, same crash.
Status: welded shut.

aeat config profile switch NAME
Suggested by NoActiveBucketSessionError message. switch calls
build_lifecycle_service -> SecureObjectRepository -> get_active_master_key()
-> NoActiveBucketSessionError. The suggestion is circular.
Status: welded shut.

aeat config reset --scope all
Calls _reset_all -> workflow_state_repository().load(). Same crash.
Status: welded shut.

aeat config profile create NAME (as recovery)
wizard/_commands.py:471 calls workflow_state_repository() before writing any artefact.
Crashes with NoActiveBucketSessionError before create can do anything.
Status: welded shut for cold-start.

aeat config repair logs
Does not require session. Calls path.read_text().splitlines()[-count:].
Raises MemoryError on large log files.
Status: raises on normal-size logs (D1).

Summary: zero of six recovery verbs are functional from cold start.

## Idle-timeout and session-expired contract

evaluate_idle(session, now, configured_minutes) is implemented in _idle_timeout.py
and returns IdleEvaluation(expired: bool, remaining_seconds: float).
DEFAULT_IDLE_LOCK_MINUTES = 15 (from Settings.aeat_bucket_default_idle_lock_minutes).
BucketSession.is_expired(now) returns True when now >= idle_deadline or sealed.
Neither function is called in production today.

Proposed five-point idle-timeout contract:

Point 1. Poll is_expired(datetime.now(UTC)) at the start of every encrypted-column
operation inside SecureObjectRepository. If expired raise BucketLockedError.

Point 2. BucketLockedError surfaces as CliRefusedBoundaryError:
Session for profile NAME expired after N minutes of inactivity.
Run aeat config profile switch NAME to re-unlock.
The session carries bucket_id; use it to populate NAME in the message.

Point 3. On clean exit (SystemExit, KeyboardInterrupt) the CLI root calls
session.close() which zeroises key buffers.

Point 4. Idle window is configurable via AEAT_BUCKET_DEFAULT_IDLE_LOCK_MINUTES
(already wired in Settings). No new env var needed.

Point 5. The operator-facing suggestion must quote the actual profile name,
not the generic NAME token. The session carries bucket_id; use it.

## Half-deleted bucket recovery

A half-deleted bucket is any state where some but not all artefacts are present.
The four observable half-states and proposed behaviours:

State 1: pointer file present, bucket directory absent, manifest absent.
Proposed: repair detects missing directory; offers to delete pointer file and
start fresh, or to re-create the bucket directory and resume.

State 2: pointer file present, bucket directory present, manifest absent.
Proposed: repair detects missing manifest; offers to write manifest from
UserProfileRecord if the SecureObjectRepository record is readable,
otherwise delete the orphaned directory and pointer and start fresh.

State 3: manifest present, UserProfileRecord absent.
Proposed: repair re-registers the UserProfileRecord from the manifest.
No data loss: manifest is the source of truth for existence.

State 4: all artefacts present, lockfile stale.
Proposed: acquire_lock._reclaim_if_stale already handles this (checks PID liveness).
No new code needed. Surface the existing BucketBusyError message.

All four repair paths require repair to be session-free, operating at the
filesystem layer, not the SecureObjectRepository layer.

## Comparable CLI patterns

Four tools handle session/credential failures with operator-grade UX.

bw (Bitwarden CLI):
bw lock seals the in-memory session. Every subsequent command raises
You are not logged in. with suggestion bw unlock or bw login.
The suggestion is verb-specific. bw never routes to a generic repair verb.

gcloud:
If the OAuth token is expired, gcloud prints a structured error followed by
Please run: gcloud auth login.
The suggestion names the exact verb. The error is never unexpected internal error.

gh (GitHub CLI):
gh auth status exits with a structured message when unauthenticated.
Every other command that requires auth prints gh auth login as the fix.
The auth state is checked at the command boundary, not inside the adapter.

git:
git credential fill fails with a structured message naming the credential helper.
git never emits unexpected internal error for credential failures.

Common pattern across all four:
Session/credential failure is detected at the command boundary.
The error message names the exact recovery verb.
There is no generic repair/reset escape hatch; each failure has one specific fix.

## Open questions for the ADR writer

Q1. Should the CLI root callback enter the master-key provider context unconditionally
(activating a session for every verb including --help and --version) or only
for verbs that require a session? Unconditional is simpler but adds latency to
informational verbs. Conditional requires a session-required marker on each verb.

Q2. Should NoActiveBucketSessionError be retired entirely once the CLI root wires
the session, or retained as a programming-contract guard?
Retaining it catches future callers that bypass the CLI root.
Recommendation: retain as a guard, never expose to operators.

Q3. Should repair be reimplemented as a session-free filesystem doctor that
does not touch SecureObjectRepository at all, or should it have a two-phase
design: filesystem phase (session-free) then encrypted-record phase (session-required)?

Q4. Should BucketLockedError (idle timeout) trigger an interactive re-auth prompt
(passphrase re-entry in the same process) or require a separate switch verb invocation?
Interactive re-auth is better UX but requires the passphrase prompter to be
injectable into the session lifecycle, not only the provider __enter__.

Q5. Should the trash-rename pattern for profile delete be implemented in the
CLI verb (CLI layer owns the rename) or in ProfileLifecycleService.remove
(domain layer owns the rename)?
Domain-layer ownership is consistent with the atomic-create contract.

Q6. list_profile_buckets() is session-free today. Should config_list call it
directly (bypassing _profile_state().load()) so that list works from cold start,
or should list require a session to show active-profile metadata alongside the names?
Recommendation: list names session-free; show facts session-required.

Q7. Should the CliUnexpectedBoundaryError catch-all be eliminated entirely,
requiring every AeatError subclass to map to a specific CliRefusedBoundaryError
before it reaches the CLI boundary? This forces explicit error handling per failure
mode and makes the catch-all a programming error rather than a runtime escape.

## Constraints inherited by the ADR writer

tr() locale requirement: every operator-facing string in the proposed surface
must go through tr(). Error messages, suggestions, and recovery hints are
operator-facing strings. Locale keys are added via python -m aeat.locales scaffold
then audit. No naked English strings in CLI output.

Error registry constraint: the proposed CliRefusedBoundaryError replacements
must be registered error types with code, message template, and suggestion field.
They must not be ad-hoc strings assembled at the call site.

Recovery-verb constraint: the recovery verbs named in suggestion fields must
actually be functional before the suggestion is shipped. A suggestion that routes
to a broken verb is worse than no suggestion.

Provider protocol constraint: EphemeralMasterKeyProvider, UnsecuredMasterKeyProvider,
FileFallbackMasterKeyProvider, and KeyringMasterKeyProvider all implement
__enter__/__exit__ and call activate_session. The CLI root should enter whichever
provider is active via get_master_key_provider().__enter__(). No new protocol needed.

No shims constraint: the cold-start session bootstrap must not be a shim wrapping
the old call graph. The CLI root callback must directly enter the provider context.
The existing _root callback in entrypoints/cli/__init__.py is the correct insertion point.

