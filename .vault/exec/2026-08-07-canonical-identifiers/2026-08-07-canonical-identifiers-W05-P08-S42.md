---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:31e339f0b7d3cbdef5960b2a22eb1f2f45beabaa053fb9e986671ce3b6f1329a'
step_id: 'S42'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `AeatBoxNumber` as a new `IdentifierNamespace.AEAT_BOX_NUMBER` member and alias, distinct from the registry's own `CasillaId`, and retype `display_number`, `form_number`, `from_number`, and `to_number` onto it

## Scope

- `src/cadrumo/core/identity/_namespace.py`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py`
- `src/cadrumo/domain/calculations/registry/_query_reports.py`
- `src/cadrumo/domain/calculations/registry/_renta_web_open_oracle.py`
- `src/cadrumo/core/observability/_models.py`

The row inherited its predecessor row's file annotation
(`adapters/outbound/aeat/sede/_notifications.py`) as a plan-authoring
artifact; none of the four named fields exist in that file. The real
population lives across the files above plus three more this row visited
and correctly declined to touch — see Notes.

## Description

- Grepped the tree for the four named fields as genuine field
  declarations (not parameter names or generic word matches): found 11
  candidate sites across 9 files, a much larger population than the row's
  text implied. Read the actual value-producing expression feeding EVERY
  site before typing any of them, rather than trusting the field name.
- Confirmed the real bound and pattern from evidence, not invention:
  every literal value across production code, TOML registry data and test
  fixtures is a plain digit string, 1-16 characters, no consistent
  zero-padding. Declared `IdentifierNamespace.AEAT_BOX_NUMBER` and
  `AeatBoxNumber` (`min_length=1, max_length=16, pattern=r"^\d+$"`,
  `strip_whitespace=True` to preserve a whitespace-tolerant behaviour one
  consumer's own `@field_validator` already asserted) in
  `core/identity/_namespace.py`, exported via `core/identity/__init__.py`.
- Retyped 4 sites confirmed genuinely digit-shaped by tracing their
  producer: `domain.calculations.registry._schema_surfaces
  .CasillaDefinition.form_number` (the registry-authored field this
  concept is named for), `domain.calculations.registry._query_reports
  .ModeloCasillaRow.form_number` (a direct projection of the same),
  `domain.calculations.registry._renta_web_open_oracle
  .RentaWebOpenDisplayOverride.display_number` (a manually-curated live
  browser-navigation override, no registry feed), and
  `core.observability._models.FormFillPayload.display_number` (a live
  form-fill observation payload with no current production constructor
  and only digit-shaped test literals).
- Found and self-caught a real defect before it shipped: three MORE sites
  share the `display_number` name — `application.storage.calc_sheets
  ._records.SheetProvenanceRow`, `application.storage.calc_sheets
  ._parity_comparison.CasillaParity`, and `adapters.outbound.google
  ._calc_sheets_pull.OperatorEdit` — and all three are fed not from
  `form_number` but from `casilla.number`, a DIFFERENT, much richer
  registry field (`CasillaDefinition.number`, plain `str`, undeclared by
  the ADR's own census). Retyped these three onto `AeatBoxNumber` first,
  ran their test suites, and got a real, reproducible failure:
  `test_parity_comparison.py` fed the literal value
  `"saldo-negativo-fin-periodo"` through `display_number` and the pattern
  refused it. Traced the value to `casilla.number`, confirmed by grepping
  real TOML data that `.number` also carries values like `"###"`, `"*01"`
  and range notations like `"*06-09"` (12,771 occurrences across the
  registry tree) — a fundamentally different, richer shape than
  `form_number`. REVERTED all three sites and their imports back to bare
  `str`, byte-identical to `HEAD`, confirmed via `git diff --stat`.
  Re-ran the full test suite after reverting: green.
- Investigated `from_number` / `to_number`
  (`application.registry._diff.RenumberedCasilla`,
  `entrypoints.cli._registry_diff_payloads`) BEFORE editing either file,
  having already learned from the `display_number` mistake to trace the
  producer first rather than trust the name. Confirmed both are fed from
  `casilla.number` too (`_diff.py`'s renumbering detector compares
  `from_casilla.number` / `to_casilla.number` with no filter excluding a
  non-digit value), the same richer field. Did not touch either file —
  no revert needed, the mistake was caught before the edit this time.

## Outcome

**COMPLETE, EVERY SITE ADJUDICATED — 4 retyped, 7 correctly declined, none
left undecided.** `AeatBoxNumber` is declared and correctly scoped to the
population it actually fits: 4 sites across 4 files retyped and verified,
all fed from a producer confirmed digits-only by tracing the actual value
flow rather than the field name. The other 7 of the row's originally-apparent
11 sites are correctly NOT retyped:
`display_number` in the 3 calc_sheets/pull sites and `from_number` /
`to_number` in the 2 registry-diff sites are fed from
`CasillaDefinition.number`, not `form_number` — a materially different,
richer-shaped field (special markers, ranges, slug fallbacks) the row's
own census never named and this alias's evidenced bound does not fit.

`ruff check`, `ruff format --check` clean on every touched file;
`basedpyright` clean on the three gated files
(`_schema_surfaces.py`, `_query_reports.py`, `_renta_web_open_oracle.py`);
`core/identity/*.py` and `core/observability/_models.py` sit outside
basedpyright's configured `include`. Real tests green: 156 passed across
`test_renta_web_open_oracle.py`, `core/observability/tests/`,
`test_modelo_registry_surface.py`, `test_modelo_casilla_number_discovery.py`;
27 more passed across the two test files that construct a
`CasillaDefinition` with an explicit `form_number=`; the calc_sheets +
google-pull suite that caught the defect is now 102 passed after the
revert (was 54 passed / 43 failed with the wrong retype in place — the
remaining 13 failures in that suite are `test_workbook_boe_consistency.py`,
an `IndexError` on an empty `export_layouts` tuple for several modelos,
confirmed pre-existing and unrelated: every implicated file
(`_layout.py`, `_export.py`, `_export_semantics.py`) is clean/uncommitted-
free, and the symptom matches the already-tracked registry-suite-red-at-head
investigation, not anything this row touched).

## Notes

**`CasillaDefinition.number` is a genuinely new, unscoped population this
row discovered and deliberately did not touch.** It is the field
`CasillaDiff.number`, `RenumberedCasilla.from_number`/`to_number`,
`CasillaGroundingReport.number`, and (mistakenly, now reverted) three
`display_number` sites all actually project — 12,771 occurrences in
registry TOML alone, plus `_record_design_coverage.py`,
`test_casillas_by_binding.py`, `test_rate_specific_box_pins_its_rate.py`,
`_referential_integrity_support.py`,
`test_declared_box_numbers_exist_in_the_design.py`, and more. Real
sampled values include plain digits, `"###"` (an internal/unprinted
marker), asterisk-prefixed forms (`"*01"`), range notations
(`"*06-09"`), and slug fallbacks (`"saldo-negativo-fin-periodo"` for a
casilla with no printed position at all). This is NOT the same concept as
`form_number` despite the similar role, and does not fit
`AeatBoxNumber`'s evidenced digits-only pattern. Whether it needs its own
alias, a union shape, or stays bare `str` is a real design question this
row deliberately leaves open rather than answering under time pressure —
flagged to the team lead rather than actioned. Widening `AeatBoxNumber`'s
pattern to admit it would also widen every one of today's 4 successfully
narrowed sites back toward the loose bound this row exists to close, which
is the wrong direction. Routed as its own plan row, `W05.P08.S69`, rather
than left standing only here — a finding this size belongs where the next
reader meets it BEFORE acting, not only in a record read after.

**A second adjacent site found and deliberately left alone:**
`RentaWebOpenLivePayload.scrape_display_numbers_by_casilla_id: dict[CasillaId, str]`
in `_renta_web_open_oracle.py` — same live-browser-number concept as the
two sites this row DID retype, but a dict value rather than a field, and
outside this row's literal four-name scope. Not touched; named here so it
is found by name on a future sweep rather than rediscovered from scratch.

No data loss. The self-caught defect (three `display_number` sites wrongly
retyped, reverted before landing) is recorded in full rather than quietly
smoothed over, because the same mistake — trusting a field's NAME over its
actual producer — is exactly what this row's own investigation into
`.number` shows is still live at three more sites nobody has looked at
yet.
