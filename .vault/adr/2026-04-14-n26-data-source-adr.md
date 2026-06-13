---
tags:
  - "#adr"
  - "#n26-data-source"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-n26-data-source-research]]"
  - "[[2026-04-21-n26-data-source-audit]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
  - "[[2026-04-13-p2a-financial-provider-research]]"
---

# `n26-data-source` adr: `pdf-statement-first-live-rig-blocked` | (**status:** `accepted`)

## Problem Statement

Issue `#106` asks where N26 transaction data enters the project's
Transaction Data Pipeline (#104) at T1 — Ingest. N26 exposes no PSD2
endpoint to individual ES customers in 2026; every ingest path must
piggyback on a channel the bank offers the account holder directly. The
research doc `2026-04-14-n26-data-source-research` enumerates eight
channels and deep-dives the two the issue explicitly names: monthly PDF
statements (Option A) and live Android + ADB UI automation (Option B).
The paired research document is `2026-04-14-n26-data-source-research`
(see `related:` frontmatter).

## Considerations

- Any N26 provider must conform to the `FinancialProvider` ABC delivered
  by #73 (PR #134, on main). The decision chosen here must slot into
  that existing substrate with no architectural disruption.
- This is a local Track-B ingest decision for roadmap milestone `0.1.0`
  ("Kent can feed his bank data in and trust the classification"). It
  does not alter the export-first product charter or any AEAT write/read
  policy because the chosen path remains file-backed and off-AEAT.
- The TDP T1 provenance invariant (#104) requires every `RawTransaction`
  to carry a byte-level pointer back to its origin so a tax inspector
  can be shown the exact source document. This invariant is the
  primary deciding criterion — not latency, not effort, not data
  richness.
- The autónomo's statutory cadence for the casillas that Track B feeds
  is **quarterly** (Modelo 130) and **quarterly/annual** (Modelo 303,
  390). A monthly cadence satisfies this rhythm; near-real-time does
  not buy any statutory capability the project currently lacks.
- N26's current terms of service for ES individual accounts prohibit
  automated access, reverse engineering, and instrumentation of the
  app. Account termination is N26's sole discretion and its downside
  falls entirely on the user, not on the project.
- The project's **live-write safety charter** (#116) forbids live
  automation that could take irreversible action against an external
  account. A live-rig harness that drives the real N26 app against a
  real account is adjacent to that charter's concerns, even when
  nominally read-only — navigation taps could trigger confirmation
  dialogs, support chat widgets, or outgoing transfer flows if the UI
  drifts.
- A licensed aggregator (Option C — GoCardless Bank Account Data,
  TrueLayer, Tink) surfaced in the research as a third qualitatively
  different option, not in the original issue framing. It is neither
  chosen nor rejected here; it is kept on the shelf for a future
  decision.

## Constraints

- Public API must continue to live under `aeat.domain.financial` and
  `aeat.domain.financial.providers` only.
- New boundary types must be strict frozen pydantic v2 models with
  `enum.StrEnum` closed sets — the research records that the only
  cross-cutting type change required is a new `SourceFormat.PDF`
  enum value in `src/aeat/domain/financial/_raw_transaction.py`.
- No live tests against a real N26 account. Any provider that ships
  must honour the live-write safety charter and must not require
  hitting production banking infrastructure from CI.
- No real PDFs or CSVs committed to the repository. All fixtures must
  be scrubbed (synthetic IBAN / name / counterparty / amounts) with a
  consistent substitution so the fixtures exercise the parser
  end-to-end without leaking the user's real financial data.
- No code changes under `src/aeat/` in this research issue. The ADR is
  the terminal artefact for #106; implementation follows in the
  follow-up issues the PM will open.

## Decision

**Accepted:** ship a **`PdfN26Provider`** that parses N26's monthly PDF
statements into strict `RawTransaction` records under the existing
`FinancialProvider` ABC, **plus** a minimal N26 column-map extension to
the existing `CsvProvider` for the in-app CSV export channel.
**Rejected:** a live Android + ADB + UI-automation harness
(`LiveN26Provider`). **Deferred:** a licensed-aggregator path
(Option C); keep it on an annual revisit cadence.

## Implementation (shape for the follow-up issues, NOT code landed here)

- **Primary path — `PdfN26Provider`** under
  `src/aeat/domain/financial/providers/_pdf_n26.py`:
  - Uses `pdfplumber` (MIT) as the sole new dependency; pinned in
    `pyproject.toml`.
  - Derives table boundaries from detected header-word positions on
    each page; the shipped parser must not rely on a fixed point list
    baked into source.
  - Detects statement locale from the page-1 header block and selects
    the date parser accordingly (`DD.MM.YYYY` for ES, `DD Mon YYYY` /
    `DD Month YYYY` for EN-class locales).
  - Extracts the statement currency from the account summary / amount
    header rather than hard-coding `"EUR"`.
  - Emits `RawTransaction` with `provenance.source_format =
    SourceFormat.PDF`, `source_sha256` = SHA-256 of the full PDF,
    `source_row_index` = 1-based ordinal of the transaction row across
    the PDF's transaction table, `raw_fields` capturing every column
    cell plus the FX continuation line verbatim where present.
  - Mirrors the ingested PDF into `AEAT_FINANCIAL_RAW_DIR` keyed by
    SHA-256 so the source bytes survive independent of the user's
    original download.
  - Download / refresh path: manual drop into a watched folder (initial
    shape), with the existing Google Workspace Gmail fetcher as the
    follow-up convenience for users on statement-by-email.
- **Secondary path — N26 CSV column-map extension** to the existing
  `CsvProvider` (no new provider class, no new `SourceFormat` value):
  adds N26 Standard and N26 Business layouts to the bank-layout
  catalogue already on main. This exists primarily as a faster-cadence
  alternative for users willing to tap "Export" more often than the
  monthly statement cycle.
- **Cross-cutting type change:** add `PDF = "pdf"` to the
  `SourceFormat` `StrEnum` in
  `src/aeat/domain/financial/_raw_transaction.py`. One-line addition; no
  other cross-cutting model changes.
- **No new subpackages.** The implementation touches
  `aeat.domain.financial.providers` only, plus the one-line enum addition
  above. Public API discipline holds.
- **Testing:** colocated `@pytest.mark.unit` tests under
  `src/aeat/domain/financial/providers/test_pdf_n26.py` against 3–5 scrubbed
  fixture PDFs the user supplies. No `@pytest.mark.live` tests for
  this provider. Live test gating continues to use
  `AEAT_LIVE_TESTS_ENABLED=1` as the canonical env var across the
  project. The acceptance set must include locale-aware dates,
  statement-derived currency, and header-derived table geometry.

## Rationale

- **Provenance wins.** A PDF is the bank's own authoritative record for
  the statement period; archiving the bytes and hashing them gives
  Option A a bank-as-witness provenance chain that Option B cannot
  match. The TDP T1 invariant is the deciding criterion here, and
  Option A satisfies it directly while Option B only satisfies it
  retroactively via reconciliation against Option A — at which point
  the project is running Option A anyway.
- **Cadence is adequate.** The project's Modelo 130 / 303 / 390 filing
  rhythm is quarterly and annual. A monthly PDF closes Q1 with three
  statements in hand. Near-real-time buys a dashboard experience, not
  a statutory capability.
- **Legal asymmetry.** N26's T&Cs prohibit automation; the downside of
  a dispute falls on the user's account, not on the project. The
  asymmetry between the project's potential benefit (~2 weeks of
  faster dashboards) and the user's potential loss (account
  termination during filing season) is extreme and unconditional on
  technical cleverness.
- **Substrate re-use.** `PdfN26Provider` drops into the existing
  `FinancialProvider` ABC with a one-line enum addition and a single
  new module. Zero architectural disruption to the substrate #73
  delivered on main.
- **Option C stays available.** Rejecting Option B is not a
  commitment against all real-time paths. If the user later decides a
  licensed aggregator (with its own provenance story and its own
  operational cost) is worth the TPP-in-the-chain consequence, that
  provider is a clean future addition under the same ABC and does not
  require revisiting this ADR.

## Consequences

- **Committed work (follow-up issues, owned by PM to open):**
  (a) `PdfN26Provider` + scrubbed fixtures + tests; (b) N26 CSV
  column-map extension + fixtures + tests; (c) annual revisit of
  Option B / Option C T&C and PSD2 state.
- **Not committed:** any Android rig, any UI-automation harness, any
  credential storage for a live N26 session, any headless-browser
  automation against `app.n26.com`. None of these lands unless the
  user explicitly reverses this ADR with full awareness of the legal
  and provenance findings in the research doc.
- **User action required:** the user supplies scrubbed PDF fixtures
  (3–5 statements covering simple / FX / multi-page / locale-shift /
  SEPA-mandate cases) and optionally one scrubbed CSV export per N26
  tier they use. The follow-up PDF implementation issue is blocked on
  the fixtures.
- **Dependency footprint:** one new MIT dependency (`pdfplumber`,
  which transitively pulls `pdfminer.six`, `Pillow`, `pypdfium2` —
  all MIT-compatible, no ML / OCR footprint).
- **Cross-cutting type change:** one new `SourceFormat` enum value
  (`PDF`) is the only change outside `providers/`. Any code that
  pattern-matches `SourceFormat` exhaustively will need to be
  updated in the follow-up implementation issue — a trivial change
  because the only existing match-sites are inside the providers
  package itself.
- **Live-write safety charter alignment:** this decision removes the
  live-rig path entirely, which keeps the project well clear of the
  safety charter's concerns for N26 ingest. No special charter
  addendum is required.

## Blockers returned to the user

- **The N26 Android T&C question has been resolved NEGATIVE in this
  ADR** — Option B is rejected on legal grounds as flagged in the
  research doc. This is a research finding, not an open blocker. If
  the user wishes to override this finding, the override MUST be
  explicit and written, and the follow-up Option B implementation
  issue MUST enforce the §R3 hostile-probe checklist as a hard gate
  before any code lands.
- **Fixture-supply blocker (soft):** the follow-up
  `PdfN26Provider` implementation issue is blocked on the user
  supplying scrubbed PDF fixtures. The PM can open the issue with
  the fixture requirement stated in the acceptance criteria.

## Review status

Formal review now lives in the corresponding audit artifact rather than
inside this ADR. That review covers the original issue acceptance
criteria, the unresolved PR #136 threads, and current-main mandate
alignment.
