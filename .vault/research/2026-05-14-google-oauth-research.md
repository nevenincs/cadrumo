---
tags:
  - "#research"
  - "#google-oauth"
date: "2026-05-14"
modified: '2026-05-14'
related: []
---

# google-oauth research: Sheets bidirectional roundtrip research

Prior-art and capability survey covering the four streams that gate the
Sheets-as-roundtrip-surface ADR: Sheets formula expressiveness vs. the
registry DSL, prior art on ledger/Sheets bidirectional sync, the parity
verification standard, and the operational coherence of multi-turn edits.

All claims are cited. Speculation is forbidden by the task contract.

## Stream A: Sheets formula capability boundary

### Registry DSL surface (locally observed)

The registry formula runtime (`_evaluate_expression` and
`_evaluate_leaf`) currently dispatches on the following `op` strings:
`add`, `sum`, `subtract`, `multiply`, `divide`, `percent`, `min`,
`max`, `clamp`, `negate`, `copy`, `lookup_parameter`,
`previous_period_value`, `cross_model_sum`, `previous_period_sum`,
`if_then_else`, plus comparator leaves `less_than`, `less_equal`,
`greater_than`, `greater_equal`, `equal`, plus two bracket-table
lookups `lookup_bracket` and `lookup_bracket_by_ccaa`. The set is
small and arithmetic; no string ops, no date arithmetic, no array
ops, no regex. (Observed in `_formula_runtime.py:152-364`.)

### Sheets coverage of each op

Sheets supports every arithmetic op the registry uses via direct
formula equivalents: operators `+`, `-`, `*`, `/`, the `^`
exponentiator, and the functions `SUM`, `ROUND`, `MROUND`,
`ROUNDUP`, `ROUNDDOWN`, `INT`, `FLOOR`, `CEILING`, `MIN`, `MAX`,
`IF`, `VLOOKUP`, `INDEX`, `MATCH`, `SUMIF`, `SUMIFS`,
`SUMPRODUCT`, `INDIRECT` ([Google Docs Editors Help: ROUND][1],
[OWOX rounding guide][2], [Sheets Bootcamp: ROUND variants][3]).

Mapping:

- `add` / `sum` / `subtract` / `multiply` / `divide` map to binary
  operators or `SUM`.
- `percent` maps to `value * rate / 100` or `value * rate`
  depending on whether the rate is stored as a fraction or as a
  percent.
- `min` / `max` / `negate` map to `MIN`, `MAX`, `-value`.
- `clamp` maps to `MIN(upper, MAX(lower, value))` (nested; nesting
  is the documented composition pattern in Sheets
  ([thebricks: nesting formulas][4])).
- `if_then_else` with comparator leaves maps to `IF(condition,
  then, else)`; comparators are native operators `<`, `<=`, `>`,
  `>=`, `=`.
- `copy` maps to a single cell reference `=A1` ([Google
  ValueRenderOption reference][5] uses this exact example).
- `lookup_parameter`, `lookup_bracket`, and `lookup_bracket_by_ccaa`
  map to `VLOOKUP(value, named_range, col, TRUE)` against a named
  range that stores the parameter table; tax brackets are the
  canonical Sheets use case ([Exceljet: VLOOKUP tax rate
  calculation][6], [SpreadsheetWeb: VLOOKUP basic tax rate][7],
  [Acctadv: dynamic income tax calculator parts 1 plus 2][8]).
  IRPF-style tramos with CCAA-conditional tables map to
  `VLOOKUP(income, INDIRECT(ccaa_table_name), col, TRUE)`;
  `INDIRECT` is the documented mechanism for dynamic table
  selection ([Excel University: income tax formula][9]).
- `previous_period_value`, `previous_period_sum`, and
  `cross_model_sum` map to cross-sheet cell references such as
  `=Sheet_2025Q1!A1` or `SUM(Sheet_2025Q1:Sheet_2025Q4!A1)`.
  No workaround needed; the challenge is layout, not formula
  expressiveness.

### Functions Sheets has that the registry DSL does not

Sheets has hundreds of functions the registry does not use: text
(`CONCATENATE`, `REGEXEXTRACT`), date (`DATE`, `YEAR`, `EOMONTH`),
array (`ARRAYFORMULA`, `FILTER`, `QUERY`), and Apps Script custom
functions ([Google Docs Editors Help full function list][10]).
None are required by the registry current op set; they become
relevant only if a future DSL op adds date arithmetic or string
manipulation.

### Functions the registry DSL has that Sheets does not

None observed. Every registry op maps to a Sheets primitive. The
DSL surface is a strict subset of the Sheets arithmetic
vocabulary.

### Numeric precision: Decimal vs binary64 -- the parity blocker

This is the load-bearing finding. The Python side uses
`decimal.Decimal`, which is base-10 and arbitrary precision (28
digits by default, configurable) ([Python docs: Floating-Point
Arithmetic][11]). Sheets evaluates every formula in IEEE 754
binary64 with about 15 to 16 significant decimal digits of
precision ([Higham: How Accurate Are Spreadsheets in the
Cloud?][12], [Wikipedia: Numeric precision in Microsoft
Excel][13], [Endjin: Excel data loss IEEE754 and precision][14],
[Microsoft Learn: floating-point arithmetic may give inaccurate
result in Excel][15]).

Concrete consequence: `Decimal("0.1") + Decimal("0.2") ==
Decimal("0.3")` exactly. Sheets evaluates `=0.1+0.2` to a
binary64 approximation whose nearest decimal display is `0.3`
but whose underlying bits represent `0.30000000000000004...`
([Endjin article][14], [Microsoft Learn][15]). For tax
computations where every casilla is rounded to two decimal
places after every operation, the two engines will agree most
of the time. They will disagree on boundary cases where a
sub-cent residual crosses a rounding threshold.

The disagreement is structural, not a bug. Bit-exact identical
results -- the user stated goal -- is unachievable as stated;
what is achievable is identical-after-the-AEAT-prescribed-rounding-
rule applied at every casilla boundary. Every modelo
workbook-style oracle already lives with this constraint because
workbooks themselves are binary64.

The Sheets-side floor is about `1e-15` relative error per
operation; worst-case accumulation over a 100-cell chain is
about `1e-13`, far below a 0.01 EUR rounding granularity. The
mitigation is to emit `ROUND(formula, 2)` at every casilla
boundary so the binary64 residual is discarded before the next
cell consumes it. This matches what Excel-based tax templates
already do ([Excel University: income tax formula uses ROUND on
every output][9]).

### API endpoint for evaluating a formula remotely

The user hypothesis is correct: `spreadsheets.values.get` with
`valueRenderOption=UNFORMATTED_VALUE` returns the computed value
after Sheets evaluates the formula ([Google ValueRenderOption
docs: Values will be calculated but not formatted in the reply;
for example if A1 is 1.23 and A2 is =A1 and formatted as
currency, then A2 would return the number 1.23][5]).
Alternatives are `FORMATTED_VALUE` (locale-formatted string,
default) and `FORMULA` (returns the formula text `=A1` rather
than its result) ([Google ValueRenderOption REST docs][17]).

The same option is available on `spreadsheets.values.batchGet`
and `spreadsheets.values.batchGetByDataFilter`. For roundtrip
pulls, `batchGet` is the cost-efficient surface.

### Stream A summary

Capability-wise, Sheets is a superset of the registry DSL;
every op maps. The capability boundary is precision, not
function coverage. The parity contract cannot be bit-exact
but can be exact after per-casilla `ROUND(_, 2)`. This is the
ADR central constraint to either accept or reject.

[1]: https://support.google.com/docs/answer/3093440
[2]: https://www.owox.com/blog/articles/ceiling-floor-round-google-sheets
[3]: https://www.sheetsbootcamp.com/round-functions/
[4]: https://www.thebricks.com/resources/guide-how-to-nest-formulas-in-google-sheets
[5]: https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueRenderOption
[6]: https://exceljet.net/formulas/vlookup-tax-rate-calculation
[7]: https://spreadsheetweb.com/how-to-calculate-basic-tax-rate-with-vlookup/
[8]: https://www.acctadv.com/build-a-dynamic-income-tax-calculator-part-1-of-2/
[9]: https://www.excel-university.com/income-tax-formula/
[10]: https://support.google.com/docs/table/25273
[11]: https://docs.python.org/3/tutorial/floatingpoint.html
[12]: https://nhigham.com/2013/03/13/how-accurate-are-spreadsheets-in-the-cloud/
[13]: https://en.wikipedia.org/wiki/Numeric_precision_in_Microsoft_Excel
[14]: https://endjin.com/blog/2022/07/excel-data-loss-ieee754-and-precision
[15]: https://learn.microsoft.com/en-us/office/troubleshoot/excel/floating-point-arithmetic-inaccurate-result
[17]: https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get

## Stream B: Bidirectional sync prior art

### QuickBooks Online (QBO) -- Spreadsheet Sync

Intuit ships first-party Spreadsheet Sync for QBO Advanced and
QBO Accountant. The native target is Excel only, not Sheets
([Intuit: Get started with Spreadsheet Sync][b1], [Intuit: QBO
Advanced Spreadsheet Sync product page][b2]).

The Excel sync surface is bidirectional: edits flow Excel to QBO
and QBO to Excel through an explicit push or pull action; it is
not a live link. The user explicitly triggers each direction
([Intuit: send data back and forth between QuickBooks Online
Advanced][b1]). There is no documented automatic conflict
resolution -- last write wins on whichever side commits last.

For Google Sheets, QBO has no first-party sync. Third-party
gateways (G-Accon, SheetsSync, Coefficient, Coupler.io) provide
two-way sync of varying fidelity ([Google Workspace Marketplace:
G-Accon for QuickBooks][b3], [SheetsSync product page][b4],
[Coefficient: connect QuickBooks][b5], [Coupler.io: QuickBooks
to Google Sheets][b6]). None publishes a documented conflict-
resolution semantics beyond scheduled batch-overwrite.
SheetsSync marketing language (two-way sync, auto-import)
describes scheduled pull plus manual push, not operational-
transform merge.

### Xero -- same shape

Xero has no first-party Sheets sync. Third-party gateways
(G-Accon for Xero, Amalgam, Unito, SyncHub) ship bidirectional
sync with a scheduled batch model ([G-Accon for Xero on Xero App
Store][b7], [Amalgam description in Coupler blog][b8],
[Unito Google Sheets <-> Xero][b9], [SyncHub Xero to
Sheets][b10]). Amalgam positioning is explicit: download data,
edit that data, then sync it back to Xero without ever closing
the spreadsheet ([Coupler.io Xero blog citing Amalgam][b8]).

API-driven custom integration via Apps Script plus Xero API is
the documented if-you-have-strong-technical-skills path
([Coupler.io blog][b8]). No vendor publishes a formal conflict
contract.

### Sheetgo and Coupler.io -- generic Sheets-to-Sheets two-way sync

Sheetgo documents two-way sync but with an explicit guard:
transfer data from the destination spreadsheet back to the
source one for analysis, but you cannot modify the same data in
different spreadsheets ([Sheetgo Help Center: Create a two-way
sync][b11]). In other words, Sheetgo two-way is two one-direction
channels, with the user contractually forbidden from concurrent
edits. This is partition-by-cell, not a merge.

Coupler.io supports two-way sync for BigQuery, Google Sheets,
and Excel destinations ([Coupler.io blog: Sheetgo alternative
comparison][b12]). Documented conflict resolution: none public.
G2 reviews and the comparison blog do not surface an LWW vs CRDT
contract.

The general industry pattern for Sheets-as-mirror is documented
in DZone Conflict Resolution: Using Last-Write-Wins vs CRDTs
([DZone article][b13]) and Mobterest Conflict resolution
strategies in Data Synchronization ([Medium article][b14]):
the options are (a) last-write-wins on a server-side timestamp,
(b) optimistic concurrency via ETag or version-token (412
Precondition Failed on stale write), (c) CRDTs or operational
transforms.

Google Sheets itself uses operational transforms internally for
the live web UI; this is opaque to the API client and not exposed
as a merge primitive. The closest API-level primitive is Drive
ETag (`If-Match` header) for conditional writes
([Wikipedia: HTTP ETag][b15], [Google general guidance on
ETag-based optimistic concurrency from Secret Manager docs which
is the same pattern Google APIs use][b16]). The Google Sheets
v3-to-v4 migration guide notes that gd:etag attributes were
available on list-feed rows in v3 for conditional updates
([Google Sheets API migration guide][b17]); v4 `batchUpdate` has
a `writeControl` / `targetRevisionId` field on
`BatchUpdateSpreadsheetRequest` for the same purpose ([Issue
Tracker 205023847: writeControl for spreadsheet batchUpdate][b18]).

### Tax-software-specific prior art

A search for two-way Sheets sync in TurboTax, FreshBooks,
Xero Tax, and Spanish hacienda software returned no first-party
implementations. TurboTax accepts imports from QBO and CSV
([Intuit support: import expenses from FreshBooks][b19]);
exports are PDF or return files, not live spreadsheets.
FreshBooks does CSV export, not bidirectional sync
([FreshBooks: 5 Best Tax Software][b20]).

For Spain specifically: AEAT itself moved away from downloadable
help programs in 2017. The historical Programa PADRE was a
desktop simulator, never a spreadsheet ([Bolsamania: Programa
Padre history][b21], [AEAT: Renta ayuda tecnica][b22]). The
current Renta WEB is a web-form UI; no spreadsheet export
contract exists.

The academic state of practice is captured by TaxCalcBench
([arxiv 2507.16126: TaxCalcBench -- evaluating LLMs against a
deterministic tax engine][b23]). It treats a deterministic tax
engine as the oracle and tests other systems against it. This is
the differential-testing paradigm; it does not address Sheets-
as-roundtrip.

### Stream B summary

No precedent exists for the exact contract being designed:
operator edits formula cells in Sheets, app pulls edits back as
authoritative state, both engines guarantee parity. Every
prior-art system either (a) treats Sheets as a read-only mirror
(API Connector, most Coupler.io pulls), (b) treats Sheets as a
write-only inbound form (Google Forms pattern), or (c) partitions
data so concurrent edits cannot collide (Sheetgo explicit rule).

The closest analog is QBO Excel Spreadsheet Sync, which solves
the conflict by making the sync explicit and manual -- the
operator chooses when to push and when to pull, and the last
explicit action wins. This is a usable model for the ADR.

[b1]: https://quickbooks.intuit.com/learn-support/en-us/help-article/accounting-bookkeeping/spreadsheet-sync/L3jiBUftI_US_en_US
[b2]: https://quickbooks.intuit.com/online/advanced/spreadsheet-sync/
[b3]: https://workspace.google.com/marketplace/app/gaccon_for_quickbooks/652300792306
[b4]: https://getsheetssync.com/
[b5]: https://coefficient.io/quickbooks/how-to-connect-quickbooks-online-to-google-sheets
[b6]: https://www.coupler.io/google-sheets-integrations/quickbooks-to-google-sheets
[b7]: https://apps.xero.com/us/app/g-accon-for-xero
[b8]: https://blog.coupler.io/xero-to-google-sheets/
[b9]: https://unito.io/integrations/google-sheets-xero/
[b10]: https://www.synchub.io/xero-to-googlesheets-connector
[b11]: https://support.sheetgo.com/en/articles/8529696-create-a-two-way-sync
[b12]: https://blog.coupler.io/sheetgo-alternative/
[b13]: https://dzone.com/articles/conflict-resolution-using-last-write-wins-vs-crdts
[b14]: https://mobterest.medium.com/conflict-resolution-strategies-in-data-synchronization-2a10be5b82bc
[b15]: https://en.wikipedia.org/wiki/HTTP_ETag
[b16]: https://cloud.google.com/secret-manager/docs/etags
[b17]: https://developers.google.com/workspace/sheets/api/guides/migration
[b18]: https://issuetracker.google.com/issues/205023847
[b19]: https://ttlc.intuit.com/community/taxes/discussion/how-do-i-import-expenses-from-freshbooks/00/1208811
[b20]: https://www.freshbooks.com/hub/taxes/best-tax-software
[b21]: https://www.bolsamania.com/declaracion-impuestos-renta/programa-padre-programa-de-ayuda-declaracion-de-la-renta/
[b22]: https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica.html
[b23]: https://arxiv.org/html/2507.16126v1

## Stream C: The parity guarantee -- how to actually verify

### Differential testing as the rigour standard

Differential testing is the documented industry pattern for tax
engines: feed identical inputs to N implementations, assert
identical outputs ([TaxCalcBench, arxiv 2507.16126: 100% baseline
because models are compared to a deterministic traditional-code
engine][c1]). The Sheets-roundtrip problem maps cleanly:
implementation A is the Python registry runtime, implementation
B is the Sheets-translated formula set. Inputs are casilla-level
operator entries.

No US, EU, IRS, or AEAT standard mandates this specific pattern.
The IRS Assurance Testing System (ATS) for accepted e-filers
requires that tax calculations on the test return match the
expected answers ([IRS Publication 1436 -- Assurance Testing
System][c2], [IRS: how tax preparation software is approved for
electronic filing][c3]), but the expected answers come from an
IRS scenario library, not from a third-party engine. AEAT
developer-facing requirements published on the sede portal cover
record-design conformance (modelo XML or TXT formats) and scanner
certification ([Expensya: AEAT technical requirements for scanner
certification][c4]), not arithmetic parity oracles. AEAT has no
equivalent of ATS scenario sets that are publicly downloadable.

ISO 9001 and SOC 2 do not mandate differential testing
specifically; they require documented test plans and
traceability. AICPA SOC 2 for SaaS tax tools maps to operating
effectiveness of controls, which differential testing satisfies
if the test plan documents the oracle.

The rigour standard for this codebase is already set by the
project rule `.claude/rules/no-tautological-calculation-tests.md`:
expected values must come from external authority (AEAT workbook
parity, AEAT-published worked examples, live oracle replay).
Differential testing against Sheets is a third oracle. It counts
as external because Sheets evaluates formulas independently of
the registry Python code path. The caveat is that Sheets-side
formulas are themselves emitted by our translation layer; if both
engines share a bug in the translation layer, both will agree
wrongly. This is the classic co-mutated oracle risk in
differential testing and must be mitigated by also asserting
against `dr.xls`-style workbooks where available.

### Evaluating Sheets formulas without round-tripping to Google

Three approaches with documented Python tooling:

- **`formulas` library** -- pure-Python Excel formula interpreter,
  parses and compiles `.xlsx`, `.ods`, and `.json` workbooks to
  Python and executes without Excel ([formulas on PyPI][c5],
  [GitHub vinci1it2000/formulas][c6], [formulas docs][c7]).
  Strong feature: covers a large subset of Excel functions
  including the ones the registry needs (`SUM`, `ROUND`, `IF`,
  `VLOOKUP`, `MIN`, `MAX`). Weakness: it implements Excel
  semantics; Sheets is largely compatible but not identical
  (`QUERY` is Sheets-only; `IFS` differs in some edge cases).
  Sufficient for CI-time parity tests of the registry actual op
  surface, which is the Excel-common subset.

- **`xlcalculator` / `xlsx_evaluate`** -- similar Python formula
  evaluator forks ([xlcalculator on PyPI][c8], [GitHub
  bradbase/xlcalculator][c9], [xlsx-evaluate on PyPI][c10]).
  Smaller function coverage than `formulas`, same no-Excel
  design.

- **LibreOffice headless `--convert-to`** -- the workbook is
  opened by the LibreOffice Calc engine, all formulas are
  recalculated, and the cached values are persisted to a new
  file. Subsequent reads via `openpyxl(data_only=True)` see those
  cached values ([MiniMax-AI skills repo: libreoffice_recalc.py
  script][c11], [openpyxl docs: data_only param][c12], [Ask
  LibreOffice: recalculate with --convert-to][c13]). This is the
  most faithful local evaluation because LibreOffice Calc shares
  the same lineage of OpenFormula semantics as Excel and most
  Sheets behaviours. The CPU cost is the LibreOffice startup tax
  per workbook; a long-lived `soffice --accept=socket` service
  via pyoo is the workaround ([pyoo on PyPI][c14]).

Recommendation: tier the parity oracle.

- Tier 1 (fast, every test): `formulas` library, runs in-process.
- Tier 2 (nightly): LibreOffice headless, validates against the
  actual spreadsheet engine for the registry full op set.
- Tier 3 (release-gate): live Sheets `spreadsheets.values.get`
  with `UNFORMATTED_VALUE`, validates that the formulas as
  actually serialized into Sheets produce the same results as
  the registry. This is the only oracle that catches
  Sheets-specific divergences (locale, function aliasing,
  recalculation order).

`openpyxl` alone is insufficient: it reads cached values but
does not evaluate ([openpyxl users group: openpyxl will not
evaluate the formulas][c12]). It needs either pre-cached
workbooks (the workflow forces a LibreOffice recalc step) or
pairing with `formulas`.

### `dr.xls` -- the AEAT workbook parity oracle

The repo already uses `workbook_parity_refs` as a registry-level
contract (referenced by
`.claude/rules/no-tautological-calculation-tests.md` as one of
the four valid oracles). Searches did not surface the AEAT
historical `dr.xls` (declaracion de la renta workbook) as a
currently downloadable artifact. The AEAT downloadable-programs
catalog ([AEAT: Descarga de programas de ayuda][c15]) lists help
programs for Sociedades, IVA, IRPF withholdings, etc., but the
Renta surface migrated to Renta WEB in 2017 with no workbook
export ([Bolsamania: PADRE history -- programs disappeared in
2017][c16], [AEAT: Renta WEB manual PDF][c17]).

For modelos other than 100 (Renta), `dr.xls`-style diseno-de-
registro workbooks are published as record-format specifications
in the Modelos 100 to 199 diseno-de-registros catalog ([AEAT:
presenting Renta via externally generated file][c18]); these are
file-format specs, not calculation oracles. The registry existing
`workbook_parity_refs` field likely points at modelo-specific
calculation workbooks that historically shipped with PADRE-family
programs and are internally preserved; they are not currently a
public AEAT download URL for the Renta surface.

### Stream C summary

Differential testing is the right pattern; the oracle stack must
be tiered. The Python-side library that meets the daily-test
requirement is `formulas`. The release-gate oracle must be live
Sheets evaluation through `spreadsheets.values.get` with
`valueRenderOption=UNFORMATTED_VALUE`. `dr.xls`-as-oracle is not
currently sourceable for Renta; it remains valid for IVA and
withholding modelos where the registry has retained the workbook
references.

[c1]: https://arxiv.org/html/2507.16126v1
[c2]: https://www.irs.gov/pub/irs-pdf/p1436.pdf
[c3]: https://www.irs.gov/e-file-providers/how-tax-preparation-software-is-approved-for-electronic-filing
[c4]: https://help.expensya.com/l/en/article/5s35kn2x9x-the-technical-requirements-of-the-aeat-for-certifying-the-scanner
[c5]: https://pypi.org/project/formulas/
[c6]: https://github.com/vinci1it2000/formulas
[c7]: https://formulas.readthedocs.io/
[c8]: https://pypi.org/project/xlcalculator/
[c9]: https://github.com/bradbase/xlcalculator
[c10]: https://pypi.org/project/xlsx-evaluate/
[c11]: https://github.com/MiniMax-AI/skills/blob/main/skills/minimax-xlsx/scripts/libreoffice_recalc.py
[c12]: https://openpyxl.readthedocs.io/en/stable/formula.html
[c13]: https://ask.libreoffice.org/t/recalculate-wit-command-line-option-convert-to/36678
[c14]: https://pypi.org/project/pyoo/
[c15]: https://sede.agenciatributaria.gob.es/Sede/ayuda/descarga-programas-ayuda.html
[c16]: https://www.bolsamania.com/declaracion-impuestos-renta/programa-padre-programa-de-ayuda-declaracion-de-la-renta/
[c17]: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Tecnicos/Renta/2023/RentaWEB2023.pdf
[c18]: https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/presentar-declaracion-mediante-fichero-generado-externo.html

## Stream D: Round-trip operational concerns

### Live-collaboration semantics in Sheets

Google Sheets is operational-transform-based; concurrent edits to
different cells merge cleanly, and concurrent edits to the same
cell resolve last-write-wins where last is the order in which the
server processes the edits ([Google Workspace: real-time
editing][d1], [Quora: simultaneous offline edits in Sheets][d2]).
Structural changes (row delete, column insert, sheet rename)
apply in server-received order and can invalidate cell edits that
referenced the affected range ([Quora reply on simultaneous
edits][d2]).

This is the OT model. As an API client, the app code is one more
collaborator. There is no privileged write path.

### External-modification warnings

There is no Sheets-side this-file-was-modified-externally modal
dialog of the kind Excel surfaces for desktop files. The
collaboration model assumes all writes are equal and merged in
real time. The operator with the Sheet open sees external edits
appear live in cells, with the cell briefly highlighted in the
editing collaborator color (the API client appears as the
authenticated service account or OAuth user). There is no UI to
accept or reject an external write.

For optional alerting, Sheets supports a per-range
show-a-warning-when-editing-this-range setting that prompts the
editor for confirmation, but it does not block writes
([thebricks: stop overwriting in Sheets][d3], [Google Docs Help:
protected ranges warning][d4]). This is operator-facing only --
the API service account can be granted edit access to
warning-marked ranges and writes complete without prompting.

### Push notifications when the operator edits

The Drive API exposes `changes.watch` for push notifications on
file changes ([Google Drive notifications-for-resource-changes
guide][d5], [Method: changes.watch v2][d6]). Confirmed
limitation: push notifications are batched and delivered at most
every ~3 minutes, not in real time
([googleapis/google-api-go-client issue #444: how to get
real-time updates for spreadsheets][d7], [Medium: building Drive
webhooks][d8]). The notifications carry no cell-level diff; they
only tell the client that the file changed. To identify what
changed, the client must call `spreadsheets.values.get` on the
affected ranges and diff against its own last-known state.

Drive Activity API and Workspace audit logs are alternatives for
enterprise-grade change tracking ([labnol.org: Drive Activity
patterns][d9]). Neither offers cell-level granularity.

The Revisions API can list and fetch full snapshots, but the
docs explicitly warn: the list of revisions returned by this
method might be incomplete for files with a large revision
history, including frequently edited Google Docs, Sheets, and
Slides. Older revisions might be omitted ([Google Drive
Revisions guide][d10], [Method: revisions.list v3][d11]). The
roundtrip workflow cannot rely on revision history as a complete
change ledger.

### Optimistic concurrency: ETag, writeControl, targetRevisionId

`BatchUpdateSpreadsheetRequest` supports a `writeControl`
parameter that takes either a `requiredRevisionId` (matches a
specific revision) or a `targetRevisionId` (matches a specific
revision or rejects with 412) ([Issue Tracker 205023847][d12],
[Google Sheets API v4 BatchUpdate Java reference][d13]). This
implements optimistic concurrency: the app fetches the current
revision id, computes its update, submits it with
`requiredRevisionId=last_seen`; if the operator edited the Sheet
in the interim, the request fails and the app must refetch and
retry. This is the ETag pattern adapted to Sheets ([Wikipedia:
HTTP ETag][d14], [event-driven.io: ETag for optimistic
concurrency][d15], [fideloper: ETags and optimistic
concurrency][d16]).

Caveat: head-revision tracking via Drive `headRevisionId` is
documented as available only for blob files, not for Google
Sheets native files ([Google Drive revisions.list v3
notes][d17]). The `writeControl.targetRevisionId` on the Sheets
v4 batchUpdate is the workable surface.

For the values endpoint, `spreadsheets.values.update` does not
expose the same writeControl primitive ([Google Sheets values
update guide][d18]); the safe write path for guarded updates is
to route every write through `batchUpdate` with `writeControl`,
or to accept LWW semantics for value writes.

### Edit conflict between operator and app re-export

The user concern: operator edits A1, app simultaneously re-
exports -- who wins? Three regimes:

- **App write via `batchUpdate` with `requiredRevisionId`.** If
  operator edit landed first, the app write is rejected with
  HTTP 412; the app refetches, recomputes, retries. This is safe
  but adds latency.
- **App write via plain `values.update` without writeControl.**
  Last-write-wins. If the operator wrote 100 to A1 at t1 and the
  app writes 200 to A1 at t2 > t1, the operator edit is silently
  overwritten. This is the unsafe regime.
- **App writes only to disjoint ranges from operator-editable
  ranges.** Cell partitioning. The operator owns the input cells;
  the app owns the formula cells and computed-output cells. With
  protected-range guards, concurrent edits never target the same
  cells. This sidesteps the conflict entirely.

The partitioning regime is the cleanest, but it breaks the user
stated operator-edits-formula-cells-too requirement. The ADR
will have to choose between (a) operator-edits-formulas plus the
requiredRevisionId-refetch loop or (b) operator-edits-inputs-only
plus the partition.

### Read-write workspace -- what `_workspace/` means operationally

The user note references an ADR-2 reservation for
`aeat-vault/_workspace/`. The text of that ADR is not in scope of
this research stream; the term read-write workspace used in
isolation maps in the broader Google Drive context to a folder
where the OAuth client has both read and write scope and where
Sheet files can be created, mutated, and deleted by the app
without operator intervention. The semantics of workspace in the
local `aeat-vault/_workspace/` directory must be defined by the
ADR; the prior-art finding is that no industry convention binds
the term and the codebase is free to define it as app-owned
spreadsheets the operator may also touch.

### Real-time collaboration: operator accountant has the Sheet open

If the accountant has the Sheet open in a browser and the app
issues `batchUpdate` writes, the accountant sees the cells update
in real time, attributed to the app OAuth identity. This is
documented Sheets behaviour ([Google Workspace real-time editing
page][d1]). No document-was-modified modal appears. The
accountant can undo the app write via Cmd+Z or Ctrl+Z, which the
API client cannot detect except via a subsequent `values.get`
showing the reverted value.

If the accountant is actively typing into a cell at the moment
the app writes the same cell, OT resolves it last-write-wins on
server-receipt order. There is no way to lock a cell against the
operator.

### Operational mitigations for multi-turn coherence

Documented patterns from third-party tooling and Google guidance:

- **Periodic poll-and-merge** (every ~30s via `values.batchGet`
  with `UNFORMATTED_VALUE`) to detect operator changes between
  app writes. The 3-minute webhook batching makes push unsuitable
  for sub-minute coherence.
- **Conditional writes** (`batchUpdate` plus `writeControl`) on
  every app write, with bounded retry on 412.
- **Protected ranges** (`addProtectedRange` in the v4 API) to
  carve out app-owned formula cells the operator can edit only
  with a warning ([Google Docs Help: Protect, hide & edit
  sheets][d4]).
- **Idempotent re-export**: every re-export is a full state
  reconciliation, not a delta apply; this makes operator-side
  undo and app-side rewrite commutative (the app converges to
  the registry authoritative state on the next cycle).
- **Out-of-band operator pause signal**: a named cell or sheet
  metadata flag that the operator toggles to I-am-editing-do-not-
  re-export so the app refrains. This is the QBO Spreadsheet Sync
  mental model.

### Stream D summary

The operational surface is workable but constrained:

- Real-time push notifications are not available; 3-minute
  batching is the floor for Drive webhook latency.
- Cell-level diff requires app-side state and polling.
- Optimistic concurrency is available via batchUpdate
  `writeControl.targetRevisionId`; values.update is LWW.
- No external-modification warning surfaces to the operator;
  collaboration is OT-merged in real time.
- The cleanest design partitions cells into app-owned and
  operator-owned ranges; allowing operator edits to formula cells
  requires retry loops and an operator-pause signal.

[d1]: https://workspace.google.com/resources/real-time-editing/
[d2]: https://www.quora.com/What-happens-when-two-people-offline-edit-Google-spreadsheet-simultaneously
[d3]: https://www.thebricks.com/resources/guide-how-to-stop-overwriting-in-google-sheets
[d4]: https://support.google.com/docs/answer/1218656
[d5]: https://developers.google.com/workspace/drive/api/guides/push
[d6]: https://developers.google.com/workspace/drive/api/reference/rest/v2/changes/watch
[d7]: https://github.com/googleapis/google-api-go-client/issues/444
[d8]: https://medium.com/swlh/google-drive-push-notification-b62e2e2b3df4
[d9]: https://www.labnol.org/google-drive-push-notifications-230826
[d10]: https://developers.google.com/workspace/drive/api/guides/change-overview
[d11]: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions/list
[d12]: https://issuetracker.google.com/issues/205023847
[d13]: https://googleapis.dev/java/google-api-services-sheets/v4-rev20210527-1.31.0/com/google/api/services/sheets/v4/Sheets.Spreadsheets.BatchUpdate.html
[d14]: https://en.wikipedia.org/wiki/HTTP_ETag
[d15]: https://event-driven.io/en/how_to_use_etag_header_for_optimistic_concurrency/
[d16]: https://fideloper.com/etags-and-optimistic-concurrency-control
[d17]: https://developers.google.com/workspace/drive/api/reference/rest/v3/revisions
[d18]: https://developers.google.com/workspace/sheets/api/guides/values

## Cross-stream synthesis (for the ADR phase)

The four streams converge on a single tractable design space:

- **Parity is exact after per-casilla `ROUND(_, 2)`, not bit-
  exact.** This is forced by binary64 vs Decimal and is consistent
  with how the AEAT itself rounds. The ADR must declare this
  explicitly.
- **No prior-art system implements the full proposed contract.**
  QBO Spreadsheet Sync is the closest mental model; its sync is
  explicit and manual. The ADR must choose how implicit the sync
  is.
- **Differential testing tiered as `formulas` (fast) plus
  LibreOffice headless (nightly) plus live Sheets (release gate)
  is the workable parity-verification stack.** No single oracle
  suffices.
- **Optimistic concurrency via batchUpdate `writeControl` is
  available; values.update is LWW.** Cell partitioning is the
  cleanest sidestep; allowing operator edits to formula cells
  forces the 412-retry regime and needs an operator-pause signal.
