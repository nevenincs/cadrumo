---
tags:
  - '#reference'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b64190deba0f4558fadaef85b3296846a66c5fda44e18af64ce22291f7f1e30f'
related: []
---

# `declarations-register-pagination` reference: `Declaraciones register pagination blindness`

Grounds an ADR on whether, and how, the *Consultar declaraciones presentadas*
register walker must detect or traverse AEAT-side result pagination. Sources
consulted: `_declarations_listbox.py`, `_declarations.py`,
`application/live/_filed_data_capture.py`, the existing pinning test at
`adapters/outbound/aeat/sede/tests/test_declarations_pagination_blindness.py`,
and the precedent shape in `entrypoints/cli/_ledger_payloads.py`
(`LedgerListResult`).

## Summary

**Single-snapshot parse, no pager awareness.** `_parse_listbox` (in
`_declarations_listbox.py`) takes one `page.content()` string and returns
every `.z-listitem` row it finds — there is no code path that reads a pager
control, no page-size setting, no "next page" click, and no read of any
declared total. It does not even look for pager markup; the function has no
concept that one exists.

**Both production callers drive exactly one search-then-parse cycle.**
`DeclaracionesRegisterSession.walk` (`_declarations.py:231-247`) and the
free function `walk_declarations_register` (`_declarations.py:375-420`) both:
call `_drive_search` once (fills Modelo/Ejercicio, clicks Buscar, asserts the
post-Buscar landing URL), then call `_parse_listbox` on a single
`page.content()` snapshot, then return. Neither loops, neither inspects
`page.url` or the DOM for a second page, neither is told a page size.

**Every downstream `row_count` is `len(rows)` from that one parse.** In
`application/live/_filed_data_capture.py`, `FiledDataCaptureReport.row_count`
is set from `len(rows)` at three sites (`:328`, `:359`, `:391`); nothing
reconciles it against any AEAT-declared total, because no such total is ever
read. A truncated capture reports a clean, confident count with no signal
distinguishing it from a complete one.

**The only real fixture cannot exercise the gap.** The sole
`real_corpus`-provenance capture (`declaraciones-modelo-100-2022.html`) has
exactly one row and carries no pager markup at all — a single row is
trivially "complete" under any interpretation, so this fixture never forced
a pagination decision.

**The gap is now pinned by a synthetic-fixture test.** Commit `82df6ed81d`
added `test_declarations_pagination_blindness.py`, built on
`declaraciones-modelo-100-paginated-synthetic.html` (provenance:
`synthetic_generated`, per its sidecar). The fixture's own pager label reads
"Pagina 1/3, registros 1-3 de 8 en total" — 8 filings declared, 3 rendered on
the captured page. The test extracts the `8` independently via regex against
the fixture's raw label text (never via anything `_parse_listbox` computes),
then asserts: `_parse_listbox` returns exactly 3 rows; `len(rows) <
declared_total` holds (the parser under-reports); and the returned
`Declaracion` rows expose no `page_count`, `total_registros`, or `truncated`
attribute a caller could consult after the fact. The test's own docstring
states the intended reversal: if a fix teaches the parser to walk pages or
reconcile against the stated total, `len(rows) == declared_total` should then
hold and this characterisation test should be *retired*, not adjusted to keep
passing.

**Unverified: whether AEAT's live grid actually paginates.** ZK Listbox
components only page when the server-side component is configured with
`mold="paging"` (or an equivalent explicit paging mold); that configuration
lives in AEAT's own served markup and cannot be determined by reading this
repository. The fixture that exercises the gap is `synthetic_generated`, not
a live capture — it proves the parser's behaviour *given* a paginated page
shape, not that AEAT ever serves one for this form. Settling that requires an
authenticated live probe against an account with enough filing history to
force a second page; nobody has given operator authorisation for that probe,
and it must not be attempted opportunistically.

**No prior consideration of the question exists in-tree.** No comment,
docstring, or ADR anywhere in the declarations-register code path
acknowledges pagination as a possibility that was weighed and ruled out. The
module-level docstring in `_declarations.py` documents one prior fix (the
Buscar-landing check) precisely because an earlier silent failure — an
off-register landing scraped as an empty result — was diagnosed and closed;
pagination has had no equivalent pass.

**A `total` + `truncated` result shape already exists as in-repo precedent.**
`LedgerListResult` (`entrypoints/cli/_ledger_payloads.py`, around line 648)
carries `rows` (the page actually rendered), `total` (the full bucket row
count), and a `truncated` flag plus `offset`/`limit`, specifically so "a large
ledger is never silently capped." This is a structurally analogous
completeness-signal shape already accepted in this codebase, though it
paginates a LOCAL query the app controls, not a REMOTE AEAT grid whose paging
behaviour is unconfirmed.

## Relevant call graph

- `walk_declarations_register` / `DeclaracionesRegisterSession.walk` →
  `_drive_search` (one Buscar click, one landing assertion) →
  `_parse_listbox` (one DOM snapshot → all rows found, no pager read).
- Consumers of `walk`/`walk_declarations_register`: `capture_previous_filing_observations`
  and `capture_relation_source_observations` (`_declarations.py:1013-1116`) each
  call `register.walk(...)` then select ONE authoritative declaration via
  `_select_authoritative_declaration` (max by `presented_at`) — a truncated
  page could omit the true most-recent filing without changing that
  selection's apparent success.
- `application/live/_filed_data_capture.py` builds `FiledDataCaptureReport` /
  `FiledDataListingReport` from the same `rows` tuple; `row_count` is a pure
  `len()` at every site, and `capture_filed_data_bulk` continues past
  per-`(modelo, ejercicio)` failures by design, collecting them as
  `FiledDataCaptureFailureRow` — a shape a pagination-truncation finding could
  plausibly reuse or must explicitly decide not to.

## Open questions for the ADR

1. Should detection (read+carry the declared total, refuse or flag on
   mismatch) ship ahead of, or instead of, full page-traversal?
2. Where does the AEAT-declared total live once captured — a new field on
   `Declaracion`/the register-session return shape, or a wrapper report
   analogous to `LedgerListResult`?
3. Is a truncated page a per-`(modelo, ejercicio)` `FiledDataCaptureFailureRow`
   (bulk sweep continues) or a hard `SedeParseError`/abort?
4. What happens to `test_declarations_pagination_blindness.py` when detection
   lands — retire, or rewrite to assert the new refusal?
5. Record explicitly: AEAT's real pagination behaviour for this form is
   unverified, and settling it needs an authenticated live probe nobody is
   authorised to run right now.
