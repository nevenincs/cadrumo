---
tags:
  - '#plan'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-09'
body_hash: 'sha256:fff85b0857b5d45afae4fe3552e862562dcffaae7bc9461ba41424945f1fccb1'
tier: L1
related:
  - '[[2026-08-07-declarations-register-pagination-adr]]'
  - '[[2026-08-07-declarations-register-pagination-reference]]'
---
# `declarations-register-pagination` plan

## Description

Executes `2026-08-07-declarations-register-pagination-adr`: the declarations
register walker parses one DOM snapshot per `(modelo, ejercicio)` query and
returns it as complete with no signal when AEAT's own pager label declares
more rows than were rendered. Implementation is authorised; every Step below
is an executable code change with a named verification gate, not a deferred
"investigate" row. This plan implements detection-and-refusal (the ADR's
chosen option B) only; full page traversal is explicitly out of scope per
the ADR's Constraints and Considered options and, per operator directive, no
Step in this plan performs or requires any live authenticated AEAT probe.
Whether AEAT's real grid paginates this form stays unverified; a future
attempt to build traversal or to verify pagination against a live account
needs separate operator sign-off and is not authorised by this plan. S01
adds the typed page result and pager-total parsing at the parse boundary.
S02 wires the truncation refusal into both register-walk entry points. S03
confirms the refusal reuses the existing per-pair bulk-capture failure
taxonomy rather than a new abort mechanism. S04 updates the pinning test
(`test_declarations_pagination_blindness.py`, commit `82df6ed81d`) to assert
the new refusal in the same change that implements it, per its own
docstring's stated reversal condition, and adds a companion non-regression
test for the untruncated, no-pager-label case. S05 proves the S04 gate
actually bites: break the detector via an outside-the-repo runtime
monkeypatch, confirm the test reds, restore, confirm green. A gate is
unproven until it has failed on demand.

## Steps

- [x] `S01` - Add a typed DeclaracionesRegisterPage carrying rendered rows, a parsed declared_total (int or None, None only when no pager label is present) and a derived truncated property to _parse_listbox, reusing a pager-label regex analogous to the pinning test's fixture-independent extraction. Gate: a new unit test asserts declared_total is parsed correctly off the existing synthetic paginated fixture and is None off the real single-row fixture; `src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py`.
- [x] `S02` - Consume the typed page in DeclaracionesRegisterSession.walk and walk_declarations_register, raising SedeParseError naming modelo, ejercicio, rendered count and declared_total when truncated is true, instead of returning a bare tuple. Gate: a unit test parses the synthetic paginated fixture through _register_rows_from_snapshot, the shared helper both entry points call and the whole of their non-browser behaviour, and asserts SedeParseError is raised, and a second test asserts the real single-row no-pager fixture still returns its rows unchanged. Not exercised here and excluded deliberately: the browser shell around that helper, meaning the navigation, the combobox drive, the Buscar click and the post-Buscar landing assertion. All of it precedes the refusal and is unchanged by it, so the residual risk is that walk stops reaching the helper at all rather than that the refusal misfires. Closing that exclusion is its own row rather than a silent gap; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `S03` - Confirm the truncation SedeParseError is absorbed by the existing per-pair FiledDataCaptureFailureRow assembly with no new bulk control-flow branch. Bulk-path walk failures are unconditionally best-effort by design, so no FAIL_FAST branch exists for a walk failure to exercise and none must be added to satisfy a gate. The FAIL_FAST axis in this file governs finalize_filed_capture's calculation-observation stage, a different function and a different failure class that this plan does not touch. Gate: an application-level test asserts the refusal is catchable by the sweep's walk arm and that the resulting failure row preserves its error type, both counts and its reason intact within the row's bounded message; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `S04` - Rewrite test_declarations_pagination_blindness.py (commit 82df6ed81d) so its assertions flip from pinning the silent gap to asserting the new refusal fires on the paginated synthetic fixture, and add a companion test proving the real no-pager-label fixture is never classified as truncated. Do not delete, skip, xfail, or loosen this test to make an unrelated fix pass. Its docstring's own stated reversal condition is authorisation to REPLACE its assertions with the refusal assertion, not to remove coverage of the gap. Gate: pytest on this file is green with the new assertions and reds if truncated defaulted to False unconditionally; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_pagination_blindness.py`.
- [x] `S05` - Prove the S04 refusal test actually detects a broken detector. From a scratch script outside this repository, never a tracked-file edit so a peer sweep cannot commit the mutation, monkeypatch the declared_total parsing or the truncated property to always report untruncated, rerun the S04 refusal test and confirm it reds naming the expected rendered-versus-declared mismatch, then remove the monkeypatch and confirm the same test is green again. Gate on the property that a rendered-versus-declared mismatch is refused, never on an exact expected row count, since a hardcoded count encodes one fixture snapshot and stops detecting anything once the fixture changes; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_pagination_blindness.py (proof only, no tracked file is edited to perform it)`.
- [x] `S06` - Add a minimal purely-additive optional register-injection seam to list_filed_data_bulk and capture_filed_data_bulk, defaulting to today's behaviour so every existing caller and signature is unchanged. Its purpose is SESSION-RESOLUTION bypass, not browser avoidance. Route interception makes the browser reachable with no production change at all, but both bulk paths first call active_verified_session, which runs AeatAccessGate.require_live_read. Under pytest that refuses unless CADRUMO_LIVE_TESTS_ENABLED is the literal 1, and it then drives ensure_authenticated_aeat_session, the central live-session writer needing an active bucket and real credentials. Satisfying that gate rather than bypassing it would ARM real AEAT access, so the seam is what lets the test never request live access in the first place. This is also why the existing navigation-timeout test needs no seam: it drives _drive_search with its own page and never resolves a session. Gate: a test passes a REAL DeclaracionesRegisterSession, never a stub or a patched production path, over route-intercepted synthetic fixtures with no AEAT contact, arranges one query pair truncated and another complete, and asserts the truncated pair becomes a FiledDataCaptureFailureRow while the complete pair still yields rows. Gate on the property, never on a pair count. This closes a gap wider than truncation, since no failure kind currently has coverage of the sweep continuing past a failed pair; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `S07` - Cover the register walk end to end offline, closing the browser-shell exclusion S02 records. The chain is reachable because nothing in it must behave like the ZK app, only be present, visible and clickable: route interception fulfils the real listing URL so the post-Buscar landing assertion still sees an AEAT url, a static composite fixture carrying the Modelo and Ejercicio labels, the combobox buttons, visible comboitem texts, a Buscar button and the listbox satisfies the form-render check and both combobox drives, and the Buscar click needs no response because the same document already carries the result rows. Gate: a test drives the real walk entry point against that fixture through a real headless browser with no AEAT contact and asserts the truncation refusal surfaces from walk itself, plus a companion asserting the real no-pager capture returns its rows. The new fixture declares synthetic_generated provenance in its sidecar; `src/cadrumo/adapters/outbound/aeat/sede/tests/`.
- [x] `S08` - Narrow _walk_or_failure_row to take the walk awaitable instead of the DeclaracionesRegisterSession, since the register was only ever used to build that coroutine. Behaviour-preserving and dependency-removing rather than parameter-adding, changing no signature any caller outside this module names, and reusing the idiom already sanctioned in the sibling _await_filed_register_walk which is tested by passing it a real coroutine. Covers PER-PAIR failure absorption only: a real refusal raised by a real coroutine becomes a FiledDataCaptureFailureRow and signals the pair be skipped. It does NOT cover CROSS-PAIR continuation, which lives in each bulk function behind active_verified_session and is S06's job. Two different guarantees. Gate: a test drives the narrowed helper with real coroutines, one raising the genuine truncation refusal and another returning real Declaracion rows, asserting the failure is absorbed into a row while a healthy call returns its rows, and reds when the helper is mutated to propagate instead of absorb; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `S09` - Cover capture_filed_data_bulk's own cross-pair continuation property, which S06 left unwalked. S06 added the register-injection seam to BOTH bulk functions as its row required, but exercised continuation through list_filed_data_bulk only, because the capture function resolves an active bucket id before its loop and covering it pulls real encrypted-storage setup into a browser test for a loop that is line-for-line the same shared context manager and the same shared per-pair absorber. What is proven for it today is only that its seam compiles, type-checks and leaves its signature and every caller unchanged, NOT that its loop continues past a failed pair. Two different guarantees, and the deferred cost is the real bucket setup rather than the browser, which S06 proved reachable offline through route interception against composite form-and-grid fixtures. Gate: a test passes a REAL DeclaracionesRegisterSession, never a stub and never a patched production path, over route-intercepted synthetic fixtures with no AEAT contact and against a real active bucket, arranges one query pair truncated and another complete, and asserts the truncated pair becomes a FiledDataCaptureFailureRow while the complete pair still captures its observations, gating on the property and never on a pair count, and redding when the shared absorber is mutated from outside the repository to propagate instead of absorb. CADRUMO_LIVE_TESTS_ENABLED must not be set anywhere and the live-read gate must not be satisfied, since satisfying it rather than bypassing session resolution would arm real AEAT access; `src/cadrumo/application/live/_filed_data_capture.py, src/cadrumo/application/live/tests`.

## Parallelization

S01 must land first: S02 and S03 both consume the typed page result S01
introduces. S02 and S03 touch disjoint files (`_declarations.py` versus
`_filed_data_capture.py`) and may run in parallel once S01 is closed. S04
depends on S02's refusal shape existing and must land in the same change
that closes S02, per the ADR's Constraints (the pinning test must not be
weakened or deleted separately from the fix that supersedes it). S05 depends
on S04's new test existing and runs immediately after S04 closes, before the
Step is marked done, since S05 is the proof that S04's gate actually
detects a regression rather than passing vacuously.

## Verification

The plan is complete when every Step is closed and:

- The pass condition is a PROPERTY, not a count: `test_declarations_pagination_blindness.py`
  asserts that walking a register page where the rendered row count is
  strictly less than the pager's own declared total raises the truncation
  refusal. The existing fixture (declared total 8, rendered 3) exercises
  this property; the test must not assert those specific numbers as the
  pass condition, only that a genuine mismatch is refused.
- A companion test proves the real single-row, no-pager-label fixture
  (`declaraciones-modelo-100-2022.html`) is never classified as truncated,
  so the detector does not false-fire when AEAT serves no pager label.
- S05's mutation proof is recorded as having been run: the S04 test reddened
  under the outside-the-repo monkeypatch and passed again after it was
  removed. A gate with no recorded red run is not yet verified.
- A targeted pytest run over
  `src/cadrumo/adapters/outbound/aeat/sede/tests/` and
  `src/cadrumo/application/live/tests/` (or the narrowest owning test
  directories touched by S01 through S04) passes.
- Per the ADR's Constraints, no live-AEAT probe is run to validate this
  work; the open question of whether AEAT's real grid paginates this form
  stays explicitly unresolved and is not implicitly closed by this plan.
  Building traversal, or running any live authenticated verification of
  pagination, requires separate operator sign-off this plan does not grant.
