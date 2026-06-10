---
step_id: S08
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S08: QHC-003 cognitive hotspot — `_resume_from_storage_state_locked`

## Outcome

`AeatAuthenticator._resume_from_storage_state_locked` reduced from cognitive
**25 → 11** by extracting two behaviour-preserving helpers. This function was
skipped in two prior QHC-003 slices for security caution (it is the AEAT
session-resume seam); it was handled here under the harness-first protocol
(behaviour-capture harness committed and proven before the function was
touched). Cognitive over-threshold count for the campaign dropped **8 → 7**.

## Harness-first protocol (commit `4cd10ca73`)

Built a behaviour-capture harness
(`tests/test_resume_behaviour_capture.py`, 11 tests) that pins the full
observable contract BEFORE any refactor, committed separately and proven green
against the unmodified function. Every seam is a real in-process implementation
of the `BrowserSessionLike` / `BrowserContextLike` Protocols (the hexagonal
boundary) — no mocks, stubs, or monkeypatches, and no live AEAT access. Failures
are injected by feeding the real control flow deterministic inputs.

Paths covered, and how each failure is driven through the real seam:

- **Four ordered validation gates** (storage_state hash, idle deadline,
  certificate thumbprint, certificate subject). Each test seeds a valid
  persisted pair via `_seed_persisted_session`, then mutates exactly one
  metadata field so the corresponding gate trips. The refusal is asserted by
  its stable redacted `reason` code on the raised `_PersistedSessionInvalidError`
  (`storage_hash_mismatch`, `idle_deadline_expired`,
  `certificate_thumbprint_mismatch`, `certificate_subject_mismatch`). No browser
  context is ever built for a metadata-gate refusal.
- **Gate ORDER** — two explicit order proofs: trip all four gates at once and
  assert the hash gate (first) wins; satisfy the hash gate and trip the rest,
  assert the idle gate (second) wins.
- **Successful resume** — asserts the rebuilt `AeatSession` fields
  (`provider_kind`, thumbprint, subject, `storage_state_path`), the
  `model_copy`-advanced `authenticated_at` (> seeded) and
  `idle_deadline == authenticated_at + AEAT_SESSION_IDLE_TTL`, plus
  `_active_session`/`_context`/`_browser_session` assignment and storage capture.
- **`_PersistedSessionInvalidError` (failed live probe)** — injected by
  `_RecordingBrowserSession(cert_ok=False)` so the page returns 401 and the probe
  is `is_valid=False`. Asserts the directly-raised error's message +
  `persisted_session_verification_failed` translated_message (this path does NOT
  carry a redacted reason code — it re-raises the original instance), context
  closed, and persisted state invalidated. Two owns_session variants: owned
  (session resolved via injected `browser_session_factory`) closes the session;
  caller-injected (`browser_session=` argument) does NOT close it.
- **General-exception path** — injected by `_MarkerMismatchBrowserSession` whose
  context omits the certificate marker, so `_assert_context_marker` raises a plain
  `AeatLoginAssertionError` caught by the general `except`. Asserts the
  `resume_failed` flag drives `_raise_invalid_persisted_state` with the
  `resume_failed` reason code, context closed, owned session closed.
- **`_capture_storage_state_locked` failure cleanup** — injected by a context
  whose `storage_state()` raises after a successful probe. Asserts `_drop_context`
  ran (`_context is None`), `_browser_session`/`_active_session` nulled, owned
  session closed, and the original `RuntimeError` re-raised.

## Refactor (commit `927bd21a8`)

Extracted two helpers at the natural seams:

- `_validate_persisted_session_metadata(metadata, *, cert, storage_state_sha256,
  storage_state_path)` — the four ordered gate checks, verbatim messages and
  verbatim `_raise_invalid_persisted_state` calls, same order. Cognitive 4.
- `_teardown_resume_attempt(context, session_like, *, owns_session,
  context_close_log)` — the repeated `context.close()` suppress-and-log plus the
  `owns_session`-gated `_close_browser_session`. The two callers' distinct DEBUG
  log strings are preserved by passing them as `context_close_log`. Cognitive 3.

The method's control flow is otherwise untouched: the early gate raises (now one
call), the `resume_failed` flag, the `context is None or session is None` tail,
the success assignment, and the capture-failure cleanup are byte-for-byte
equivalent. The `AeatSession` construction and `model_copy` update are unchanged.

## Anti-tautology proof

The harness was proven non-tautological by two deliberate working-tree mutations
(applied then fully restored, no commit affected):

- Swapped the hash and idle gates in `_validate_persisted_session_metadata` →
  `test_validation_gate_order_earliest_wins` went RED (observed
  `idle_deadline_expired`, expected `storage_hash_mismatch`).
- Changed the teardown gate to `if owns_session or True` →
  `test_failed_live_probe_with_injected_session_does_not_close_session` went RED
  (the externally-owned session was wrongly closed).

Both restored; `git diff` of the source against HEAD is empty.

## Verification gate

- Harness against unmodified function: **11 passed** (commit `4cd10ca73`).
- Harness after each extraction: **11 passed**.
- Full auth suite (`uv run --no-sync pytest src/aeat/adapters/outbound/aeat/auth -q`):
  **139 passed, 6 deselected** (128 baseline + 11 new), log at
  `.vault-scratch/qhc003-auth-suite-postrefactor.log`.
- `uv run --no-sync ruff check` clean on both files.
- `uv run --no-sync pyright` on both files: **0 errors**.
- Scoped complexity (`python -m dev.audit.complexity`):
  `_resume_from_storage_state_locked` cognitive **25 → 11**; helpers at **4** and
  **3** (both under the ~12 guidance). Cognitive over-threshold count **8 → 7**.
- `python -m dev.docs.apidocs scaffold --check`: no drift.
- Core-struct docstring links: the auth module is NOT in the gate's violation
  list (the helper docstrings cross-reference `AeatSession` /
  `PersistedSessionMetadata` truthfully). The gate's two failures are in unrelated
  peer modules (`application.modelo._iva_wallet_seed`, `application.registry`) and
  are out of this Step's scope.
- Review: fresh-context honesty self-review performed (no
  agent-dispatch tool available this session); verdict PASS — behaviour-preserving,
  proven by the two mutation red-runs above.

## Commits

- `4cd10ca73` test(qhc-003): behaviour-capture harness for `_resume_from_storage_state_locked`
- `927bd21a8` refactor(qhc-003): extract validation + cleanup helpers from `_resume_from_storage_state_locked` (cognitive 25->11)
