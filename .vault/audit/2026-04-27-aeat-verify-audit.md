---
tags:
  - '#audit'
  - '#aeat-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-26-aeat-verify-audit]]"
  - "[[2026-04-25-aeat-verify-plan]]"
  - "[[2026-04-25-pdf-sanitizer-plan]]"
  - "[[2026-04-25-pdf-sanitizer-adr]]"
---



# `aeat-verify` audit: `post-pdf-sanitizer-completion-state`

## Scope

Audit the state of the `aeat-verify` feature after the
continuous-execution session that landed the
`pdf-sanitizer` sub-feature, the declaraciones-register read
backend, and the first 15 sanitised fixtures. Captures what is
runnable end-to-end, what tests / gates protect each surface, and
what remains operator-gated or scoped to a follow-up.

## Findings

### Read backend — fully shipped

Two AEAT sede surfaces are now driven by typed, tested,
read-only Python code:

- `aeat.adapters.outbound.aeat.sede.walk_expedientes_tree(session, *, modelo)` — walks
  *Mis Expedientes* at `/wlpl/TEWV-CORE/ResumenVlt`. Returns
  `Expediente` records. **This surface holds procedures**
  (sanciones, recursos, gestión recaudación, plus the per-year
  IRPF detail entries) — not declarations.
- `aeat.adapters.outbound.aeat.sede.walk_declarations_register(session, *, modelo,
  ejercicio)` — drives the ZK form at `/wlpl/SCEJ-MANT/CONSUL/
  index.zul` ("Consultar declaraciones presentadas"). Returns
  `Declaration` records. **This surface holds Kent's actual
  filing register** — the routine quarterly/annual modelos that
  the expediente tree omits.

Cross-wave P1 enumeration against the authenticated operator account, fully
resolved:

| Wave | Modelo | Status | Captured |
|------|--------|--------|----------|
| W1 | 100 (IRPF anual) | confirmed | 2021-2023 (3 filings) |
| W2 | 130 (IRPF fraccionado) | confirmed | 2021-2024 (15 filings) |
| W3 | 303 (IVA quarterly) | confirmed | 2021-2024 (17 filings) |
| W4 | 390 (IVA anual) | confirmed | 2021-2023 (3 filings) |
| W5 | 111 (retenciones quarterly) | confirmed | 2024 (4 filings) |
| W6 | 190 (retenciones anual) | confirmed | 2024 (1 filing) |
| W7 | 115/180 (inmuebles ret.) | na | zero rows |
| W8 | 123/193 (capital mob. ret.) | na | zero rows |
| W9 | 131/202/200 (sociedades) | na | per user confirmation |
| W10 | 347 (operaciones terceros) | na | zero rows |
| W11 | 369/720/232/840 (niche) | na | per user confirmation |

Total live captures under `scratch/declarations-corpus/` — 49
PDFs spanning Modelos 100/111/130/190/303/390 across ejercicios
2021-2024. Every single one parses through
`aeat.domain.justificante.parse_justificante` to a valid `Justificante`
record (modelo, period, tax_id, csv, presented_at). Mix of
Spanish + English receipts, modern + legacy 2021 layouts.

### Sanitiser — fully shipped

The `pdf-sanitizer` sub-feature is end-to-end production-ready:

- `aeat.adapters.inbound.sanitizer` subpackage with strict-frozen pydantic v2
  records, the 8-step order-of-operations pipeline, refuse-if-
  signed + refuse-if-already-sanitised guards, and deterministic
  byte-stable output.
- `aeat sanitize` CLI bridge with four verbs (`pdf`,
  `prepare-map`, `verify`, `check`).
- `prepare-map` auto-detects 28-35 PII surfaces per Modelo 100
  declaration (NIF + CSV + name + 28 IMPORTE values + dates +
  catastral references + NRC tokens). Operator now only fills
  the taxpayer name; everything else is auto-detected.
- `verify` masks synthetic values from the byte streams before
  searching for real values, defending against substring false
  positives (a real `0,00` would otherwise falsely match the
  synthetic `1.000,00` containing it).

15 sanitised fixtures committed under
`tests/fixtures/justificantes/`:

| Modelo | Year | Periods | Count |
|--------|------|---------|-------|
| 100 | 2022 | 0A | 1 |
| 111 | 2024 | 1T-4T | 4 |
| 130 | 2024 | 1T-4T | 4 |
| 190 | 2024 | 0A | 1 |
| 303 | 2024 | 1T-4T | 4 |
| 390 | 2023 | 0A | 1 |

Every fixture is verify-clean across its mapping, parses
through `parse_justificante` to a valid record, and its SHA-256
is recorded in `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS` so
re-sanitisation fails fast with `AlreadySanitizedError`.

### Test coverage — production-ready

| Surface | Tests | Coverage |
|---------|-------|----------|
| `aeat.adapters.inbound.sanitizer.*` (8 modules) | 91 unit tests | records, determinism, metadata, dynamic, streams, pipeline, no-write-surface |
| `aeat.entrypoints.cli.sanitize` | 34 unit tests | forbidden flags, prepare-map auto-detect (10 tests), verify masking, all 4 verbs |
| `aeat.adapters.outbound.aeat.sede._declarations` | 6 offline tests | listbox parser, presented_at, error paths |
| `aeat.domain.justificante._extract` | inline-shape tests | Spanish + English layouts, positional period, inverted NIF, loose ejercicio |
| Fixture-bound security | 62 tests | adversarial-absence + round-trip across all 15 fixtures |

Total: ~680 unit tests pass project-wide. Lint + ty clean.

### Live-AEAT-write safety — preserved

Every new module honours the parent ADR's 5-layer write guard:

- Layer 1 (`mode: Literal["read"]`): `Declaration` carries the
  marker. `SanitizationResult` is a transformation record (not
  a boundary), so the marker is N/A but `frozen=True` /
  `extra="forbid"` discipline holds.
- Layer 2 (no submission verbs): `aeat sanitize` CLI's
  `_FORBIDDEN_FLAGS` rejects 13 mutation-implying tokens before
  Typer dispatch. Per-subpackage `test_no_write_surface.py`
  greps for forbidden verbs in public symbol names.
- Layer 3 (write-surface tests): present in `aeat.adapters.inbound.sanitizer`
  and `aeat.adapters.outbound.aeat.sede` (existing).
- Layer 4 (`AeatAccessGate`): inherited unchanged from
  `aeat.adapters.outbound.aeat.auth`.
- Layer 5 (`AEAT_LIVE_TESTS_ENABLED`): inherited unchanged.
  No new live tests were added in this round; the live walker
  test is queued as a follow-up.

## Recommendations

### Immediate next steps (in order of leverage)

1. **Per-modelo deep extractors** (`aeat.adapters.inbound.declaracion._parsers/
   {130,303,390,111,190}/`). Each modelo's casilla map needs a
   typed extractor like the existing `modelo_100`. This is the
   gating step for aggregator cumulation tests. Estimated
   effort: 1 person-day per modelo for the simple ones (130,
   111), 2-3 days for the aggregators (390, 190) which need
   cross-period summation logic.

2. **Aggregator cumulation tests**. Once per-modelo extractors
   exist: assert `M390/2023 = sum(M303/2023/{1T,2T,3T,4T})`
   within `Decimal("0.01")` tolerance; same for `M190/2024 ←
   M111/2024 quarterly`; and `M100/2023 ← M130 + M111 + M115 +
   M123` (for years where Kent withholds). The 15-fixture corpus
   already has all the quarterly inputs.

3. ~~**W1 P7 — live reconcile dry-run**. Build
   `aeat.domain.testing.synthesize_filing_draft(modelo, casilla_map)`,
   instantiate an APPROVED `FilingDraft` from the M100/2022
   sanitised fixture's casilla map, run `aeat filing reconcile
   --modelo 100 --period 0A --ejercicio 2022` against the live
   AEAT, assert MATCH.~~ **Offline portion shipped** in commits
   `c309602` (`synthesize_filing_draft` helper + 15 unit tests)
   and `dd8e8c4` (10 dry-run tests parametrised across the
   committed corpus: 8 MATCH, 1 DIVERGENT, 1 NOT_YET_FOUND).
   Live AEAT version still requires a fresh Cl@ve session and
   moves to follow-up #5 below.

### Longer follow-ups

4. ~~**Capture the older years' sanitised fixtures**. The 49-PDF
   live corpus under `scratch/declarations-corpus/` has 34
   uncommitted PDFs (M100/2021, M100/2023, M130/2021-2023,
   M303/2021-2023, M390/2021-2022, plus M303/2024
   complementarias). Each can be sanitised + committed via the
   same prepare-map → pdf → verify → check pipeline. Likely
   1-2 hours of operator time.~~ **Done** in commit `c69a570`
   (25 fixtures: M100/2021+2023, M130/2021+2022+2023 full year,
   M303/2021+2022+2023 full year, M390/2021+2022). All passed
   the prepare-map → pdf → verify → check pipeline; SHAs
   registered in `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS`.

5. **Live walker tests** (gated by
   `AEAT_LIVE_TESTS_ENABLED=1`). Exercise
   `walk_declarations_register`, `capture_declaration`, and
   `aeat filing reconcile --modelo 100 --ejercicio 2022 --period 0A`
   against AEAT in CI when the env var is set.

6. **Independent code review** — vaultspec-code-reviewer
   already reviewed an earlier iteration with a PASS. Worth
   a fresh pass after the declaraciones-register backend +
   prepare-map auto-detect landed.

## Open issues / known limitations

- ~~**Annual modelos (M100/M390/M190) fall back to ejercicio**
  as the period when no labelled token exists. Schema accepts
  this; semantically `0A` would be cleaner. Tracked as a parser
  follow-up.~~ Resolved in commit `23d92e0`: annual modelos
  now synthesise canonical `0A` via `_ANNUAL_MODELOS` set.
- **`prepare-map` IMPORTE auto-detection misses values** that
  span across pdfplumber line breaks. Not observed on the
  current corpus but possible for very wide tables. Operator
  reviews the YAML before sanitising.
- **Pre-existing `aeat.adapters.outbound.aeat.auth` test failures** (5 tests in
  `test_clave_movil.py`) are out of pdf-sanitizer scope. The
  failures were re-confirmed in this session: the tests are
  marked `@pytest.mark.unit` but `fake_session_login` fixture
  triggers a real Cl@ve flow that times out after 5 min on the
  2FA push. Fix requires substantive auth-subsystem rework;
  tracked separately. Full-unit runs need
  `--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` until then. The
  marker-integrity regression PR #427 introduced was fixed in
  commit `6b494d7`.
- **49-PDF corpus contains real PII** under `scratch/`
  (gitignored). Operator should treat the directory as
  non-shareable.

## Round-2 code review (2026-04-27)

The vaultspec-code-reviewer ran round-2 against the
declaraciones-register backend + parser hardening + sanitizer
prepare-map auto-detect + verify masking. Verdict: REVISION
REQUIRED with 1 HIGH, 5 MEDIUM, 3 LOW. All HIGH/MEDIUM/L1
resolved in commit `e319d38`:

- **H1**: `_PERIOD_POSITIONAL_RE` over-matched M190 casilla
  numbers (the `0[1-9]|1[0-2]` monthly alternation matched
  `Ejercicio (con 4 cifras) ....... 2024 01 enero`,
  mislabelling annual filings as monthly period `01`).
  Tightened to `0A|[1-4]T` only.
- **M3**: `capture_declaration` now explicitly checks the
  cotejo-redirect URL against the canonical
  `/wlpl/KATA-APLI/cotejo/CotejoIdSv` prefix and raises a clear
  session-expired error.
- **M4**: `_extract_csv_from_url` validates the CSV against
  `^[A-Z0-9]{8,24}$` (mirror of `_CSV_LABEL_RE`).
- **M2**: `aeat sede capture-corpus` gained `--delay-seconds`
  pacing (default 1.0s) and broadened per-iter exception
  handling so a single Playwright timeout doesn't kill the
  loop.
- **M1**: `test_no_write_surface.py` docstring no longer
  claims `.click(`/`.submit(` coverage; it explicitly notes
  Playwright primitives are out-of-scope (legitimate read-
  event dispatch).
- **L1**: `bs4.BeautifulSoup` lifted from function scope to
  module top.

Three D-flagged items (D1 per-query browser context, D2
multi-CSV suspicion, D3 `0A` annual fallback) were initially
documented as follow-ups (defensible as-is per the reviewer)
and have since all landed:

- **D3** — canonical `0A` annual period synthesis when no
  labelled or positional period appears for an annual modelo.
  Commit `23d92e0`. Regression tests in
  `src/aeat/domain/justificante/test_extract_modelos.py:215-229`
  for M190 and M390 layouts.
- **D2** — `_extract_csv_from_url` rejects cotejo URLs
  carrying multiple `CSV` query values rather than silently
  picking the first. Commit `daba8d3`. Regression test
  `test_multiple_csv_values_rejected` in
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/test_declarations.py:131-135`.
- **D1** — Playwright bringup deduplicated into a single
  `_open_register_page` `asynccontextmanager` shared by
  `walk_declarations_register` and `capture_declaration`.
  Side-effect bug fix: the walker previously did not call
  `BrowserSession.close()`, leaking the retained browser
  handle. Commit `1e5f496`. All 42 sede unit tests stay
  green.

### Round-3 verification (2026-04-27)

vaultspec-code-reviewer round-3 verified the round-2 fixes
resolve every flagged finding at the precise file/line
locations claimed in the commit message. Verdict: **PASS**.
Regression tests cover every fix where the round-2 review
demanded them. The explicitly out-of-scope DISAGREE items
remain open as documented.

### Round-4 verification (post-D-item follow-ups)

vaultspec-code-reviewer round-4 reviewed the five follow-up
commits that landed after the round-3 PASS:
- `daba8d3` (multi-CSV rejection)
- `1e5f496` (single-context-manager refactor)
- `45b9188` (audit refresh)
- `2eb0f1e` (sede docstring refresh)
- `f79f0c6` (cli/sede docstring refresh)

Verdict: **PASS**. No CRITICAL / HIGH findings. Independent
verification confirmed:

- Multi-CSV check correctly fires before the shape regex.
- The leak-fix claim for `BrowserSession.close()` is real:
  `BrowserSession._close_browser_locked()` is the load-bearing
  step that releases the retained Chromium handle.
- Cleanup ordering (`context.close()` → `browser_session.close()`)
  is correct per Playwright lifecycle requirements.
- Public signatures of `walk_declarations_register` /
  `capture_declaration` unchanged.
- Sede docstring lists exactly the 24 names in `__all__`;
  cli/sede docstring lists exactly the 6 names in the
  `@app.command(...)` registry.
- Multi-CSV edge cases (empty trailing value, percent-encoded
  ampersand) are correctly rejected by the existing chain
  without further regression tests.

The reviewer DISAGREED on adding a direct unit test for
`_open_register_page` — would require mock/patch of
`async_playwright` (forbidden) or live Playwright, and the
helper is already exhaustively exercised through live and
unit tests on `walk_declarations_register` / `capture_declaration`.
A direct unit test would be tautological.

### Full unit suite (2026-04-27)

`uv run --no-sync pytest -m unit -q --tb=no
--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` →
**3186 passed, 9 skipped, 0 failed**, 90.5s wall.

The `--ignore` clause excludes the pre-existing auth tests
documented above; without it, those 5 tests would each spend
~5 minutes timing out on a real Cl@ve push and dominate the
wall time. With the auth tests, the suite is `3186 passed,
9 skipped, 5 failed` and runs ~22 min — the failing 5 are
unrelated to this feature's surface and have been confirmed
out of scope twice in this session.

## Aggregator cumulation testing — design challenge

The 15-fixture corpus has a complete year of M130 / M303 /
M111 quarterly inputs and matching anuales (M390/M190). Naive
cumulation tests of the form
`assert sum(M303_quarterly_cuotas) == M390_anual` would,
however, be **structurally trivial** because every sanitised
fixture carries `1.000,00` for every IMPORTE. The sum
`1.000,00 × 4 = 4.000,00` would never equal `1.000,00`, so the
test would always fail; or if both sides used the same
synthetic, the test would always pass regardless of correctness.

For meaningful aggregator cumulation testing, one of:

- **Per-fixture synthetic mapping that preserves the
  cumulation invariant.** Each casilla in M303/Q1 gets a
  unique synthetic; the M390 anual fixture's casillas use
  pre-computed sums of those synthetics. The mapping
  generator becomes load-bearing on the test's mathematical
  validity.
- **Live-test cumulation** against `scratch/declarations-corpus/`
  unsanitised PDFs, gated by `AEAT_LIVE_TESTS_ENABLED=1` and
  contributor-local. Runs on the operator's box, not in CI.
- **Synthetic test fixtures with hand-crafted casilla maps**
  whose values cumulate by construction. Uses
  `aeat.application.filing.testing` patterns rather than real captures.

This is the gating design decision before per-modelo deep
extractors are worth building in scope; recorded here so the
follow-up PR can pick a path explicitly rather than discovering
the constraint mid-implementation.

## Round-5: corpus extension + parser fix + W1 P7 offline closure

This wave drove three previously-blocking follow-ups to completion
in a single autonomous pass with no AEAT round-trip.

### Corpus extension (commit `c69a570` + `6bbf76c`)

Sanitised 25 additional capture PDFs through the existing
prepare-map → pdf → verify → check pipeline:

- **M100**: 2021, 2023 (joining 2022)
- **M130**: 2021 Q2-Q4, 2022 Q1-Q4, 2023 Q1-Q4
- **M303**: 2021 Q2-Q4, 2022 Q1-Q4, 2023 Q1-Q4
- **M390**: 2021, 2022 (joining 2023)

Total committed corpus is now 40 sanitised justificantes
spanning 4 modelos × 4 years (2021-2024). Every fixture passed
verify (zero leaks against the per-capture mapping) and check
(parse_justificante binds modelo/period/csv/tax_id correctly).

### Parser fix: positional year promoted to ejercicio

The corpus regression test `TestRealCorpusParses` (commit
`6bbf76c`, 41 parametrised tests walking every committed
fixture) surfaced a real parser bug: pre-2024 quarterly
modelos (M130 2021-2023) print only the positional
``Y0000001S 2022 4T`` line with no labelled "Ejercicio 2022"
anywhere. The parser's ejercicio extraction relied on
label-bound regexes only, so `record.ejercicio` came back
`None` for those layouts. Fixed by promoting
`_PERIOD_POSITIONAL_RE.group("year")` to ejercicio when the
labelled extractors found nothing. 11 M130 fixtures
re-generated with year-embedded synthetic CSVs to match the
new shape. SHAs updated in `aeat.adapters.inbound.sanitizer.fixtures`.

### W1 P7 offline portion (commits `c309602` + `dd8e8c4`)

- **`aeat.domain.testing.synthesize_filing_draft`** — strict-frozen
  FilingDraft factory taking a casilla map. Default status
  APPROVED so the result is immediately ready for
  `aeat filing reconcile`. Companion
  `synthesize_filing_draft_from_decimals` coerces decimal-as-string
  values at the boundary. 15 unit tests cover every invariant
  (frozen, draft_id determinism, status propagation, approved_by
  provenance, decimal coercion).
- **End-to-end dry-run** — `TestLiveReconcileDryRun` parametrises
  10 cases across the corpus: 8 MATCH (M100/2021-2023, M130/2024
  1T+4T, M303/2024 1T+4T, M390/2023), 1 DIVERGENT (modelo
  mismatch), 1 NOT_YET_FOUND (justificante=None). Each MATCH
  case asserts the trilingual narrative is populated. Pure
  offline — never reaches AEAT.

### Read-only mandate honoured

Every commit in this wave is local-only: PDF sanitisation reads
files and writes files. The reconcile dry-run reads files and
runs pure-construction helpers. Zero AEAT requests in any path.
The five-layer write guard (mode marker, no-write verbs,
no-write-surface tests, AeatAccessGate, AEAT_LIVE_TESTS_ENABLED)
remains intact.

### Round-5 independent review verdict (post-corpus extension)

`vaultspec-code-reviewer` round-5 verified all five corpus-wave
commits (`c69a570`, `6bbf76c`, `c309602`, `dd8e8c4`, `c9093c4`).
Verdict: **PASS**. No CRITICAL / HIGH findings. Two LOW
informational items addressed in commit `b208793` (decimal
boundary comment polish + late-import hoisting in reconcile
dry-run tests). Independent verification confirmed:

- 1,459 PII replacement records across 44 sidecars; zero
  cleartext `real:` keys (privacy-preserving `real_sha256`
  only).
- Parser fix is a single-line minimal change at
  `src/aeat/domain/justificante/_extract.py:367-368`.
- All 11 M130 SHAs genuinely re-sanitised (differ from
  `c69a570` baseline).
- `synthesize_filing_draft` has zero HTTP imports and zero
  forbidden verbs.
- 28/28 no-write-surface guards remain green on
  `aeat.adapters.outbound.aeat.sede` and `aeat.application.filing.reconciliation`.

### Full unit suite (round-5)

`uv run --no-sync pytest -m unit --ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py
-q --tb=no` → **3505 passed, 9 skipped, 0 failed**, 135.5s wall.

That's +319 over the round-4 baseline (3186 → 3505): 41 corpus
regression tests + 15 synthesize_filing_draft tests + 10
reconcile dry-run tests + 4 _synthesise_csv_for tests + 1
live capture_declaration test + miscellaneous from the
focused-scope additions.

### Live AEAT verification (round-5, with operator-approved Cl@ve)

Operator approved a Cl@ve Móvil 2FA push (third attempt — first
two timed out at the post-auth-landing step). With the fresh
session, every Kent-observable triad branch was driven against
the live AEAT sede. **All read-only**: every request was a GET
or a ZK form drive that fetches state, never POSTs / submits.

- **Live walker tests** — `pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/test_declarations_live.py
  -m live_read` with `AEAT_LIVE_TESTS_ENABLED=1`:
  - `test_walk_modelo_100_returns_at_least_one_declaration` PASSED
  - `test_capture_declaration_returns_pdf_bytes` PASSED — fetched
    a real `%PDF-` body via APIRequestContext (read-only GET to
    `/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=...`)

- **Live reconcile, MATCH path** — synthesised an APPROVED
  `FilingDraft` for M100/2022/0A via `synthesize_filing_draft`,
  persisted to `var/drafts/`, ran
  `aeat filing reconcile --last --modelo 100 --period 0A --ejercicio 2022 --json`.
  Verdict: `status: match`, zero mismatches.
  Live justificante: `csv=MZRSYDRL5JMPJPRT`,
  `presentation_id=1004231535072`, `total_a_ingresar=549.52`,
  `presented_at=2024-02-01T19:15:34`. Hungarian narrative rendered
  cleanly after the cp1252 fix below.

- **Live reconcile, NOT_YET_FOUND path** — synthesised an
  M100/2025/0A draft (current year, not yet filed), reconciled
  against AEAT. Verdict: `status: not_yet_found`, one
  `filing_not_yet_found` mismatch surfaced. Spanish narrative:
  "AEAT no tiene constancia del modelo 100 del período 0A."

- **Live reconcile, DIVERGENT path** — synthesised an
  M100/2022/0A draft with `profile_tax_id="X9999999Z"` (wrong
  NIE), reconciled against AEAT's real record. Verdict:
  `status: divergent`, `tax_id_mismatch` surfaces:
  draft=X9999999Z vs AEAT=<redacted operator NIE>.

This closes the Kent-observable acceptance criteria for #239:
> "`aeat filing reconcile <draft-id>` returns MATCH 30 minutes
> post-upload."
> "`aeat filing reconcile` returns NOT_YET_FOUND with prominent
> warning when AEAT has no record."

### Live-driven CLI fix: cp1252 JSON encoding (commit `431bb5c`)

`aeat filing reconcile ... --json` initially crashed with
`UnicodeEncodeError` on the Hungarian "ő" (U+0151) in the
trilingual narrative. Root cause: `typer.echo` →
`click.echo` re-encodes through `sys.stdout`'s locale codec,
which on Windows defaults to cp1252 (no Latin Extended-A
coverage). Fix: write the rendered JSON byte stream directly
to `sys.stdout.buffer` in UTF-8, bypassing the codec. The CLI
output is now a valid UTF-8 stream regardless of shell.

This is a real bug surfaced ONLY by the live run — the offline
test suite uses `typer.testing.CliRunner` which bypasses the
real stdout codec.

### Live-driven CLI fix: declarations-register fallback (commit `8509aa5`)

`aeat filing reconcile --last --modelo 130 --period 4T` returned
NOT_YET_FOUND despite AEAT having the M130/4T filing on record.
Root cause: `_run_reconcile` used only `find_expediente` from
`aeat.adapters.outbound.aeat.sede._walker`, which traverses Mis Expedientes (the
procedure tree). Quarterly modelos (M130, M303, M111, ...)
typically do NOT appear there — their authoritative record
lives in *Consultar declaraciones presentadas*.

Fix: extracted `_capture_for_filing(...)` that tries the
procedure tree first (same as before), and on
`ExpedienteNotFoundError` falls back to
`walk_declarations_register` + `capture_declaration` (the new
walker added in this PR). Both paths produce a `SedeCapture`
so the downstream parse_justificante + reconcile flow is
unchanged.

Confirmed live: M130/2024/4T → MATCH (CSV `HFZPAVR85USDNPM2`,
presented 2025-03-26 18:46:30) after the fix; M130/2025/1T
correctly returns NOT_YET_FOUND through the same fallback path.

### Live-driven fix: sanitizer error registry (commit `c4521f4`)

`aeat filing reconcile` (any invocation) crashed at startup with
`ValueError: AeatError subclass aeat.adapters.inbound.sanitizer._errors.SanitizationError
is missing a declared ErrorCode registry entry`. Root cause: the
AeatError base class enforces an `__init_subclass__` hook that
resolves every subclass against the ErrorCode registry, but the
five sanitizer error classes were never added when
`aeat.adapters.inbound.sanitizer` landed. The crash only fires on the CLI path
because `aeat.entrypoints.cli.__init__` imports `aeat.entrypoints.cli.sanitize` →
`aeat.adapters.inbound.sanitizer`, triggering subclass registration. Unit tests
that import `aeat.adapters.inbound.sanitizer` directly succeed because the
import order is different.

Added 5 registry entries (alphabetical between aeat.adapters.outbound.aeat.sede and
aeat.application.setup): AlreadySanitizedError, SanitizationError,
SanitizerSourceParseError, SignaturePresentError,
UnknownSurfaceError. Each carries trilingual default messages.

### Live verification matrix (round-5)

After the three live-driven fixes above, every reachable path
through `aeat filing reconcile` has been confirmed end-to-end
against the live AEAT sede:

| Modelo | Period | Year | Verdict        | Path | CSV               |
|--------|--------|------|----------------|------|-------------------|
| 100    | 0A     | 2022 | MATCH          | tree | MZRSYDRL5JMPJPRT  |
| 100    | 0A     | 2025 | NOT_YET_FOUND  | tree | (no record)       |
| 100    | 0A     | 2022 | DIVERGENT*     | tree | MZRSYDRL5JMPJPRT  |
| 130    | 4T     | 2024 | MATCH          | reg  | HFZPAVR85USDNPM2  |
| 130    | 1T     | 2025 | NOT_YET_FOUND  | reg  | (no record)       |
| 303    | 4T     | 2024 | MATCH          | reg  | LFXDUFRGA8388AKX  |
| 111    | 4T     | 2024 | MATCH          | reg  | ZF45RSV655G4STJD  |
| 390    | 0A     | 2023 | MATCH          | tree | 7PMVLB5GXHG2L2MU  |

\* DIVERGENT case used profile_tax_id="X9999999Z" (wrong NIE).

Path key: `tree` = procedure-tree walker; `reg` =
declarations-presentadas register fallback.

Five-layer write guard intact across every live invocation: every
AEAT touch was a GET (cotejo PDF, expedientes tree HTML) or a
ZK form drive that fetches state. Zero writes to authenticated
AEAT state.
