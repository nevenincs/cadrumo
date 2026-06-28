---
tags:
  - "#audit"
  - "#secure-persistence-foundation"
date: 2026-04-29
modified: '2026-04-29'
related:
  - "[[2026-04-29-secure-persistence-foundation-wave18-research]]"
  - "[[2026-04-29-secure-persistence-foundation-wave18-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave15-16-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave17-audit]]"
---

# `secure-persistence-foundation` audit: wave-18 rotation-correctness gate

## Scope

Audit gate for **wave-18**: closing two pre-existing P1 findings on
the rotation substrate that the wave-17 review pass surfaced and
the wave-17 absorption commit explicitly deferred. Each finding is
objectively verifiable against current code (not a stylistic
preference); each fix is scoped, surgical, and has zero operator-
facing surface.

Wave-18 in scope:

- Research artefact + ADR formalising D1 (blob-store rotation
  roots) and D2 (rotation lock-target alignment with the writer
  convention).
- ``default_blob_store_roots`` correction in
  ``src/aeat/adapters/persistence/storage/_rotation.py``.
- ``RotationPlanEntry.lock_path_for`` method + ``rotate_master_key``
  call-site update.
- 8 new regression tests in
  ``src/aeat/adapters/persistence/storage/_test_rotation.py`` (3 covering the blob-store
  helper, 5 covering the lock-target alignment).
- Operator runbook note in ``docs/security-runbook.md`` for
  installations that ran rotation before the fix.

## Findings

### Strengths

**Both confirmed-real P1 findings are now closed.**

- **D1 — blob-store rotation roots**: `default_blob_store_roots`
  visits `aeat_blob_store_dir` (where ``get_secret_store`` actually
  wires the blob store) and `aeat_attachments_dir` (the attachments
  blob store). The helper deduplicates overlap and skips missing
  directories. Three regression tests prove the new behaviour.
- **D2 — rotation lock-target alignment**: ``RotationPlanEntry``
  exposes ``lock_path_for(envelope_path)`` that returns the writer-
  canonical sidecar path. ``rotate_master_key`` calls the method
  instead of computing the lock target inline. Five regression
  tests prove the alignment, including a contention test that
  holds the writer's lock with `timeout=0` and asserts the rotation
  sees `LockAcquisitionError`.

**Adjacent codex / gemini findings reviewed and confirmed-already-
addressed.** The research artefact catalogues each one against the
current source line and shows the fix is in place:

- envelope_suffix coverage of single-file envelopes (`target_filename`
  override at lines 320 + 384 of `default_rotation_plan`).
- ``migrate_master_key_kdf`` write order (lines 1069-1080: master.key
  first, master.kdf last; partial-migration recovery at 1041-1054).
- master-key first-time mint race (`exclusive_file_lock` at
  `_master_key.py:471-478`).
- `_try_decrypt_bytes` malformed-AAD safe path (lines 142-147).
- corpus-manifest symlink rejection (lines 179-180: `is_symlink` BEFORE
  `is_file`).
- corpus-manifest backslash separator rejection (lines 77-80).
- master.kdf non-object preview (`isinstance(preview, dict)` at
  lines 992-995).

**Test surface materially expanded.**

- 23 rotation tests total (15 pre-existing + 8 wave-18).
- All 382 storage + wave-17 CLI + integration tests pass.
- Lint + format + type-check clean on every touched file.

**No regressions in the wave-17 surface.**

- `aeat security provision` / `recover` / `key-export` smoke tests
  pass unchanged.
- `aeat doctor` security rows render unchanged.
- The first-run integration test (8 scenarios, brand-new-user flow
  under the file-fallback backend) passes unchanged.

### Residual risks

**R1 — Existing installations may need a re-rotation.** Anyone who
ran `aeat security rotate-master-key` against the substrate prior
to this commit may have left their secret-store DEKs under the old
master key (because rotation walked `var/secrets` instead of
`var/blobs`). The runbook now calls this out explicitly and
documents the resume-idempotent re-run path. The substrate cannot
detect or self-correct this from the operator side; the fix is to
re-rotate under the corrected helper before decommissioning the old
key the second time. Acceptable because (a) the substrate is still
pre-1.0 and rotation has not been run in production according to
project context, and (b) the runbook + commit message + audit
report make the operator action explicit.

**R2 — Lost-update tests under live concurrent writers are
deferred.** Wave-18 closes the lock-target alignment so the OS-level
serialisation now actually engages, but the integration test only
proves contention on the same sidecar — not that concurrent
write-during-rotation traffic produces no lost updates. Acceptable
because (a) the runbook's quiesce-then-act expectation makes this
an operator-discipline concern, and (b) the lock-target alignment is
the necessary precondition for any future lost-update test to mean
anything.

**R3 — `lock_path_for` does not validate that the consumer's
writer actually uses the convention the entry assumes.** A future
consumer that ships its own custom lock convention would need a
plan entry that matches; the substrate has no way to enforce this
beyond inspection. Acceptable because every wave-7 governance
repository, every wave-4 envelope writer, and every wave-7 single-
file writer in the substrate today uses one of the two conventions
the helper covers. New consumers will follow the established
patterns or the documentation; the contract is published and
testable.

### Findings against earlier wave audits

- The wave-15+16 audit's R1 (operator-quiesce-rotate) is **closed**
  by the wave-18 lock-target alignment. The OS-level lock now
  actually engages between rotation and writer.
- The wave-17 audit gate remains PASS. Wave-18 does not touch any
  wave-17 surface.
- All other wave-1..17 audit gates remain PASS.

## Recommendations

**Pass the gate.** Both confirmed-real P1 findings are closed; the
test surface is regression-free across 8 new scoped tests; the
runbook documents the operator action for pre-fix installations.

**Track R1 (existing-installations re-rotation) in the runbook
and the release notes.** When the project tags a release that
includes this fix, the release notes should call out the
re-rotation pointer so any operator who rotated under an earlier
build can re-run under the corrected helper.

**Track R2 (lost-update integration tests) for a future hardening
pass.** Acceptable as a wave-19 follow-up if the operator
experience surfaces a need; not blocking.

**Pursue fresh review feedback.** The wave-18 commits will land at
the existing PR (#441) where `@gemini-code-assist` and
`@chatgpt-codex-connector` already actively review. Findings, when
they arrive, are absorbed by amending the residual-risks section.

## Verdict

**Wave-18 audit gate: PASS.** The rotation substrate now visits the
right blob-store and contends on the writer-canonical sidecar;
both pre-existing P1 findings are closed; the wave-15+16 lock-
acquisition that was meant to provide OS-level serialisation now
actually does so.

The post-wave-18 secure-persistence-foundation epic is **substrate-
feature-complete + operator-UX-feature-complete + rotation-
correctness-hardened**. The remaining work is operator-feedback-
driven polish (wave-17 R2, wave-17 R3, wave-18 R1, wave-18 R2) and
the merge-readiness verification.
