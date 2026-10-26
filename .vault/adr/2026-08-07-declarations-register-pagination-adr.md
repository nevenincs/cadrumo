---
tags:
  - '#adr'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:373932455ac2a3da44fa0da78ac7fa7a714309c8ce9816946c25ae6fdfef13f7'
related:
  - "[[2026-08-07-declarations-register-pagination-reference]]"
---

# `declarations-register-pagination` adr: `Detect AEAT declarations register pagination truncation` | (**status:** `accepted`)

## Problem Statement

The declaraciones-register walker parses one DOM snapshot and returns it as
the complete filing history for a `(modelo, ejercicio)` pair, with no read of
any pager control (`2026-08-07-declarations-register-pagination-reference`).
`FiledDataCaptureReport.row_count` and its listing sibling are `len(rows)` at
every site, so a truncated capture is reported with the same confidence as a
complete one. This is the same failure shape `no-silent-under-declaration`
already forbids for calculation output — a valid-looking result with no
refusal and no signal — applied to filing-history capture instead of a
casilla value. A decision is needed now because the gap is pinned by
`test_declarations_pagination_blindness.py` (commit `82df6ed81d`) but nothing
yet closes it, and the previous-filing and relation-source capture paths
(`capture_previous_filing_observations`, `capture_relation_source_observations`)
both select "the" authoritative declaration from whatever `walk` returns, so a
truncated page can silently exclude the true most-recent filing.

## Considerations

- Silent truncation is structurally identical to the under-declaration class
  this project refuses to ship quietly — the correct minimum bar is a loud
  refusal, not a best-effort guess (`no-silent-under-declaration`,
  reference summary).
- Full page traversal (clicking through the ZK pager) cannot be validated
  offline: whether AEAT's live grid pages at all for this form is unverified,
  and confirming it needs an authenticated live probe against an account with
  enough filing history, which requires operator authorisation nobody has
  given (reference: "Unverified: whether AEAT's live grid actually
  paginates").
- Detection — reading the pager's own declared total and comparing it against
  the rendered row count — is answerable from the DOM AEAT already serves on
  the single snapshot the walker already fetches; it needs no new navigation
  and is provable against the existing synthetic fixture.
- A `total`/`truncated` result shape is already accepted precedent in this
  codebase (`LedgerListResult`, reference: "A `total` + `truncated` result
  shape already exists as in-repo precedent"), though that shape paginates a
  local query the app controls, not a remote grid whose paging behaviour is
  unconfirmed — the precedent supports the SHAPE, not a claim that AEAT
  necessarily paginates.
- `capture_filed_data_bulk` already has a per-`(modelo, ejercicio)` failure
  taxonomy (`FiledDataCaptureFailureRow`): `_walk_or_failure_row`
  (`_filed_data_capture.py:186-217`) catches any walk failure unconditionally
  and folds it into that row so the sweep continues to the next pair —
  there is no `FAIL_FAST` branch for a walk failure in the bulk path. The
  `FiledCaptureFailurePolicy.FAIL_FAST`/`BEST_EFFORT` axis that DOES exist in
  this file governs a later, separate stage — `finalize_filed_capture`'s
  calculation-observation persistence — and is hardcoded per call site
  (`BEST_EFFORT` for bulk, `FAIL_FAST` for the singular `capture_filed_data`
  and for source capture), not a parameter a walk failure can select
  (reference: "Relevant call graph"; verified directly against HEAD, not
  restated from the reference, which does not make this claim).
- `aeat-worktree-safety` and `aeat-agent-orchestration` forbid landing this
  decision without opening its implementing rows in the same action, since a
  ruling on code with no owner leaves HEAD carrying the old silent behaviour
  while a reader believes the question is settled.

## Considered options

- **A. Full page traversal now.** Teach the walker to click through every
  ZK pager page and concatenate rows. Rejected as the first move: it is the
  larger, riskier change, it cannot be exercised or validated without a live
  authenticated probe nobody is authorised to run, and if AEAT does not
  actually page this form (unconfirmed), the traversal code is dead weight
  guarding a case that never fires. Not ruled out permanently — recorded as
  a follow-on this ADR does not authorise.
- **B. Detect and refuse on mismatch (chosen).** Parse the pager's own
  declared total, if present, off the same DOM snapshot already fetched;
  compare it against the rendered row count; raise loudly on a genuine
  mismatch. Safe to ship even if traversal never lands, provable entirely
  from static fixtures, and turns today's silent gap into an explicit,
  actionable refusal.
- **C. Leave as-is, document the gap only.** Rejected: the gap is already
  documented (the pinning test's docstring, this ADR's own reference) and
  documentation without a code change leaves the silent-truncation failure
  mode live in every real capture.

## Constraints

- The live AEAT pagination behaviour for this specific ZK form is unverified
  and MUST NOT be assumed either way by the implementation; the detector must
  work purely off whatever pager label AEAT's DOM does or does not carry, and
  must not fail when no pager label is present (the single-row real fixture
  carries none).
- No live-AEAT probe may be attempted to settle the open question; this
  constraint is absolute per operator directive and is not relaxed by this
  ADR.
- The fix must not weaken or delete
  `test_declarations_pagination_blindness.py`'s intent; per its own
  docstring, the correct outcome is for that test's assertions to flip to
  assert the new refusal, in the same change that implements detection.

## Implementation

Extend `_parse_listbox` (`_declarations_listbox.py`) to also look for a pager
label in the parsed DOM (the same regex shape the pinning test already uses
against the fixture's raw text, `"de (\d+) en total"`, generalised to the
real markup once implemented) and return a typed page result — not a bare
`tuple[Declaracion, ...]` — carrying the rendered rows, the parsed declared
total (`int | None`, `None` when no pager label is present, which is a
one-page result by construction, not a mismatch), and a derived `truncated`
flag. `DeclaracionesRegisterSession.walk` and `walk_declarations_register`
(`_declarations.py`) consume this typed page instead of a bare tuple; when
`truncated` is `True` they raise a `SedeParseError` naming the modelo,
ejercicio, rendered count and declared total, rather than returning
degraded data silently.

That refusal is caught exactly where every other per-pair register failure
is already caught: `_walk_or_failure_row` catches it unconditionally and
folds it into a `FiledDataCaptureFailureRow`, so the bulk sweep continues to
the next pair. This is a deliberate design property, not an oversight: bulk
capture's walk stage is unconditionally best-effort by construction, and it
carries no `FAIL_FAST` branch to fall back to — the fail-fast equivalent for
one pair lives in a different function, `capture_filed_data` (the singular,
non-bulk capture), whose walk failure is never caught and propagates
uncaught to its caller. `FiledCaptureFailurePolicy.FAIL_FAST`/`BEST_EFFORT`
is a real axis in this file, but it governs the later
calculation-observation persistence stage inside `finalize_filed_capture`,
not the walk stage this ADR's refusal fires from; this ADR does not touch
that axis or that later stage. No new bulk control-flow mechanism is
introduced — truncation reuses the walk-failure taxonomy that already
exists for this exact purpose.

Full page traversal is explicitly out of scope for this ADR; it is Considered
option A recorded as a live follow-on, not authorised here.

## Rationale

Option B wins on a knockout criterion: it is the only option provably
correct today, entirely from the fixtures already in-tree, without requiring
the unauthorised live probe that both settling "does AEAT paginate this form"
and validating traversal (option A) would need. It also directly closes the
`no-silent-under-declaration` gap the reference identifies — the operative
harm is the silent confident report, and a loud refusal removes that harm
regardless of whether AEAT's real grid turns out to page or not. Reusing the
existing `FiledDataCaptureFailureRow` taxonomy (rather than inventing a new
abort mechanism) keeps the bulk sweep's continuation semantics intact and
avoids a second, competing failure-reporting channel.

## Consequences

- **Gain:** a truncated filing-history capture becomes an explicit, named
  failure instead of a clean-looking undercount; `capture_previous_filing_observations`
  and `capture_relation_source_observations` inherit the same protection for
  free, since both consume `register.walk(...)`.
- **Difficulty:** the pager-label regex is authored against one synthetic
  fixture's text and has never been checked against AEAT's live markup;
  a genuine shape mismatch (different wording, different total position)
  will surface as `declared_total is None` (treated as one page, not a
  refusal) until a real multi-page capture is obtained to verify the regex
  — which itself requires the unauthorised live probe. This residual risk is
  accepted rather than closed by this decision.
- **Pitfall avoided:** the `no-silent-under-declaration` failure mode this
  campaign closes is specifically the "valid-looking output, no refusal, no
  signal" shape; detection-without-traversal fully closes that shape for
  filing-history capture even though it leaves the traversal capability
  unbuilt.
- **Pathway opened:** if a future live probe (under proper authorisation)
  confirms AEAT does page this form, option A (traversal) becomes buildable
  on top of the same typed page/declared-total plumbing this ADR introduces,
  and `test_declarations_pagination_blindness.py`'s successor assertion
  (`len(rows) == declared_total`) becomes the traversal gate rather than the
  refusal gate.
- **Unresolved, recorded explicitly:** whether AEAT's real register grid
  paginates this form is NOT settled by this ADR. This decision governs what
  the walker does about pagination it CAN detect from the DOM it already
  fetches; it does not claim to know whether that DOM ever actually carries
  a multi-page pager in production.
