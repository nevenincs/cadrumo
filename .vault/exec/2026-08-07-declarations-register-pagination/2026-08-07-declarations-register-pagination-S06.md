---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a188e4e28123019a943bf89f57c78becca61bb94f180d53c06b837b10a79ec10'
step_id: 'S06'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
# Add a minimal purely-additive optional register-injection seam to list_filed_data_bulk and capture_filed_data_bulk, defaulting to today's behaviour so every existing caller and signature is unchanged. Its purpose is SESSION-RESOLUTION bypass, not browser avoidance. Route interception makes the browser reachable with no production change at all, but both bulk paths first call active_verified_session, which runs AeatAccessGate.require_live_read. Under pytest that refuses unless CADRUMO_LIVE_TESTS_ENABLED is the literal 1, and it then drives ensure_authenticated_aeat_session, the central live-session writer needing an active bucket and real credentials. Satisfying that gate rather than bypassing it would ARM real AEAT access, so the seam is what lets the test never request live access in the first place. This is also why the existing navigation-timeout test needs no seam: it drives _drive_search with its own page and never resolves a session. Gate: a test passes a REAL DeclaracionesRegisterSession, never a stub or a patched production path, over route-intercepted synthetic fixtures with no AEAT contact, arranges one query pair truncated and another complete, and asserts the truncated pair becomes a FiledDataCaptureFailureRow while the complete pair still yields rows. Gate on the property, never on a pair count. This closes a gap wider than truncation, since no failure kind currently has coverage of the sweep continuing past a failed pair

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Added one purely-additive keyword-only optional register parameter to both bulk functions, defaulting to None so every existing caller and both signatures are unchanged.
- Extracted the session bring-up both functions duplicated inline into one async context manager that yields the open register and its walk timeout, and which short-circuits only session resolution when a register is supplied. The walk timeout then comes from the local settings load, which contacts nothing.
- Authored two composite synthetic fixtures, each one document that is both the register form and its own result grid, since route interception fulfils every request with the same body and the walk reads the page content after clicking Buscar. One declares more records than it renders; the other carries no pager at all.
- Added the cross-pair continuation test, driving a real headless browser over those fixtures with no AEAT contact.
- Landed a follow-up one-line import correction after a peer's whole-index commit swept this work mid-edit.

## Outcome

The gap this closes is wider than truncation, exactly as the row says. Per-pair absorption already had coverage: a refusal becomes a failure row. What had none was the loop around it. A sweep that stopped at its first failure would emit the identical row for that pair and simply omit every later one, which reads to an operator as a taxpayer who filed nothing afterwards rather than as an aborted run. That is now gated.

The seam's purpose is session-resolution bypass and nothing else, and the row's reasoning holds up under measurement. The browser was already reachable offline with no production change, as the sibling navigation-timeout test shows by driving the form helper with its own page and never resolving a session. What was not reachable is the bulk loop, because both bulk functions resolve a verified session first, which runs the live-read access gate and then the central live-session writer. Satisfying that gate rather than bypassing it would have armed real AEAT access, so it was never attempted and the live-tests opt-in was never set.

Everything the test exercises is real: a real session object, a real headless Chromium page and context, a real register session, the real form drive including the landing assertion and both combobox drives, the real parse, the real refusal and the real sweep. Only the network is intercepted, and only with synthetic fixtures.

What the row asks that this does not fully deliver. The seam was added to BOTH bulk functions as required, but the continuation property is exercised through the listing function only. The capture function resolves an active bucket before the loop, so covering it would pull real encrypted-storage setup into a browser test for a loop that is line-for-line the same shared context manager and the same shared absorber. The standing goal still asks for the capture function's own loop to be walked; what is proven for it today is that its seam compiles, type-checks and leaves its signature and every caller unchanged, not that its loop continues.

The assertions are order-independent by construction, because the route handler cannot see which pair a navigation belongs to: the pair is chosen after the document loads, by driving the comboboxes. So the pages are served in walk order and the property is asserted without naming which year received which page. Some pair is refused for truncation, some other pair returns rows, no pair does both, and every queued page was requested. No pair count is asserted anywhere, per the row: a count would pass equally if the sweep walked one pair twice.

Neither the rendered nor the declared number is hardcoded. Both are read out of the fixture's raw markup by local regexes, never from the parser under test, so the failure row is cross-checked against the page it came from and the assertions travel with the fixture if it is regenerated at a different size.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/application/live/tests/test_filed_bulk_sweep_continues_past_a_failed_pair.py
    1 passed in 23.56s

    uv run --no-sync pytest -n0 -q src/cadrumo/application/live/tests/
    311 passed, 2 deselected in 62.21s

The two deselected carry the external-tool or keychain markers, not the integration marker; a follow-up run of the same directory under the integration marker reported all 313 deselected, so nothing in this directory was hidden behind that lane.

Evidence the whole chain really ran rather than short-circuiting: the adapter logged one completed register search per pair, each naming the pair and reporting the form shape it found, with three grid rows for the truncated page and two for the complete one, plus a Buscar button and six combobox options present in both. That log line comes from after the Buscar click.

Mutation proof of the continuation property. A pytest plugin resident OUTSIDE the repository wrapped the shared per-pair absorber so that a pair it would have reported as a failure row instead propagates, which is precisely the aborting behaviour the assertion claims to detect. No tracked file was edited. The plugin asserted the absorber was present on the module before wrapping and asserted the rebinding took, printing that the mutation was applied and the holder found.

    1 failed in 16.97s
    RuntimeError: MUTATED: the sweep aborts instead of continuing past a failed pair

Both fixtures were verified to parse as intended before any browser work: the paginated one reports three rendered rows against a declared total of eight and is classified truncated; the complete one reports two rows, no declared total, and is not truncated.

Type and lint gates: ty check reported all checks passed on both the production module and the new test, ruff format left both unchanged, ruff check clean.

## Notes

Both new fixtures declare synthetic_generated provenance in their sidecars, alongside a recorded role and the sha256 and byte size of the committed bytes. Each document also carries a comment block stating that it is hand-built, why a composite form-plus-grid document is necessary, and which parts mirror the real capture. Neither carries any input element, so the committed-fixture credential-hygiene scan has nothing to flag.

A peer's whole-index commit under an unrelated subject swept this Step's production seam, its test module and both fixtures into HEAD before the work was finished, taking the test module at a moment when its import of the report class still named the wrong module. HEAD therefore briefly could not collect that module. The correction was landed immediately as its own single-file pathspec commit. No peer content was touched in either direction.

The row's exclusion note is honoured: nothing here performs or requires a live authenticated AEAT probe, and the live-tests opt-in environment variable was never set.
