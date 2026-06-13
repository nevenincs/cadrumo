---
tags:
  - '#audit'
  - '#security-swarm-2026-05-30'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-security-swarm-2026-05-30-audit]]"
  - "[[2026-05-30-security-crypto-swarm-2026-05-30-audit]]"
  - "[[2026-05-30-security-supply-chain-2026-05-30-audit]]"
---

# security swarm — axis 3: input validation and deserialization

Read-only audit of every external input boundary in `src/aeat/`. Scope per dispatch brief:
inbound financial providers (CSV / XLSX / OFX / PDF), declaracion / borrador / justificante PDFs,
registry TOML loaders, JSON envelopes, MCP / CLI inputs, Google Sheets pulls, AEAT export
parsing. Methodology: ripgrep sweep of canonical dangerous sinks; targeted read of every
boundary that decodes attacker-controllable bytes.

## summary of the dangerous-sink sweep

The good news up front, so the high-severity findings below can be read in context:

- `pickle.loads`, `marshal.loads`, `yaml.load` (any form), `eval(`, `exec(` of dynamic
  input — **zero hits in production code**. The only ripgrep matches were regex string
  literals (`re.compile(...)`) and pytest internals.
- XML parsing under `src/aeat/domain/calculations/registry/_export_parse.py` imports
  `defusedxml.ElementTree` rather than stdlib `xml.etree`; `xml.etree.ElementTree.Element`
  is imported only as a type alias. No `xml.dom`, `xml.sax`, or `lxml.etree` usage.
- All TOML parsing uses stdlib `tomllib` (safe parser; no executable nodes).
- Every JSON deserialization boundary I inspected wraps the parsed payload in a strict
  pydantic v2 model (`model_validate_json` or `Model.model_validate(json.loads(...))`)
  before propagating it. The encrypted-column codec (`adapters/persistence/storage/crypto/_encrypted_columns.py:200-201`)
  is the one place that returns `json.loads(...)` straight to a caller, but the ciphertext
  is AEAD-authenticated and master-key-bound — the JSON only decodes after a successful
  AES-GCM tag verification, so external attackers cannot reach the `json.loads` sink.

The findings below are everything I could turn up that warrants a structural fix or a
defence-in-depth note.

## findings

### F1 — Financial providers read entire source files with no size cap (HIGH — DoS)

- File:line: `src/aeat/adapters/inbound/financial/providers/_base.py:245-253`
  (`FinancialProvider._read_source_bytes`)
- Attack surface: every concrete provider (`CsvProvider`, `XlsxProvider`, `OfxProvider`,
  `PdfN26Provider`) calls `_read_source_bytes` which executes `resolved.read_bytes()` on
  the operator-supplied path with no max-bytes check, no streaming, and no pre-flight
  `stat().st_size` comparison against a configured ceiling.
- Concrete consequences:
  - A multi-GB "CSV" can exhaust process memory before any layout sniff happens.
  - `_csv.py:299` then expands `rows = [[cell.strip() for cell in row] for row in reader]`
    into a fully materialised `list[list[str]]` — second memory amplification.
  - `_xlsx.py:253` uses `read_only=True` which streams cells, but the source bytes have
    already been pinned. An XLSX zip-bomb (small file, ~GB inflated content) is still a
    distinct vector — openpyxl does not enforce inflation ratio limits.
  - PDF path (`_pdf_n26.py:189`) hands the full bytes to `pdfplumber.open(str(path))`;
    pdfplumber-on-pdfminer has historical CVE history around malformed object streams.
- Remediation: introduce a `financial_max_source_bytes` Settings field (default e.g.
  64 MiB), check `resolved.stat().st_size` in `_read_source_bytes` before the
  `read_bytes()` call, raise `InvalidFinancialSourceError` with a translated message on
  overrun. Add a per-provider data-row cap (e.g. 250 000 rows) honoured by `_csv.py`,
  `_xlsx.py`, and `_ofx.py`. For XLSX consider validating the central-directory total
  uncompressed size before `load_workbook`.

### F2 — `csv.Sniffer().sniff` on attacker-controlled CSV text (MEDIUM — parser DoS)

- File:line: `src/aeat/adapters/inbound/financial/providers/_csv.py:323-329`
- Attack surface: every CSV the operator imports passes through `csv.Sniffer().sniff` on
  a 4 KiB sample. `csv.Sniffer` has documented CPython issues with pathological inputs
  (CVE-2024-12254-class regressions have surfaced periodically). The 4 KiB cap helps but
  the sniffer still tries many delimiter combinations.
- Remediation: the cap is sensible; add a defensive `try/except csv.Error` (already
  present) and consider running the sniff in a thread with a short timeout, or skipping
  the sniffer entirely when an upstream layout match has already succeeded with
  `csv.excel`. Low fix priority but worth a defence-in-depth note.

### F3 — `Decimal(str)` accepts scientific notation and Decimal-special values from operator CSVs (MEDIUM)

- File:line: `src/aeat/adapters/inbound/financial/providers/_base.py:408`
  (`parse_amount_value` → `Decimal(normalized)`) and
  `src/aeat/adapters/inbound/pdf/_label_regex.py:93`
  (`parse_spanish_decimal` → `Decimal(cleaned)`).
- Attack surface: a malicious CSV that survives the layout match but smuggles
  `"NaN"`, `"sNaN"`, `"Infinity"`, or `"1E1000"` into the amount column will produce a
  Decimal whose value flows into ledger aggregation, IVA reconciliation, and persisted
  bank-event projections. `Decimal("NaN")` propagates through arithmetic without raising;
  every subsequent comparison silently returns False; `Decimal("1E1000")` consumes
  unbounded memory in `quantize`.
- Concrete consequences: poisoning the bank ledger with `NaN` causes downstream verifier
  predicates (`all_nonzero`, `any_nonzero` in `application/modelo/_actions.py:2342-2380`)
  to evaluate incorrectly; exporters round-trip the value as `"NaN"` literal.
- Remediation: in `parse_amount_value`, after `Decimal(normalized)`, reject
  `amount.is_nan() or amount.is_infinite()` and bound `abs(amount) < MAX_AMOUNT`
  (a settings-configurable Decimal, e.g. `Decimal("1e15")`). Same in
  `parse_spanish_decimal`. The `decimal` module's `localcontext` with `traps={InvalidOperation}`
  is the canonical pattern.

### F4 — `parse_amount_value(float)` re-stringifies floats and re-parses them (LOW — float coercion regression)

- File:line: `src/aeat/adapters/inbound/financial/providers/_base.py:394-398`
- Attack surface: XLSX cells often arrive as `float` (openpyxl reads numeric cells as
  `float`). `coerce_decimal(value)` is called for the float path; its implementation
  ultimately formats the float with `repr()` which leaks IEEE-754 imprecision into the
  bank ledger (1234.56 → 1234.5599999...).
- Remediation: configure `openpyxl.load_workbook(..., data_only=True)` is already in
  use; additionally request `number_format` reads or force cells through
  `cell.value` as `str` for the amount column when the layout column type is known.
  Document the float path as a defence-in-depth gap and assert no float arrives in
  `parse_amount_value` for layouts whose decimal_separator is `","`.

### F5 — `pydantic ConfigDict(extra="allow")` on auth-diagnostic and master-key envelopes (MEDIUM — boundary leak)

- File:lines:
  - `src/aeat/application/auth/_diagnostics.py:105` (`_DiagnosticPayload`)
  - `src/aeat/adapters/persistence/storage/master_key/_master_key.py:93`, `102`, `116`, `216`
  - `src/aeat/application/workflow/_models.py:400` (run-record diagnostics)
- Attack surface: these models load attacker-influenced JSON (auth diagnostics blob,
  master-key custody records, workflow run logs) yet accept arbitrary extra fields
  silently. While the explicit pydantic fields are typed, `extra="allow"` defeats the
  vault rule that boundaries reject unknown payload shapes.
- Concrete consequences: a tampered diagnostic JSON cannot inject typed fields, but it
  can store unbounded extra string blobs that downstream code might serialise back into
  the encrypted-column store, causing storage amplification and obscuring tampering.
  Project rule `aeat-architecture-boundaries` mandates strict pydantic at boundaries.
- Remediation: switch `extra="allow"` to `extra="forbid"` on all five sites; for
  `_DiagnosticPayload` add explicit optional fields for any historical extras instead
  of a wildcard allowance. The accompanying tests in
  `application/workflow/test_run_persistence_roundtrip.py:92` make the contract switch
  visible.

### F6 — N26 PDF regex `_ROW_RE` uses non-greedy `.+?` with backtracking risk (LOW)

- File:line: `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py:54-56`
  `^(?P<narrative>.+?) (?P<booked_date>\d{2}\.\d{2}\.\d{4}) (?P<amount>[+-][\d\.,]+)EUR$`
- Attack surface: a maliciously crafted "N26 PDF" with thousands of digits and dots in
  the amount column on a single line could amplify backtracking inside the
  `[+-][\d\.,]+` group via the trailing `EUR$` anchor. Each line is bounded by the PDF
  parser, so realistic exploitation is limited, but a pathological PDF could
  burn meaningful CPU per line.
- Remediation: anchor amount more tightly (`[+-]\d{1,3}(?:[.  ]\d{3})*,\d{2}EUR$`)
  to match the Spanish-amount discipline already used in `_label_regex.SPANISH_AMOUNT_GROUP`.
  Bound `.+?` length with `.{1,200}?` or `[^\d]{1,200}?`.

### F7 — Path-traversal exposure during financial-source ingestion (MEDIUM — duplicates axis 5)

- File:line: `src/aeat/adapters/inbound/financial/providers/_base.py:247`
  (`path.resolve()` follows symlinks before reading).
- Attack surface: an operator who uploads a symlink-bearing path can have the provider
  read arbitrary host files (e.g. `~/.ssh/id_rsa`) into source bytes; the SHA-256
  becomes part of the persisted provenance record, leaking host file identity.
- Remediation: this is axis-5 territory but worth recording here since the input
  boundary is the surface. Reject symlinks before `read_bytes` (`resolved.is_symlink()`
  on the pre-resolve path), or constrain ingestion to a configured `aeat_inbox_root`.

### F8 — Registry TOML loader has no recursion / size guard on fragment merging (LOW)

- File:line: `src/aeat/domain/calculations/registry/_loader.py:255-278`
- Attack surface: the registry tree is fully under repo control today (not attacker
  input), so this is a defence-in-depth note only. The loader recursively merges every
  `revisions/*.toml` and every `revisions/<id>/*.toml` fragment using
  `freeze_toml(read_toml(...))` without bounding fragment count, total merged size, or
  recursion depth on nested append arrays. A future feature that exposes registry
  authoring to less-trusted contributors would inherit this gap.
- Remediation: cap fragment count per directory and reject revisions whose merged TOML
  exceeds a fixed byte budget. Today this is documentation-only.

### F9 — `csv.Sniffer` sample falls back to `csv.excel` on error without rejecting (LOW)

- File:line: `src/aeat/adapters/inbound/financial/providers/_csv.py:326-329`
- Attack surface: an unparseable / adversarial CSV silently downgrades to `csv.excel`
  rather than raising. Combined with the lenient header sniffer this means
  near-arbitrary content might still parse to a low-score layout.
- Remediation: when `csv.Sniffer().sniff` raises `csv.Error`, log a warning that names
  the source path (already done at debug level); ensure the eventual layout score
  threshold (`< 3` ⇒ no match) is genuinely enforced. The current `_locate_header`
  already returns `(0, None, ...)` below score 3, so the structural gate exists; this is
  a documentation note.

### F10 — OFX provider trusts ofxparse duck-typed objects without size check (LOW)

- File:line: `src/aeat/adapters/inbound/financial/providers/_ofx.py:107-130`
- Attack surface: `ofxparse` is a permissive SGML-style parser; a malformed OFX with
  nested `<BANKMSGSRSV1>` blocks could produce a long `transactions` list and exhaust
  memory. The provider iterates without a row-count cap.
- Remediation: same per-provider row cap as F1; reject ingestion when
  `len(statement.transactions)` exceeds the cap.

## summary count

| Severity | Count | Findings |
| --- | --- | --- |
| HIGH    | 1     | F1 |
| MEDIUM  | 4     | F2, F3, F5, F7 |
| LOW     | 5     | F4, F6, F8, F9, F10 |

Total: 10 findings.

Most concerning: **F1** — every inbound financial provider reads the operator-supplied
source via `Path.read_bytes()` with no size ceiling. The combination of unbounded read
plus pdfplumber / openpyxl / csv-Sniffer parsing makes the financial-input pipeline the
single highest-risk DoS surface for a local-only application that may in the future
ingest files from a less-trusted operator surface (web upload, scheduled drop folder).

Notably **clean** (no findings): the cryptographic deserialization path
(`EncryptedJSON.process_result_value`) is AEAD-authenticated before `json.loads` runs;
the XML parser is `defusedxml`; no `pickle` / `yaml.load` / `eval` exists in production
code; tomllib is stdlib-safe; all JSON envelopes I inspected validate through strict
pydantic v2 models.
