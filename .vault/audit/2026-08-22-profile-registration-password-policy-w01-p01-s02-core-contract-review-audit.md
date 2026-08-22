---
tags:
  - '#audit'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:1e932d0f64bbaab1b49ad63e5432217f33bd7d8a0cedf25b57fb36f3240a678c'
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
