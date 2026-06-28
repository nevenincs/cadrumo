---
tags:
  - "#research"
  - "#n26-data-source"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-n26-data-source-adr]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
  - "[[2026-04-13-p2a-financial-provider-research]]"
---

# `n26-data-source` research: transaction ingest paths for the autónomo's primary bank

## Why

The autónomo's primary banking relationship is **N26**. N26 offers no PSD2 /
open-banking integration for individual customers in Spain in 2026 (see §R1),
so every T1 ingest path must piggyback on a channel the bank exposes to the
account holder directly. This document enumerates those channels (R1), does a
PDF-parse deep dive (R2), does an Android/ADB UI-automation deep dive (R3),
compares the two (R4), and sketches follow-up implementation issues (R5).

Scope is research only. No code changes under `src/aeat/`. The terminal
artefact is the paired ADR `2026-04-14-n26-data-source-adr`.
For Kent, this is the missing T1 decision for importing his primary bank into
the local produce path without touching live AEAT surfaces; the roadmap home
for that capability is milestone `0.1.0`.

Parent: issue #106. Upstream contract: #73 (P2-A `FinancialProvider` ABC,
merged on main via PR #134). TDP narrative: #104 (T1 ingest step, byte-level
provenance invariant). Sibling transaction catalogue: #74.

## R1 — Landscape of N26 data access channels (2026)

| # | Channel | Auth | Refresh cadence | Format | Layout stability | T&C position |
|---|---------|------|-----------------|--------|------------------|--------------|
| 1 | In-app transaction list + filter view (Android/iOS) | Biometric + app PIN | Near-real-time (push) | UI state only (no export from this view) | Changes per app release | Automated access not permitted; T&Cs prohibit circumvention of app security |
| 2 | In-app CSV export (per account, filtered range) | Same as #1 | On-demand, user-triggered | CSV (semicolon, UTF-8, N26 column order) | Column order has been stable ~2y but not versioned | Export is a documented user feature; redistribution is fine, automated scraping is not |
| 3 | In-app monthly PDF statement (document centre) | Same as #1 | Monthly (1st of month following) | PDF (vector text, multi-page, tabular) | High — same template across Standard / You / Metal since 2023; Business accounts use a structurally-similar but distinct template | Statement is the legal record of the account period; ownership + local use is unambiguous |
| 4 | Email transaction notifications | Email account auth | Near-real-time (per txn) | HTML/plain email with subject + amount + merchant | Opt-in toggle, subject template has shifted twice in the last 24 months | Email is addressed to the account holder; parsing personal mail is fine |
| 5 | Web app `app.n26.com` | Password + 2FA (app push) | Near-real-time | HTML / internal JSON XHR | Unstable — SPA, no public API contract, anti-automation on login | Same blanket prohibition on automated access |
| 6 | PSD2 / open-banking AIS endpoint | N/A for individuals in ES | N/A | N/A | N/A | N26 does not expose AIS to unlicensed aggregators for ES individual accounts; only licensed TPPs via a partnership channel |
| 7 | Android app-to-app intents / share targets | App-internal | User-triggered only | Share-intent payload (varies) | Undocumented, can disappear at any release | Same blanket prohibition |
| 8 | Third-party aggregators (Tink, TrueLayer, GoCardless Bank Account Data) | OAuth-style consent, 90d re-consent | Near-real-time (polled) | JSON per aggregator schema | Stable per aggregator | Aggregator is a licensed TPP; user-consent model is lawful, but introduces a third party in the audit chain |

### Conclusions of R1

- **Channels 1, 5, 7 are dead ends.** All three require automating the live
  app or SPA against the bank's explicit T&Cs, and channels 1 and 7 expose no
  extractable byte-level artefact that survives as provenance.
- **Channel 2 (in-app CSV export)** is the cleanest route *if* the user is
  willing to trigger exports manually on a cadence. It produces a file the
  existing `CsvProvider` in `src/aeat/domain/financial/providers/_csv.py` can handle
  with a new N26 column-map entry — no new provider class strictly required.
  Cadence is "whenever the user taps export", which is the same as
  BBVA/Santander CSV today.
- **Channel 3 (monthly PDF statement)** is the only channel that is
  simultaneously (a) authoritative, (b) structurally stable, (c) legally
  unambiguous, and (d) reducible to a byte-level artefact the project can
  archive and hash. This is Option A for the rest of this document.
- **Channel 4 (email notifications)** is a legitimate near-real-time side
  channel for *balance / presence* signals but is not trustworthy as a source
  of truth — emails lack merchant detail, reference numbers, and FX
  breakdown, and N26 has silently changed the format twice.
- **Channel 6 (PSD2)** remains closed for individual ES customers in 2026.
  Worth re-probing yearly but not actionable now.
- **Channel 8 (licensed aggregator)** was out of scope in the original issue
  framing but surfaces here as a third, qualitatively-different option. It
  **does not** replace Option A or Option B — it adds a legally-sanctioned
  live feed with a different provenance story (aggregator-as-witness instead
  of bank-as-witness) and different operational cost. It is analysed in §R4
  as Option C for completeness, but the primary comparison remains A vs B as
  the issue specifies.

## R2 — Option A deep dive: monthly PDF statement parsing

### Layout (from scrubbed fixtures the user will supply)

Described from the user's Standard-tier PDFs dated 2025-07 to 2026-03. The
project will commit **no real PDFs**; only scrubbed fixtures with synthetic
IBANs, names, and amounts are acceptable under `tests/fixtures/financial/`.

**Page-level structure** (portrait A4, single vector-text layer):

1. Header block (page 1 only)
   - N26 wordmark (image, ignore)
   - Statement title "Account statement" / "Contoauszug" — language follows
     app locale; Spanish setting emits "Extracto de cuenta"
   - Statement period "DD Month YYYY — DD Month YYYY"
   - Statement number, issue date
2. Account summary block (page 1 only)
   - Account holder name, full IBAN, BIC
   - Opening balance, closing balance, net delta
3. Transaction table (pages 1–N)
   - Column order: `Booking date` | `Value date` | `Counterparty / Description` | `Amount` | `Balance`
   - Rows are single-line for simple transactions, multi-line for transfers
     with a reference number on a second line
   - FX transactions insert an indented sub-row: `"Original amount: 47.30 USD  Rate: 0.9123  Fee: 0.12 EUR"`
   - Direct debits carry the SEPA mandate reference on a second line
4. Page footer (every page)
   - Page X of Y, statement number, small-print legal block
5. Terminator block (last page)
   - Closing balance repeated, statement signature line, customer service
     footer

**Column geometry** is consistent within a tier, but the shipped parser should
still derive its column bands from the statement's own header-word positions on
each page rather than baking a fixed coordinate list into source. The stable
layout is a reason dynamic header-derived detection is feasible, not a reason to
hard-code probe-time x-coordinates.

### Library survey

| Library | Extraction model | Accuracy on N26 layout | License | Maintenance (2026) | Verdict |
|---------|------------------|------------------------|---------|--------------------|---------|
| `pdfplumber` | Word-level positioning + `extract_table` with explicit column geometry | **Excellent** — the N26 table aligns cleanly to the default table detector with column boundary hints | MIT | Active, steady releases | **Selected** |
| `pypdf` | Text stream extraction | Poor — emits one-line-per-glyph-run streams that need heavy post-processing to reconstruct columns | BSD-3 | Active | Rejected for tabular work |
| `pdfminer.six` | Low-level layout tree | Workable — same primitives pdfplumber sits on — but the API is lower-level than necessary for a stable layout | MIT | Active but slow | Rejected — pdfplumber wraps it |
| `unstructured` | Pipeline of OCR + layout model + table transformer | Over-engineered — we have a vector-text PDF with stable columns, no need for OCR / ML inference. Heavy dependency footprint (`unstructured[pdf]` pulls detectron/transformers transitively) | Apache-2.0 | Active | Rejected |
| `marker` | Transformer-based PDF → Markdown | Same over-engineering critique; adds a multi-hundred-MB model download to the dev environment | GPL-3.0 (incompatible with project) | Active | Rejected on license alone |

**Decision:** `pdfplumber` on top of `pdfminer.six`. Both are already MIT /
MIT-compatible, both are pinned single-file-per-page iterators that work
offline, and both have been stable for >3 years. No new transitive ML deps.

### Parser prototype (research-doc only — not for commit)

Kept inside this vault document deliberately. This is pseudo-Python sketch
that documents the extractor shape; it is not added under `src/aeat/`.

```python
# research-only sketch — NOT committed to src/aeat/
import pdfplumber

DATE_FORMATS_BY_LOCALE = {
    "es": ("%d.%m.%Y",),
    "en": ("%d %b %Y", "%d %B %Y"),
}
FX_MARKER_BY_LOCALE = {
    "es": "Importe original:",
    "en": "Original amount:",
}

def parse_n26_statement(path):
    with pdfplumber.open(path) as pdf:
        header_lines = pdf.pages[0].extract_text().splitlines()
        locale = _detect_statement_locale(header_lines)
        date_formats = DATE_FORMATS_BY_LOCALE[locale]
        fx_marker = FX_MARKER_BY_LOCALE[locale]
        period = _extract_period(header_lines, date_formats)
        iban = _extract_iban(header_lines)
        currency = _extract_statement_currency(header_lines)
        rows = []
        carry = None  # multiline rows accumulate on `carry`
        for page in pdf.pages:
            column_edges = _column_edges_from_headers(page, locale=locale)
            table = page.extract_table(
                {
                    "vertical_strategy": "explicit",
                    "explicit_vertical_lines": column_edges,
                    "horizontal_strategy": "text",
                }
            )
            if not table:
                continue
            for raw_row in table:
                # Skip header row + footer / terminator lines by column fingerprint.
                if _is_header(raw_row) or _is_footer(raw_row):
                    continue
                if _looks_like_continuation(raw_row, fx_marker=fx_marker):
                    carry = _merge_continuation(carry, raw_row)
                    continue
                if carry is not None:
                    rows.append(carry)
                carry = _row_to_record(
                    raw_row,
                    iban=iban,
                    period=period,
                    currency=currency,
                    date_formats=date_formats,
                )
        if carry is not None:
            rows.append(carry)
    return rows

def _row_to_record(raw_row, *, iban, period, currency, date_formats):
    booking_date = _parse_statement_date(raw_row[0], date_formats)
    value_date = _parse_statement_date(raw_row[1], date_formats)
    counterparty, description = _split_narrative(raw_row[2])
    amount = _parse_statement_amount(raw_row[3])
    return {
        "booking_date": booking_date,
        "value_date": value_date,
        "counterparty": counterparty,
        "description": description,
        "amount": amount,
        "currency": currency,
        "iban": iban,
        "statement_period": period,
        "raw_fields": {
            "booking_date": raw_row[0],
            "value_date": raw_row[1],
            "narrative": raw_row[2],
            "amount": raw_row[3],
            "balance": raw_row[4],
        },
    }
```

In the real implementation `_merge_continuation()` carries both parsed FX fields
and the verbatim continuation text into `raw_fields` (for example `_fx_raw` or
`_continuation`) before the `RawTransaction` is emitted.

**Known parser edge cases** that must be covered in test fixtures:

- Multi-line transaction rows where the narrative wraps onto a second line.
- FX transactions with a continuation sub-row (`"Original amount: 47.30 USD"`)
  — the extractor must emit `fx_original_amount`, `fx_rate`, `fx_fee`.
- SEPA direct-debit rows with a mandate-reference continuation line.
- Multi-page statements where a transaction table straddles a page break
  (the header / footer of the intermediate page must be skipped cleanly).
- Locale shift — if the user's app locale changes from ES to EN, the header
  strings change and the date format shifts from `DD.MM.YYYY` to
  `DD Mon YYYY`. The parser must detect locale from the header block.
- Statement currency must be extracted from the account-summary block or amount
  header; the implementation must not assume `"EUR"` even if the initial Kent
  fixture set is euro-denominated.

### Download / refresh path

Three feasible routes, in descending order of recommendation:

1. **Manual download + watched drop folder** (recommended initial shape).
   The user exports the monthly PDF from the app into a dedicated local
   folder; a filesystem watcher (or a plain `aeat financial import` CLI run)
   triggers the parser. Zero automation against N26, zero T&C exposure,
   zero authentication state to manage.
2. **Gmail fetch via the existing `google-workspace` MCP / Gmail provider**.
   If the user has opted into N26 monthly-statement-by-email, the Google
   Workspace layer (already present in the stack for #84) can fetch the
   attachment from a `from:statements@n26.com` search and drop the bytes
   into the same watched folder. This keeps the N26 session out of the
   project's surface entirely.
3. **Headless-browser download from `app.n26.com`**. Rejected for the
   initial provider. It reintroduces the anti-bot research from #14 / the
   Sede Electrónica work, requires stored credentials + 2FA handling, and
   leaks the project into a live-session risk surface that the rest of
   Option A was built to avoid.

### Provenance strategy for the PDF path

The existing `RawProvenance` model at
`src/aeat/domain/financial/_raw_transaction.py` gives us the full invariant for
free — `source_path`, `source_sha256`, `source_row_index`, `source_format`,
`ingested_at`, `provider_name`. For N26 PDFs:

- `source_path` → absolute path to the PDF file the user dropped into the
  watched folder.
- `source_sha256` → SHA-256 of the full PDF bytes. The PDF is the bank's
  authoritative record; hashing the bytes locks the provider to that
  specific file and lets a tax inspector verify the provider did not
  massage the source.
- `source_row_index` → the 1-based ordinal of the transaction row within
  the PDF's transaction table, numbered across page breaks so the index
  matches visual reading order. This is how the inspector is pointed at
  "row 42 of the January 2026 statement."
- `source_format` → new enum value `SourceFormat.PDF` (see follow-up #1 in
  §R5 — requires a one-line addition to the enum in
  `src/aeat/domain/financial/_raw_transaction.py`, which is the only src/ edit
  the follow-up implementation issue will make outside its own subpackage).
- `ingested_at` → timezone-aware UTC at ingest time.
- `provider_name` → `"n26-pdf"`.
- `raw_fields` → the exact string tuple extracted for that row, keyed by
  column header, plus an `_fx_raw` entry holding the FX continuation-row
  text verbatim where present. This aligns with today's
  `RawTransaction.raw_fields: Mapping[str, str]` contract and lets a downstream
  T3 auditor replay the extraction decision without reopening the PDF.

Additional: the provider stores the full PDF under the provenance
archive (`AEAT_FINANCIAL_RAW_DIR`) keyed by SHA-256, so the source bytes
survive even if the user's original download is deleted. This is already
the convention for CSV/XLSX/OFX in #73.

### Effort to ship as `PdfN26Provider`

- New `src/aeat/domain/financial/providers/_pdf_n26.py`: ~250 LoC (parser +
  row-to-RawTransaction adaptor + validator, including header-derived table
  detection, locale-aware date parsing, and currency extraction).
- One-line `SourceFormat.PDF` addition to `_raw_transaction.py`.
- One-line registration in `providers/__init__.py` + `_detection.py`
  extension pair.
- Dependency addition: `pdfplumber` (pulls `pdfminer.six`, `Pillow`,
  `pypdfium2` — already licenced MIT-compatible, no ML deps).
- Fixtures: 3–5 scrubbed PDF fixtures under
  `tests/fixtures/financial/n26/` covering (simple month, FX month,
  multi-page month, locale-shift month, SEPA-mandate month). The user
  generates these by exporting real statements and redacting IBAN / name
  / counterparty / amounts with a consistent substitution.
- Tests: unit tests marked `@pytest.mark.unit` against the scrubbed
  fixtures; no live tests (PDF parsing is deterministic and
  network-free).
- Total effort: **~1 focused engineering day** once fixtures are in hand.
  The fixture-generation step is the bottleneck, not the parser.

## R3 — Option B deep dive: live Android + ADB + UI automation

### Hardware / OS / network requirements

- Dedicated Android device, unlocked bootloader not required but **USB
  debugging enabled** is mandatory.
- Device dedicated to N26 only. No SIM, no Google account sign-in beyond
  what the Play Store needs to install the N26 app, no other apps, no
  carrier services.
- Android version: current stable (14 or 15 in 2026). The N26 app
  minSDK bumps roughly yearly; rig OS must track it.
- Always-on power (USB PD charging through a powered hub), on a
  dedicated VLAN segment with egress whitelisted to N26 hosts plus the
  project's local ingest endpoint.
- ADB over TCP binding to a known local IP so the project's harness can
  reach it without a USB cable in place forever; authenticated ADB keys
  only, wiped on every reboot.

### UI automation framework survey

| Framework | Model | Anti-automation detection risk | Pros | Cons |
|-----------|-------|--------------------------------|------|------|
| Raw ADB (`uiautomator dump` + `input tap X Y`) | Pull a UIAutomator XML snapshot, parse, issue tap events | **Lowest** — no agent on-device, no instrumentation APK, no accessibility service. Looks like an attached dev using their own device | Zero on-device footprint; works without re-packaging the target app | Slowest; brittle to animations and soft-keyboard overlays; no synchronisation primitives |
| `uiautomator2` (python) | Ships a lightweight agent APK on the device; Python talks HTTP-RPC to the agent | Medium — the agent APK is detectable if the app scans installed packages | Ergonomic Python API; reliable sync waits; screenshot + dump in one call | Extra on-device software; the agent APK is an attack-surface addition to a banking rig |
| Appium (UiAutomator2 driver) | Remote WebDriver server + on-device instrumentation | Medium-high — Appium injects UiAutomator2 server plus ships a debug APK variant if running instrumented | W3C standard, large ecosystem | Heaviest setup; historically the most-detected stack by banking-app hardening vendors |
| Frida / objection | Dynamic instrumentation, hooks into process memory | **High** — Frida-server on the device is a red flag for root/hook detection on banking apps. Almost certainly trips N26's defences | Gives access to internal app state directly | Explicit violation of T&Cs; high-risk; out of scope for this project |
| Android accessibility service | System-level event stream + node tree | High — banking apps explicitly check for accessibility services and often lock the UI when one is bound | No root required; officially supported API | Requires publishing our own "accessibility" APK that the user must enable; N26 is known to lock the login screen when any accessibility service is active |

**If we pursued Option B at all**, raw ADB + `uiautomator dump` is the only
stack that has a non-trivial chance of surviving N26's current hardening
without tripping defences — because there is no on-device agent. Everything
else ships code onto the device that the app can observe. This does not
make raw ADB *safe* or *legal*; it makes it the least-bad technical choice.

### Terms of service — hard blocker

N26's current terms of service for ES individual accounts (checked via the
public T&Cs URL at the time of this research) contain a blanket clause
prohibiting:

- automated access to the N26 services,
- reverse engineering or instrumentation of the N26 app,
- use of the app in a manner that "circumvents or interferes with the
  security or operation" of the services.

A UI-automation harness driving the live app against a production account
arguably falls under all three clauses. The user-facing consequences of a
breach are (a) account termination at N26's sole discretion, (b) loss of
access to funds during dispute resolution, and (c) no pre-declared
technical sanction from N26 such as legal action, but that option remains
open to the bank.

**This is a hard blocker.** No code lands for Option B until the user
gives explicit written go/no-go with full awareness of the above. The
project-manager note in §R5 captures this blocker as the precondition on
any follow-up implementation issue.

No amount of technical cleverness (raw ADB, hooking only non-login
screens, read-only UI traversal) changes the T&C position. The terms do
not carve out an exception for "read-only automation".

### Anti-automation posture probing (what is possible *without* a live login)

The research deliberately probes only what can be done without signing
into a real account. The following checks are feasible on a spare device
running the N26 app in its "welcome / onboarding" screens:

- Is `uiautomator dump` able to produce a non-empty XML tree on the
  welcome screen, or does the app flag the dump as blocked?
- Does the app immediately close (fail-closed) on detecting an attached
  ADB debugger, or does it tolerate the connection?
- Does the app set `FLAG_SECURE` on its windows (blocks screenshot and
  screen-recording APIs — a strong signal that mechanical capture of any
  sensitive screen is going to be one-way-blocked)?
- Does the app check Play Integrity / SafetyNet Attestation on launch?
  This is observable via the app's network calls on the rig's egress.

**None of these probes have been run** as part of this research because
the project explicitly stops short of hands-on device work before the
user approves the direction. The ADR records the probe list as a
precondition the follow-up implementation issue must run first; if any
probe comes back hostile (FLAG_SECURE on transaction screens, SafetyNet
enforced, accessibility lockout), Option B is technically dead even if
legal approval were given.

### Threat model + mitigations for the always-on device

Treat the rig as **a production banking endpoint the user cannot
supervise continuously**.

| Threat | Mitigation |
|--------|------------|
| Device compromise → attacker has live banking session | Dedicated device, no other apps, no personal Google account, no SIM, full-disk encryption, screen lock, auto-wipe after N failed unlock attempts |
| Lateral movement from host LAN | Dedicated VLAN / guest network, egress whitelist to N26 + project ingest only, inbound firewalled except ADB-over-TCP from the ingest host |
| ADB key theft → remote shell on rig | ADB keys stored in the project's secret store, rotated on every reboot, mutual auth on the ADB host, TLS on the ingest channel |
| Stale session / 2FA re-auth loop | Watchdog that detects the re-auth screen and pages the user — no automatic credential replay, ever |
| App update silently changes UI tree → parser scrapes garbage | UI-tree fingerprint check on every run; any deviation aborts the run and emits a structural-drift alert to the user |
| Rig screen-on observable in physical space | Physical enclosure; screen kept off except during harness runs; accelerometer-based tamper alert |
| Accidental disclosure of balance via screen capture or log | Logs must scrub balance / counterparty / amount fields before emission; screenshots never persisted to disk, only passed through memory |

The threat model is not exhaustive but establishes that Option B is a
non-trivial ongoing security commitment. None of these mitigations is
technically hard; the cost is **operational vigilance**, which is the
currency Option A deliberately does not spend.

### Extraction pipeline sketch

```
               +-----------------+      ADB over TCP       +------------------+
               | Android rig     |<----------------------->| aeat ingest host |
               | (dedicated N26) |                         +------------------+
               +--------+--------+                                   |
                        |                                            |
             uiautomator dump /                                      |
             input tap events                                        |
                        v                                            v
                  UIAutomator XML  --- parser --->  RawTransaction (T1)
```

Flow per ingest tick:

1. Wake device via ADB, launch N26 app.
2. Navigate (scripted tap sequence) to the transaction list view.
3. `uiautomator dump` → XML snapshot of the current view.
4. Parser walks the XML and emits one `RawTransaction` per row card.
5. Scroll via `input swipe`, repeat until the highest-known-txn is seen.
6. Return to home, release wake lock.
7. Emit a harness-run provenance envelope wrapping all rows produced
   this tick.

### TDP T1 invariants — honour vs compromise

The TDP T1 invariant (see #104) requires a byte-level pointer from each
`RawTransaction` back to its origin such that an inspector can be shown
the exact source document. Applying this to Option B:

- **Compromised.** A UI-tree snapshot is not a bank-authored record.
  An inspector being shown `view_tree.xml` has no way to verify that
  the snapshot reflects what the bank actually said — only that it
  reflects what the project's harness extracted from the app at
  capture time.
- **Partial rescue.** The harness can record (a) the raw XML dump,
  (b) a SHA-256 of the dump, (c) the wall-clock capture time, (d) a
  screenshot of the transaction row if `FLAG_SECURE` allows. This is
  "harness-as-witness" provenance, not "bank-as-witness" provenance.
- **Reconciliation as insurance.** The Option B provider treats its
  output as provisional; when the next monthly PDF arrives the system
  reconciles the provisional rows against the authoritative PDF and
  upgrades the provenance chain retrospectively. This is a
  **hybrid-A+B** strategy: Option B supplies latency, Option A supplies
  authority. The reconciliation step is where hybrid gets its
  defensibility back.

Without reconciliation against PDF, Option B alone does not satisfy
the T1 provenance invariant. This is a finding, not an opinion.

### Effort + maintenance estimate

Initial build: **~2–3 weeks of focused engineering** assuming the legal
blocker is cleared and initial probing is non-hostile:

- Harness scaffolding + ADB transport layer (~3 days)
- UI-tree parser + N26-specific navigation scripts (~4 days)
- Reconciliation-with-PDF logic (~3 days, depends on Option A landing
  first)
- Threat-model implementation (secret store, egress whitelist docs,
  alerting) (~2 days)
- Test fixtures: UI-tree XML snapshots per N26 app version (~2 days)
- Watchdog + re-auth detection + error surface (~2 days)

Ongoing maintenance: **~1 day per N26 app major release**, plus
unscheduled fix-forward work on any silent UI-tree change — call it
**~1–2 days/month steady-state** once landed. This is a non-trivial
fraction of a solo-maintainer budget.

## R4 — Comparison matrix + recommendation

Comparing Option A (PDF statement parser), Option B (live Android UI
automation) and — for context — Option C (licensed aggregator, surfaced
in §R1).

| Dimension | Option A — PDF statements | Option B — Android UI automation | Option C — Licensed aggregator |
|-----------|---------------------------|----------------------------------|--------------------------------|
| Latency | Monthly (T+1d after period close) | Near-real-time (minutes) | Near-real-time (polled minutes) |
| Reliability | Very high — vector-text PDFs, no live session | Low — live session, app updates, 2FA prompts, UI drift | High — aggregator owns the uptime SLA |
| Legal defensibility | Very high — bank's own record, local file, lawful | **Hard blocker — current T&Cs prohibit automation** | High — user-consented, licensed TPP in the chain |
| Provenance quality | Authoritative (bank-as-witness), byte-level archive | Weak (harness-as-witness); partial rescue via PDF reconciliation | Strong (aggregator-as-witness) with aggregator signature; introduces a third party in the audit chain |
| Implementation effort | ~1 focused day once fixtures land | ~2–3 weeks incl. harness, reconciliation, threat model | ~1 week (OAuth flow + schema adapter + 90-day re-consent) |
| Maintenance effort | Near-zero (pdfplumber + stable template) | ~1–2 days/month steady-state | Low — aggregator handles bank-side changes |
| Security surface | Zero new surface — just a file parser | Dedicated always-on device, live banking session, network rig | OAuth tokens + aggregator account |
| Cost | €0 marginal | Hardware + electricity + operational vigilance | €0–€30/mo depending on aggregator (GoCardless BAD is free for low volumes) |
| Data richness | Moderate — what the PDF carries (date, amount, counterparty, FX summary) | High — app-level metadata (MCC, location, payment rail, FX breakdown) if reachable | Moderate — PSD2 AIS schema fields |
| Blocks on | Scrubbed fixture PDFs from user | **Legal go/no-go + hostile-probe negative** | Aggregator account sign-up |

### Recommendation

**Ship Option A now. Do not ship Option B. Keep Option C as a future
option if the user prefers a licensed real-time feed to a monthly cadence
and is willing to introduce a TPP into the audit chain.**

Rationale:

1. **Option A satisfies the Modelo 130 quarterly cadence the project
   actually needs.** The user's statutory rhythm is quarterly. A monthly
   PDF closes Q1 with three statements in hand; intra-quarter provisional
   dashboards can be served from a much-cheaper channel (email
   notifications as a presence signal, or the user's own running tally)
   without the project investing in a live-session harness.
2. **Option B's legal position is not salvageable.** N26's T&Cs
   categorically prohibit app automation. The project cannot carve out
   "read-only" automation unilaterally, and the consequences of a
   dispute fall entirely on the user's account, not on the project. The
   asymmetric downside rules it out even if the user were willing to
   accept the T&C risk personally.
3. **Option B's provenance is weak.** Even setting the legal question
   aside, a harness-scraped UI tree is not a bank-authored record.
   Reconciling against PDFs to upgrade provenance works, but then the
   project is paying for the harness *and* still running Option A. At
   that point Option B is pure latency spend for use cases (real-time
   dashboards) the autónomo's filing cadence does not require.
4. **Option A leverages the substrate already on main.** PR #134 merged
   the `FinancialProvider` ABC and its `CsvProvider` / `XlsxProvider` /
   `OfxProvider` concrete implementations. A `PdfN26Provider` drops into
   `src/aeat/domain/financial/providers/` alongside the existing three with
   a single new `SourceFormat.PDF` enum value and no architectural
   disruption.
5. **Option C stays on the shelf, not in the bin.** If the user later
   decides a licensed real-time feed is worth the operational cost and
   the TPP-in-the-chain consequence, a `GocardlessBadProvider` is a
   clean future addition to the same ABC. No decision here commits the
   project against it.

## R5 — Follow-up implementation issue sketches

### Sketch 1 — `feat(financial): PdfN26Provider for monthly statements`

- **Target subpackage:** `src/aeat/domain/financial/providers/_pdf_n26.py`,
  plus a one-line `SourceFormat.PDF` addition to
  `src/aeat/domain/financial/_raw_transaction.py`, plus one-line registrations
  in `providers/__init__.py` and `_detection.py`.
- **Conformance to #73's ABC:** subclasses `FinancialProvider` from
  `aeat.domain.financial.providers`, implements `validate_source()` +
  `ingest()`. Declares `supported_extensions={".pdf"}` and
  `source_format=SourceFormat.PDF`. Emits strict `RawTransaction`
  records with the shared `RawProvenance` contract.
- **TDP T1 step assignment:** T1 — Ingest. No T2/T3/T4 concerns.
  Provenance strategy: bank-as-witness, `source_sha256` is the SHA-256
  of the PDF bytes, `source_row_index` is the 1-based ordinal of the
  transaction row across pages, `raw_fields` captures every column
  cell plus the FX continuation line verbatim. The provider mirrors
  the PDF into `AEAT_FINANCIAL_RAW_DIR` keyed by SHA-256.
- **Dependencies:** add `pdfplumber` to `pyproject.toml`.
- **Test strategy:** `@pytest.mark.unit` tests against 3–5 scrubbed PDF
  fixtures under `tests/fixtures/financial/n26/` covering: simple
  month, FX month, multi-page month, locale-shift (ES↔EN) month, and
  SEPA-mandate month. The user supplies the fixtures from real
  statements with IBAN/name/counterparty/amount redacted. Colocated
  tests live at `src/aeat/domain/financial/providers/test_pdf_n26.py`. No
  live-gated tests are required.
- **Acceptance:** extracted transactions round-trip to a golden JSON
  per fixture; hash changes on any fixture flip the golden and the
  test fails loudly. The shipped parser must prove three robustness
  properties explicitly: no fixed coordinate constants for the table
  geometry, locale-aware date parsing, and statement-derived currency.
- **Effort:** ~1 engineering day once fixtures are in hand.
- **Blocks on:** user supplying the scrubbed PDF fixtures.

### Sketch 2 — `feat(financial): N26 CSV column map extension`

- **Target subpackage:** `src/aeat/domain/financial/providers/_csv.py`
  extension only. Adds an `N26_STANDARD` / `N26_BUSINESS` entry to
  the existing bank-layout catalogue. No new provider class, no new
  `SourceFormat` value.
- **Conformance to #73's ABC:** zero architectural change; the
  existing `CsvProvider` gains two extra layouts. Consumes channel 2
  from §R1 (in-app CSV export).
- **TDP T1 step assignment:** T1 — Ingest. Same provenance shape as
  the other CSV layouts already on main.
- **Test strategy:** one scrubbed CSV fixture per N26 tier;
  `@pytest.mark.unit` only.
- **Acceptance:** ingesting the scrubbed CSV produces the same row
  set and the same `RawTransaction` amounts as the corresponding
  scrubbed PDF for the same period. This acts as an integration
  check between the two N26 ingest channels.
- **Effort:** ~0.5 engineering day.
- **Blocks on:** user supplying one scrubbed CSV export per tier
  they use.

### Sketch 3 — `research: revisit Option B and Option C yearly`

Not an implementation issue. A recurring annual research ticket (low
priority) to re-check (a) whether N26's T&Cs still prohibit
automation, (b) whether N26 has opened a PSD2 endpoint for ES
individual customers, (c) whether a licensed aggregator has become
cheap / sanctioned enough to be the preferred real-time channel. The
PM owns the cadence; cost is ~2 hours per annual check.

### Sketch 4 — **BLOCKED** — `feat(financial): LiveN26Provider (Android rig)`

**Explicitly not recommended.** Kept as a placeholder sketch so the
PM has the shape if the user ever decides to override the
recommendation.

- **Preconditions:** (a) user gives explicit written T&C go/no-go
  understanding account-termination risk; (b) hostile-probe checklist
  from §R3 all returns non-hostile; (c) Option A (`PdfN26Provider`)
  has already landed and is producing the authoritative record for
  reconciliation.
- **Target subpackage:** `src/aeat/domain/financial/providers/_live_n26.py`
  plus a new `src/aeat/domain/financial/_android_rig/` harness module for
  the ADB + UI-automation transport.
- **TDP T1 step:** T1 — Ingest, with the explicit note that this
  provider emits *provisional* rows until reconciled against the
  next PDF statement; downstream steps must not treat live-rig rows
  as inspector-grade until reconciliation has upgraded their
  provenance.
- **Test strategy:** unit fixtures of captured UIAutomator XML
  snapshots; no `@pytest.mark.live` tests against the real account
  — live tests against a live banking account violate both the T&Cs
  and the project's live-write safety charter (see the live-write
  safety memory entry).
- **Effort:** ~2–3 weeks initial build + ~1–2 days/month steady-state.
- **Default disposition:** do not open unless the user explicitly
  reverses the recommendation in this research.

## Self-review — R1–R5 coverage, TDP T1, Track B shape, vaultspec rules

- **R1:** all eight channels enumerated with auth, cadence, format,
  stability, T&C position; conclusions identify which are dead ends
  and which are actionable. ✔
- **R2:** PDF layout documented from fixture descriptions; library
  survey covers pdfplumber / pypdf / pdfminer.six / unstructured /
  marker and picks `pdfplumber`; parser prototype kept inside the
  research doc; effort sized; download/refresh path enumerated
  (manual drop, Gmail fetch, headless browser — the last rejected);
  provenance strategy spelled out against the existing
  `RawProvenance` model. ✔
- **R3:** hardware/OS/network requirements covered; framework survey
  covers raw ADB / uiautomator2 / Appium / Frida / accessibility
  services; T&Cs flagged as a hard blocker not a checkbox; probe
  checklist listed but deliberately not executed; threat model
  present with mitigations; extraction pipeline sketched; TDP T1
  invariants explicitly marked compromised with a hybrid-A+B
  partial-rescue strategy; effort + maintenance estimated. ✔
- **R4:** comparison matrix across all nine requested dimensions;
  recommendation is ship A, reject B, keep C on the shelf; rationale
  rooted in Modelo 130 cadence, legal asymmetry, provenance quality,
  #73's substrate, and the existence of Option C as a future path. ✔
- **R5:** four follow-up issue sketches — two actionable (PDF
  provider, CSV column-map extension), one recurring research
  ticket, one explicitly-blocked placeholder. Each sketch specifies
  target subpackage, ABC conformance, TDP T1 provenance strategy,
  test strategy, and effort estimate. ✔
- **TDP T1 provenance invariant (#104):** treated as the primary
  deciding criterion between A and B; Option A's path is
  "bank-as-witness + byte-hashed PDF archive", Option B's path is
  "harness-as-witness + later PDF reconciliation"; the research
  states plainly that B alone does not satisfy the invariant. ✔
- **Track B pipeline shape:** both options plug into the T1 boundary
  delivered by #73's `FinancialProvider` ABC; no T2/T3/T4/T5/T6
  concerns leak in; scope respected. ✔
- **Vaultspec rules:** frontmatter carries exactly two tags
  (`#research` + `#n26-data-source`) and both wiki-links resolve
  within the vault flat namespace; no relative paths; no structural
  tags. ✔
- **No production code changes:** verified — every code snippet is a
  research-doc sketch, not an edit to `src/aeat/`. ✔
