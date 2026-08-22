---
tags:
  - '#audit'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:687b2fad11f71910afff89666890715a9a90d53183ce33613a9cf151babe2869'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
  - "[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]"
---

# `profile-registration-password-policy` audit: `w01 p01 s02 core contract review`

## Scope

Commit `63617870cb` and current HEAD were reviewed against the accepted canonical
credential capability ADR, its research and incident reference, the active plan, and
the S02 execution record. Semantic discovery located the governing core and custody
surfaces before exact-symbol confirmation. The review covered the complete
`src/cadrumo/core/_credentials.py`, every live exact consumer of its removed and added
symbols, the public core facade, the commit diff, direct Unicode-boundary probes, and a
representative registration test collection.

The pure assessment correctly counts Python Unicode scalar values after refusing
surrogates, preserves composed and decomposed inputs without rewriting, accepts 15
through 256 scalars and 1,024 UTF-8 bytes, exposes only numeric facts plus finite typed
results, and keeps strength advisory. The byte-first ordering for overlapping upper
bounds is coherent with the requirement for an independently observable 1,025-byte
refusal: under Unicode's four-byte maximum, a 1,025-byte candidate necessarily also
exceeds 256 scalars. Ruff, formatting, and diff-hygiene checks passed for the owned
module. The repository state is nevertheless not independently coherent for the reason
below.

## Findings

### step-atomicity | high | The committed core change breaks the live public facade and registration import graph

`src/cadrumo/core/_credentials.py:37-51` removes
`NIST_PASSPHRASE_MIN_LENGTH`, `PassphraseStrength.TOO_SHORT`, and the public
`character_class_count`, and `src/cadrumo/core/_credentials.py:86` changes
`assess_passphrase_strength` from a required `minimum_length` API to a one-argument
advisory API. However, `src/cadrumo/core/__init__.py:155-159`,
`src/cadrumo/core/__init__.py:535`, `src/cadrumo/core/__init__.py:752`,
`src/cadrumo/core/__init__.py:1003`, and `src/cadrumo/core/__init__.py:1125` still
publish or lazily resolve the deleted names, while
`src/cadrumo/application/user_profile/_registration.py:39`,
`src/cadrumo/application/user_profile/_registration.py:63`,
`src/cadrumo/application/user_profile/_registration.py:115`, and
`src/cadrumo/application/user_profile/_registration.py:152` still import or call the
old contract. `src/cadrumo/adapters/inbound/tui/_registration_screen.py:120` and
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:131` also still require the
deleted enum member. Conversely, none of the new profile-specific types, constants, or
assessment function is exposed through the public core facade yet.

This is an observable repository break, not merely an unintegrated new feature:
accessing `cadrumo.core.NIST_PASSPHRASE_MIN_LENGTH` raises `AttributeError`, and pytest
cannot even collect `src/cadrumo/application/user_profile/tests/test_registration.py`
because `_registration.py` cannot import the removed constant. The S02 execution record
acknowledges this state at lines 47-49, but acknowledgment does not make a committed Step
independently coherent. S03 only changes the facade and S07 is deferred until W02, so
following the current plan literally would preserve broken application and TUI imports
across multiple intervening commits. This violates the architectural direction of a
public core authority consumed through stable boundaries and prevents meaningful gates
for subsequent Steps. It is HIGH and blocks continuing until the commit boundary or
Step sequence is repaired.

## Recommendations

- Resolve `step-atomicity` before dispatching further implementation. Make the canonical
  contract, public facade, and all compile-time consumers one coherent landing unit,
  either by amending/squashing the dependent S03 and consumer migration into S02 or by
  immediately landing the full dependency-ordered migration before unrelated W01 work.
  Do not restore aliases, shims, `TOO_SHORT`, or the eight-character constant: the
  accepted ADR requires their deletion rather than compatibility scaffolding.
- After migration, prove the repaired boundary with at least a core public-facade import
  probe and test collection for application registration and TUI registration, in
  addition to the planned core boundary tests. Keep the byte-before-upper-scalar
  precedence explicit in those tests by asserting a 257-astral-scalar / 1,028-byte
  candidate maps to `TOO_MANY_UTF8_BYTES`, while 257 ASCII scalars map to
  `TOO_MANY_SCALARS`.

## Resolution

The HIGH `step-atomicity` finding was resolved immediately in the S03 remediation
landing before unrelated W01 work. The core facade now exports every canonical
profile-password bound, assessment type, refusal reason, and assessor while the
deleted generic floor, refusal-strength member, and character-class export remain
absent. Registration, rotation, CLI composition, TUI rendering, package facades, and
their immediate tests consume the canonical assessment directly; no alias, shim, or
restored legacy symbol was introduced.

Registration and rotation refuse every invalid prospective password before custody
work. The existing precise localized minimum-length key remains in use for the lower
bound, while other expected shape refusals use the existing localized generic custody
refusal until the locale-owned reason-specific work in S07. The TUI renders invalid
assessments as refused independently of advisory strength and clears stale refusal
styling when the candidate becomes valid.

A public-facade import probe passed, both affected test modules collected all 15 tests,
and the focused real-behavior registration, rotation, and headless-TUI run passed all
22 tests. Exact repository search finds no live consumer of the removed constant,
enum member, public helper, application assessment model, or application minimum alias.
The remaining byte-precedence and exact Unicode matrix belongs to S04 as recommended.

### step-atomicity-remediation | low | Follow-up review confirms the blocking import-graph finding is closed

The follow-up review re-grounded current code and the accepted ADR semantically, then
confirmed the exact symbol graph and inspected remediation commits `2ca941531e` and
`61a63f2f8c`. Current `src/cadrumo/core/__init__.py:155-162`,
`src/cadrumo/core/__init__.py:551-553`, `src/cadrumo/core/__init__.py:711-712`,
`src/cadrumo/core/__init__.py:756`, and `src/cadrumo/core/__init__.py:1011-1013`
publish and lazily resolve the canonical bounds, assessment, refusal taxonomy, and
assessor. Registration consumes that assessor at
`src/cadrumo/application/user_profile/_registration.py:182`, rotation at
`src/cadrumo/application/user_profile/_passphrase_rotation.py:116`, TUI validation at
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:369` and
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:415`, and CLI composition at
`src/cadrumo/entrypoints/cli/_config/_manager_frontend.py:468-471`.

Exact repository search under `src/cadrumo` finds no
`NIST_PASSPHRASE_MIN_LENGTH`, `PassphraseStrength.TOO_SHORT`, public
`character_class_count`, old `minimum_length=` strength call, application
`PassphraseAssessment`, `PASSPHRASE_MINIMUM_LENGTH`, or `assess_passphrase` consumer.
The remaining `_character_class_count` is private implementation detail, not an alias or
compatibility export. A public-facade import probe succeeded; integration collection
found all 22 targeted registration, rotation, and headless-TUI tests; and the same 22
tests passed. No new HIGH or CRITICAL finding was identified. The former HIGH is fully
resolved, and W01.P01 may proceed to S04.

### s04-surrogate-coverage | medium | The contract test proves only the first high-surrogate code point

The mandatory S04 follow-up reviewed commit `ac5f1d5648` against the accepted ADR,
research, incident reference, plan, current core implementation, execution record, and
overlapping shared-worktree state after fresh semantic and exact-symbol discovery. The
literal boundary matrix in `src/cadrumo/core/tests/test_credentials.py:19-49` is
independent of production constants and will turn red for regressions at 14/15/256/257
scalars, 1,024/1,025 bytes, or the required byte-before-scalar precedence. The tests at
`src/cadrumo/core/tests/test_credentials.py:69-77` distinguish composed from decomposed
input by their submitted scalar and byte measurements; lines 80-97 pin the finite
dataclass field surface, typed numeric facts, frozen/slotted representation, and absence
of the candidate; and lines 100-105 prove that a strong invalid candidate remains
invalid while a fair valid candidate remains valid. These expectations are capable of
failing when their corresponding production guarantees regress. The commit adds only
the owned core test and its S04 execution record, Ruff and formatting pass, diff hygiene
passes, and the focused serial unit run passes all 11 cases, matching the execution
record.

The surrogate test at `src/cadrumo/core/tests/test_credentials.py:59-66`, however, uses
only `U+D800`. That proves refusal at the first high-surrogate value and proves that a
surrogate result carries no UTF-8 measurement, but it does not exercise any low
surrogate (`U+DC00` through `U+DFFF`) or the upper endpoint. A regression narrowing the
production check to the high-surrogate half would therefore keep all S04 tests green
while violating the ADR's refusal of every surrogate code point. Add an independently
parameterized low-surrogate case, preferably `U+DFFF` to pin the closed upper endpoint,
and assert the same `CONTAINS_SURROGATE`, scalar-count, and absent-byte facts. This is a
MEDIUM test-completeness defect, not a current production defect. No HIGH or CRITICAL
finding blocks S05, though S04 should be amended so its claimed surrogate guarantee is
complete rather than carried as later debt.

### s04-surrogate-coverage-closure | low | Both closed surrogate-range endpoints now bite

Commit `9924fffae6` closes `s04-surrogate-coverage` without production changes. After
fresh semantic ADR and code grounding plus exact-symbol confirmation, the amended test at
`src/cadrumo/core/tests/test_credentials.py:59-66` independently supplies `U+D800` and
`U+DFFF`. Both cases assert `CONTAINS_SURROGATE`, the unchanged submitted scalar count,
and no UTF-8 byte measurement. A regression that accepts either the high-surrogate start
or low-surrogate upper endpoint now turns the focused suite red, covering the entire
closed production range represented by `0xD800 <= ord(character) <= 0xDFFF`.

The remediation diff is limited to the owned test and S04 execution evidence. Ruff,
formatting, and commit diff hygiene pass; the focused serial core unit module passes all
12 cases; and the execution record reports the same amended count. The MEDIUM is closed.
No unresolved HIGH, CRITICAL, or MEDIUM finding remains from the S02-S04 core-contract
reviews.

### s05-secret-free-error-bite | medium | The safe-error test does not prove the candidate and measurements are absent

The mandatory S05 review grounded commit `c92641e881` against the accepted ADR,
research, incident reference, live plan, current source, execution record, commit history,
and overlapping shared-worktree state. `src/cadrumo/adapters/persistence/storage/custody/_records.py:75-82`
delegates validity exclusively to the public core assessment, maps only the finite
`reason.value` into an internal `ProfileCustodyPasswordError`, and returns the exact
strict UTF-8 encoding. Lines 85-92 strictly decode transport bytes, reapply the same
canonical assessment, and return the submitted sequence without normalization. The
duplicate custody bounds and old validators are absent from `_records.__all__`, both
custody facades, and exact repository consumers; direct facade probes confirm there are
no aliases or shims. The accepted 15/256 scalar and 1,024-byte boundaries,
1,025-byte-over-scalar precedence, every typed reason, malformed UTF-8, and
composed/decomposed exact roundtrips are exercised in
`src/cadrumo/adapters/persistence/storage/custody/tests/test_records.py:132-177`.

The generic parent and worker wrap operation still routes recovery secrets through the
same private password codec at `_kdf_supervision.py:362` and `_kdf_worker.py:130`. This
is the explicit ordered S06 dependency documented in the S05 execution record, changes
no recovery bytes, and introduces no parallel policy. The commit is limited to the two
facades, records codec, parent and worker consumers, focused tests, and its execution
record. Ruff, formatting, and diff hygiene pass; the 13 focused record tests pass; the
20 focused supervision/import-graph tests pass; and the repository-default custody lane
reproduces the recorded 207 passed and 10 marker-deselected result.

However, the test named
`test_password_contract_maps_every_canonical_reason_to_a_safe_custody_error` at
`src/cadrumo/adapters/persistence/storage/custody/tests/test_records.py:167-172` checks
only that `reason.value` occurs in the exception string. It would remain green if a
future diagnostic appended `candidate`, `scalar_count`, `utf8_byte_count`, or the
assessment representation, contradicting both the ADR and the execution record's
secret-free claim. Capture the exception, assert its exact finite diagnostic text (or
otherwise explicitly assert absence of a distinctive candidate and numeric facts) for
every refusal reason, and keep the expectation independent of the production formatter.
This is a MEDIUM regression-coverage defect, not a current secret leak. No HIGH or
CRITICAL finding blocks S06, and S06's recovery split may proceed, but S05 should not be
treated as review-clean until this secret-safety bite is added.

### s05-secret-free-error-bite-closure | low | Exact diagnostics and independent exclusions now guard every refusal

Commit `05f3070c85` closes `s05-secret-free-error-bite` after fresh semantic ADR and
code grounding, exact-symbol confirmation, and current-diff inspection. The amended
matrix at `src/cadrumo/adapters/persistence/storage/custody/tests/test_records.py:156-184`
uses distinctive candidates for all four canonical reasons, captures each custody
exception, and requires the exact finite `reason.value` diagnostic. It also independently
excludes the complete candidate, scalar and UTF-8 field names, complete assessment
representation, and both numeric measurements. Appending any of the previously untested
secret or measurement material now turns the test red.

The remediation changes only the owned custody record test and S05 execution evidence.
Ruff, formatting, and commit diff hygiene pass, and all 13 focused record tests pass.
The MEDIUM is closed. No unresolved HIGH, CRITICAL, or MEDIUM finding remains from the
S02-S05 reviews, and S06 may proceed.

### s06-worker-policy-independence-bite | medium | Policy-free recovery is not exercised across the parent-worker boundary

The mandatory S06 review grounded commits `021a90c1be` and `f8ca508b46` against
the accepted ADR, research, incident reference, live plan, current source, execution
record, commit history, and overlapping shared-worktree state. The current implementation
is functionally correct: `_recovery_secret_codec.py:9-22` is strict, exact UTF-8 with
typed malformed-transport errors and no normalization or password assessment;
`_kdf_supervision.py:303-380` preserves canonical password validation while lines
383-428 use the recovery codec; `_kdf_worker_supervision.py:99-147` emits distinct
password/recovery wrap and unwrap tokens; and `_kdf_worker.py:55-64` accepts only those
closed tokens before choosing the corresponding decoder at lines 116-140. Exact search
finds no recovery caller of the profile-password codec and no old generic material API,
alias, or shim. Existing real recovery tests preserve mnemonic, Argon2id, DEK, envelope,
artifact, and isolation behavior, and the complete serial default custody lane passes
217 tests with 10 expected marker deselections.

The new S06 bite does not prove the load-bearing separation through the supervised child.
`test_recovery_secret_roundtrip_is_byte_exact_and_not_password_shaped` at
`tests/test_recovery_secret_codec.py:14-20` sends empty, short, and over-256-scalar
secrets only through the direct codec. The negative-space scan at lines 37-46 reads
`_recovery.py`, `_recovery_artifact.py`, and `_recovery_secret_codec.py`, but omits the
two exact routing owners, `_kdf_supervision.py` and `_kdf_worker.py`. Existing real
worker-backed recovery tests use the current 24-word mnemonic, which already satisfies
profile-password policy. Consequently, a regression that sends a recovery operation
through `_encode_profile_password` or `_decode_profile_password` would keep both the
new tests and existing worker roundtrips green.

Add a real parent-to-worker recovery wrap and unwrap using a deliberately non-password-
shaped but valid recovery secret, such as `short`, and prove the exact DEK returns under
the unchanged KDF/AAD/sentinel contract. Pair it with a password operation using the same
secret that must refuse, so the test proves operation-token and decoder separation rather
than only cryptographic roundtrip. The same test should assert composed/decomposed byte
identity if practical. This is a MEDIUM regression-coverage defect, not a current
production-policy coupling.

### s06-format-evidence | medium | Three modified production modules fail the formatter gate

The S06 execution record says the custody surface remains lint-clean, and Ruff lint does
pass, but `ruff format --check` reports that
`src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py`,
`src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py`, and
`src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py` would be
reformatted. The diff shows the newly inserted regions carrying inconsistent line
endings/layout relative to their surrounding files. This is current production quality
debt and contradicts the Step evidence; run the repository formatter over exactly those
owned modules, verify no semantic diff, rerun Ruff and the focused/full serial custody
tests, and amend the execution evidence honestly.

No HIGH or CRITICAL defect was found. These two MEDIUM findings block review-clean S06
closure and therefore block dispatching S07 until remediated; the complete serial custody
result itself is green and does not reproduce the earlier xdist infrastructure failure.

#### S06 remediation resolution

Commit `672b342a17` closes both MEDIUM findings. A real parent-to-isolated-worker test now
wraps and unwraps the exact DEK with the non-password-shaped `short` recovery candidate,
distinctive recovery AAD, and the persisted sentinel proof. The paired password operation
uses the same candidate and must refuse with canonical `too_few_scalars`. The negative-space
bite reads both routing owners and requires the recovery decoder in both worker branches,
so redirecting recovery through either profile-password codec turns the suite red.

The formatter was applied only to the owned production modules and tests. Ruff check and
format-check are clean; the focused worker/codec lane passes 28 tests, and the complete
serial default custody lane passes 218 tests with 10 expected marker deselections. Both
MEDIUM findings are closed, with no remaining HIGH or CRITICAL S06 defect.

#### S06 independent remediation verification

Current-HEAD re-review independently confirms that commits `672b342a17` and
`2b78e05375` close `s06-worker-policy-independence-bite` and
`s06-format-evidence`. Semantic code and governing-ADR discovery was repeated before
exact search of the two routing owners. The regression at
`src/cadrumo/adapters/persistence/storage/custody/tests/test_kdf_supervision.py:409-441`
uses the deliberately password-invalid recovery candidate `short` across the real
parent-to-supervised-worker recovery wrap and unwrap operations, verifies the exact DEK
after sentinel proof, and then requires the paired canonical password wrapper to refuse
the identical candidate with `too_few_scalars`. This test therefore fails if either
recovery operation is redirected through profile-password assessment.

The static bite at
`src/cadrumo/adapters/persistence/storage/custody/tests/test_recovery_secret_codec.py:37-50`
now covers the recovery portion of `_kdf_supervision.py` and all of `_kdf_worker.py`; it
excludes profile-password assessment and codecs from the supervisor recovery routes and
requires both worker recovery branches to select `decode_recovery_secret`. Exact search
also confirms the obsolete generic wrap and unlock names remain absent except for their
negative assertions. Commit diff checks are clean. Ruff check passes and Ruff
format-check reports all six reviewed modules/tests already formatted. The focused
serial worker/codec lane independently passes 28 tests, and the complete serial default
custody lane independently passes 218 tests with the same 10 expected marker
deselections in 85.23 seconds. Those results agree with the amended S06 execution
record rather than relying on its assertion.

Both S06 MEDIUM findings are closed. No unresolved HIGH, CRITICAL, or MEDIUM finding
remains from this review chain, and W01.P03.S07 may proceed.

### s07-refusal-context-mutability | medium | The frozen refusal exposes a mutable context

The mandatory S07 review grounded the application implementation in commits
`cee3240301`, `8b01182fb9`, and `f0fcbb9681` against the accepted ADR, research,
incident reference, live plan, current source, execution record, history, and shared
worktree state. The production ordering is correct today: registration assesses at
`src/cadrumo/application/user_profile/_registration.py:191-200` before identity
generation, random key material, custody creation, session construction, or lifecycle
publication; rotation assesses at
`src/cadrumo/application/user_profile/_passphrase_rotation.py:125-135` before root
resolution, transaction locking, committed-material loading, unwrap, re-heading, or
publication. Exact search finds no stale minimum-only application policy, compatibility
alias, or parallel validator. The real integration tests cover all four reasons, both
surrogate-range endpoints, 14/15/256/257 scalars, the 1,024/1,025-byte boundary and
precedence, and exact composed/decomposed usability. Whole-root byte snapshots prove
that refused registration and rotation leave every extant capsule, inventory, session,
record, recovery, and envelope path unchanged. Successful rotation coverage retains the
DEK epoch, recovery door, generation, record history, and new-password session behavior.

However, `ProspectiveProfilePasswordRefusal` is only shallowly frozen. Its declaration
at `src/cadrumo/application/user_profile/_prospective_password.py:32-39` stores
`context` as a mutable `dict`; callers can add, remove, or replace presentation facts
despite `frozen=True`, and both application errors retain that same object. This violates
the Step's immutable stable-context contract and lets a downstream surface accidentally
turn a reviewed secret-free payload into an expanded or inconsistent one. Store a truly
immutable mapping (constructed from a fresh private mapping) and add a test that mutation
is refused. Pin the exact translation key and exact finite context keys/values for each
reason, rather than the current prefix assertion and the tautological comparison between
an error and its own payload. This is a current contract defect, not evidence of a
present secret leak.

### s07-preflight-order-bite | medium | Storage snapshots do not prove the claimed preflight boundary

The refusal matrices at
`src/cadrumo/application/user_profile/tests/test_registration.py:184-211` and
`src/cadrumo/application/user_profile/tests/test_passphrase_rotation.py:226-261` prove
typed outcomes and durable no-mutation. They do not prove the stronger ordering claimed
by the ADR and execution record. Registration could generate an identity and key
material or enter custody before returning the same application refusal; rotation could
resolve the root, acquire and release the transaction lock, load the envelope, or unwrap
the current password before assessing the replacement. Those regressions can leave the
whole-root snapshot byte-identical, so every current test would remain green.

Add collaborator-boundary bites that make `new_profile_id`, randomness, and custody
material creation fail if reached during invalid registration, and make root resolution,
lock acquisition, material loading, and unwrap fail if reached during invalid rotation.
Keep the existing whole-storage snapshots because they prove the separate durable-state
guarantee. The implementation is correctly ordered now; this is a regression-coverage
and evidence-completeness defect.

### s07-format-evidence | medium | Four S07-owned files fail the formatter gate

Ruff lint passes, and the correctly selected serial integration lane independently
passes all 35 registration and rotation tests in 44.31 seconds. But `ruff format
--check` reports that `src/cadrumo/application/user_profile/__init__.py`,
`_passphrase_rotation.py`, `_prospective_password.py`, and `_registration.py` would be
reformatted. The mixed-commit diff introduced inconsistent line endings in the S07
regions and also leaves a formatter-owned layout change in the new message mapping.
This contradicts the execution record's focused Ruff evidence. Format exactly the S07
owned files, verify the diff is non-semantic, rerun Ruff and the 35-test integration
lane, and amend the execution evidence.

No HIGH or CRITICAL finding was found. These three MEDIUM findings block review-clean
S07 closure and therefore block S08 until remediated and independently rechecked.

#### S07 remediation closure

Current-HEAD re-review of commit `8b50c24566`, after repeated semantic code and
governing-ADR discovery plus exact-symbol confirmation, closes all three S07 MEDIUM
findings. `ProspectiveProfilePasswordRefusal` at
`src/cadrumo/application/user_profile/_prospective_password.py:32-56` now stores only
frozen typed scalar fields and derives a fresh `MappingProxyType` context from them.
There is no mutable context retained inside the result; attempted writes through the
read surface raise `TypeError` and cannot alter the underlying refusal. The application
errors continue to make their own plain-dictionary copy through the established
`CadrumoError` convention.

Both refusal matrices now pin the exact finite translation key and the exact safe
context keys and values for every canonical reason, including the absence of a byte
measurement for surrogate refusal. They independently exclude the submitted candidate
from the typed payload. Registration's fail-if-called bite at
`src/cadrumo/application/user_profile/tests/test_registration.py:254-268` guards profile
identity generation, every randomness call, and custody material/KDF entry. Rotation's
bite at `src/cadrumo/application/user_profile/tests/test_passphrase_rotation.py:293-315`
guards root resolution, transaction locking, material loading, unwrap, record re-heading,
and envelope publication. The existing whole-root byte snapshots remain separate proof
that capsule, inventory, session, record, recovery, and envelope state is unchanged.

Commit diff hygiene passes. Independent Ruff lint and format checks pass over all six
owned files, reporting them already formatted. The correctly selected serial integration
lane passes all 37 registration and rotation tests in 48.19 seconds, consistent with the
execution record's 37-test result. `s07-refusal-context-mutability`,
`s07-preflight-order-bite`, and `s07-format-evidence` are closed. No unresolved HIGH,
CRITICAL, or MEDIUM finding remains, and W02.P05.S08 may proceed.

### s08-cli-absent-channel-laundering | high | The CLI relabels every storage fault as a missing password channel

The mandatory S08 review grounded commit `94abc99a67` against the accepted ADR,
research, incident reference, live plan, current source, commit history, diff, and
execution evidence. The central application contract is narrow and secret-free:
`ProfileAuthenticationRefusedError` has one stable translation key and no context;
the closed `ProfilePasswordProofOperation` enum makes every mapping call explicit; and
`map_profile_password_proof_failure` at
`src/cadrumo/application/user_profile/_custody_ports.py:1014-1023` collapses exactly
`ProfileCustodyPasswordError`, allowing record, integrity, archive, supervision,
transaction, resource, keyring, and storage faults to propagate. Login preserves the
throttle write before raising the common refusal. Real malformed and wrong passwords
are indistinguishable at login, password restore, and recovery export, with no candidate,
measurement, or prospective-policy guidance and no publication. Rotation retains its
operation-specific outer error while using the same narrow internal classification.
Exact search confirms the obsolete broad password predicate and all consumers are gone,
no recovery-removal capability exists, and this commit makes no locale changes.

The required minimal CLI adjustment is not narrow. In
`src/cadrumo/entrypoints/cli/_config/_custody.py:253-275`, the handler catches both the
new authentication refusal and every `SecretStoreError`; when no callback or configured
passphrase exists, its condition tests only `isinstance(exc, SecretStoreError)`. Thus a
`KeyringUnavailableError`, unavailable storage, corruption, supervision failure, or
other operational storage fault occurring during callback-free login is replaced by
`CliRefusedBoundaryError(application.user_profile.errors.passphrase_channel_absent)`.
That tells the operator to supply a password channel when the real fault is operational,
violates the ADR's explicit non-laundering boundary, and can suppress the correct
retryability/remediation classification. The adjacent comment still claims that only
the absent-channel custody refusal is selected, but the old predicate that made that
true was deleted.

Represent absence of an explicit password channel with its own typed application outcome
before this boundary, or otherwise match only that exact condition without resurrecting
the broad password predicate. Add a CLI regression injecting `KeyringUnavailableError`
and at least one corruption/supervision storage error with no callback/configured secret
and require the original typed fault to escape unchanged; separately prove the genuine
absent-channel case retains its CLI guidance. This HIGH finding blocks S09.

### s08-operational-distinction-bite | medium | The focused tests do not exercise the closed mapper's negative space

The new real tests cover malformed and wrong credentials for three public doors and
prove login throttling and mutation safety, but no focused test supplies non-password
custody failures to `map_profile_password_proof_failure` or through the restore, export,
rotation, and login catch boundaries. Rotation also lacks the paired malformed-current
password case that would prove parity with its existing wrong-current-password test.
The exact `isinstance(ProfileCustodyPasswordError)` implementation is correct today,
but a future widening to `SecretStoreError` or `CadrumoError` would launder operational
faults while the new focused tests remained green.

Add a finite negative-space matrix covering representative record/integrity,
archive/transaction, supervision/resource, and unavailable-storage errors and require
identity-preserving propagation from the relevant public doors. Pair malformed and
wrong current-password rotation attempts and assert identical safe outer error facts and
unchanged whole storage. This is a MEDIUM regression-coverage defect.

Ruff lint and format checks independently pass over all 12 changed source/test files.
The recovery and rotation integration lane passes all 39 cases. The full login-handover
lane reproduces the recorded 22 passed and seven failures. All seven failures are
successful session-resume or crash-recovery assertions with captured
`KeyringUnavailableError`; none executes the changed password-refusal exception branch,
and the commit touches only that branch plus the separate wrong/malformed refusal test.
They are therefore a Windows keyring baseline/environment limitation, not an in-scope
red, but they also demonstrate why the HIGH CLI laundering path must not ship.

No CRITICAL finding was found. The HIGH and MEDIUM findings block review-clean S08 and
W03.P06.S09 dispatch until remediated and independently verified.

#### S08 remediation closure

Current-HEAD re-review of the S08 paths in mixed-provenance commits `b64e27f26c`,
`1da3ae3f89`, and `f9a4062945`, after repeated semantic code and governing-ADR
discovery plus exact-symbol confirmation, closes both findings. The CLI boundary at
`src/cadrumo/entrypoints/cli/_config/_custody.py:253-280` no longer imports or catches
the broad `SecretStoreError` family. It catches only the application authentication
refusal and the exact custody password error that escapes before authentication when
there is no callback or configured password. Only the latter, combined with both
channel-absence facts, becomes `passphrase_channel_absent`; an offered malformed or
wrong password remains the common application refusal.

The new CLI classification tests inject `KeyringUnavailableError`, custody record
integrity failure, and KDF supervision refusal into callback-free login and require the
same exception object and concrete type to propagate. The genuine raw custody password
absence signal independently retains the specific CLI guidance. Exact source inspection
shows transaction, resource, archive, generic unavailable-storage, and other operational
errors are outside the catch tuple entirely, so their type, category, retryability, and
context cannot be rewritten there. No broad password predicate or `SecretStoreError`
catch has been reintroduced.

The mapper negative-space matrix at
`src/cadrumo/application/user_profile/tests/test_authentication_failure_mapping.py:18-35`
covers record/integrity, transaction, KDF resource, KDF supervision, and keyring
unavailability for every closed `ProfilePasswordProofOperation`; all return `None`.
Each public application door handles that result with a bare re-raise, preserving the
original exception object, while only `ProfileCustodyPasswordError` becomes
`ProfileAuthenticationRefusedError`. Rotation now pairs a malformed `short` current
password with a cryptographically incorrect well-shaped password and proves identical
outer translation key, `context is None`, candidate absence, whole-storage byte identity,
and continued unlock by the current credential. The existing prospective replacement
matrix remains separate and retains its detailed reason-bearing contract. No new error
or compatibility type was introduced.

Diff hygiene passes for the isolated S08 paths. Independent Ruff lint and format checks
pass over all four remediation files. The serial CLI/mapper lane passes all 24 cases in
2.27 seconds, and the complete serial rotation lane passes all 19 cases in 35.57 seconds,
matching the execution record. `s08-cli-absent-channel-laundering` and
`s08-operational-distinction-bite` are closed. No unresolved HIGH, CRITICAL, or MEDIUM
finding remains, and W03.P06.S09 may proceed.

### s09-duplicate-prospective-mapping | medium | The TUI reimplements the application refusal contract

The mandatory S09 review grounded commits `12f30636fc` and `90c05dad3a` against the
accepted ADR, research, incident reference, live plan, current source, history, diffs,
and execution evidence. The screen now consumes the canonical core assessment for live
acceptance, retains refusal keys and primitive safe facts in a frozen/slotted
`RegistrationRefusal`, and resolves them only at the active-language presentation
boundary. The manager frontend preserves keyed `ProfileRegistrationError` facts and
rethrows unkeyed registration failures into the genuine unexpected-worker path. Refused
submission tests cover all four reasons, 14 and 257 scalars, 1,025 bytes, and both
surrogate halves without persistence, candidate representation, raw custody prose, or
traceback material. The password stays only in the masked correction fields and the
necessary submission span; the temporary mutable byte buffer is wiped on every worker
exit, and neither attempt nor refusal envelope retains it. Locale files are untouched as
assigned to S10. Accepted live 15/256/1,024 and composed/decomposed end-to-end coverage
is properly scheduled for S11 rather than duplicated in this mapping Step.

However, `assessment_refusal` at
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:142-164` independently rebuilds
the complete reason-to-message map, safe-context shape, and reason-specific limit facts
already owned by application
`src/cadrumo/application/user_profile/_prospective_password.py:32-72`. It imports all
three profile-password limits and branches over every refusal reason a second time. A
future application key or context change can therefore make live TUI feedback disagree
with submission, and a new reason requires synchronized edits in two layers. This is the
parallel policy/presentation path the ADR and the campaign's no-bloat requirement forbid,
even though its current values agree.

Expose the already canonical prospective refusal projection through the application
facade (or a dependency-safe equivalent application presenter) and have both live TUI
feedback and registration submission adapt that one immutable result into
`RegistrationRefusal`. Delete the TUI reason branches, limit imports, and duplicated
keys without aliases or shims. Add an equality bite proving live feedback and application
submission carry the same key and exact safe context for every reason. This is an
architectural consistency and bloat defect, not a current secret leak.

### s09-original-crash-bite | medium | The live screen test stays green on the original worker-error regression

`test_short_password_refuses_and_creates_nothing` at
`src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py:162-175` drives the
real Textual screen but asserts only `outcome is None` and no manifest. In the original
bug, 8-14-scalar input reached the worker, raised custody English, rendered mixed-language
INTERNAL guidance, created no profile, and also left `outcome` as `None`; this test would
therefore remain green. The new parameterized test at lines 45-76 asserts the direct
manager attempt envelope, not the live worker settlement or pinned status message, and
its `"INTERNAL" not in repr(attempt)` assertion cannot detect what the screen renders.

Strengthen the live 14-scalar regression to require `app.error is None`, an error-toned
nonempty pinned refusal, the expected typed key/context path, and absence of INTERNAL
guidance, raw custody English, traceback text, and the submitted candidate from both the
status and retained attempt/error state. Add a deliberately unkeyed registration failure
test proving the opposite branch still sets `app.error` and renders genuine INTERNAL
guidance. S11 may own the broader all-language and accepted-boundary matrix, but S09 must
bite the exact crash shape it claims to remove.

Commit diff hygiene, Ruff lint, and Ruff format checks pass over the four changed Python
files. The registration-screen module passes 11 cases; the registration plus full
language-switch lane passes 15, although it emits a pre-existing cross-context cleanup
warning from `override_settings`; and the existing manager refusal-rendering lane passes
three cases. No HIGH or CRITICAL finding was found. These two MEDIUM findings block
review-clean S09 and S10 until remediated and independently verified.

#### S09 remediation closure

Current-HEAD re-review of commit `fbfaa7cb84`, after repeated semantic code and
governing-ADR discovery plus exact-symbol confirmation, closes both S09 findings. The
application facade now exports `prospective_profile_password_refusal`, whose immutable
result remains the sole production owner of refusal-reason message keys, exact safe
context, and reason-specific limits. TUI `assessment_refusal` at
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:140-151` only adapts that
application result into the immutable screen envelope. Exact search finds no TUI copy of
the four keys, maximum-scalar or byte limits, or reason-to-context branches; the retained
minimum import serves only the independent password-hint copy. The five refused
candidate cases prove exact equality between live projection and the real submission
attempt envelope, including both surrogate endpoints.

The headless 14-scalar regression at
`src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py:165-198` drives the
real password widget and create action. It proves nonempty live and submitted refusal
copy, error tone, `app.error is None`, no manifest, and absence of the candidate,
`INTERNAL`, the original raw custody English, and traceback text. Its assertions would
turn red on the original escaped-worker failure. The paired unkeyed `RuntimeError` test
at lines 201-220 proves the genuine unexpected path retains the exact exception in
`app.error` and renders exactly the active-language INTERNAL boundary guidance. Expected
keyed errors therefore remain typed and localized without swallowing programming faults.

Diff hygiene passes. Independent Ruff lint and format checks pass on all three
remediation source/test files. The authoritative registration, language-switch, and
manager-refusal integration lane passes all 19 cases in 19.11 seconds with the one
already documented Textual context-teardown warning. `s09-duplicate-prospective-mapping`
and `s09-original-crash-bite` are closed. No unresolved HIGH, CRITICAL, or MEDIUM
finding remains, and W03.P07.S10 may proceed.
