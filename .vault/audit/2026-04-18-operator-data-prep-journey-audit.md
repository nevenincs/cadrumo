---
tags:
  - "#audit"
  - "#kent-data-prep-journey"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-17-export-first-adr]]"
---

# kent-data-prep-journey-audit

Third Kent audit. Prior audits covered **first-file journey** (twenty walls, onboarding → export) and **revise/review** (twenty walls, amendments + pipeline observability + structured review). This one drills into the phase **between** "Kent sits down to do his taxes" and "Kent has a computable draft." The ingest, invoice handling, classification, enrichment, VAT, proportionality, and deductibility layer — the T1→T5 span of the Transaction Data Pipeline — as Kent experiences it.

The single biggest finding is not another missing command. It is a **structural mismatch between data-model excellence and CLI reach**. The pydantic layer is impressively ambitious: 39 spending categories with legal citations, 17 VAT categories with regulatory metadata, a typed proportionality system for usage ratios and statutory caps, strict Spanish NIF validation, IVA arithmetic cross-checks. Almost none of it is reachable by Kent through the CLI. He can *browse* the taxonomy. He cannot *apply* it.

---

## who is Kent this session

Same Kent as the first two audits. British autónomo in Málaga, six years self-employed, remote work for UK + EU clients. For this session assume:

- Clean tool install (the first-file audit's onboarding walls notionally closed)
- Bank statements ready to export: BBVA EUR, Wise EUR, Wise GBP
- Invoices saved in Gmail (client PDFs) and Google Drive (supplier PDFs)
- Phone photos of parking / meal receipts
- Cuota de autónomos (Seguridad Social) €312/month, direct debit BBVA
- Home office: 15 m² of a 70 m² apartment (21% ratio)
- Quarter-end mindset: "I want to file Modelo 130 for Q1 2026"

Kent is not a tax expert. He knows the concepts — income, expenses, IVA, deductible, proportional — not the machinery: casilla codes, BOE Ordenes, autoliquidación rectificativa, artículo 30 LIRPF. He wants the tool to know.

---

## the session, scene by scene

### scene 1 — "it's time"

Kent opens a terminal. `aeat deadlines next` tells him Modelo 130 Q1 is due April 20. `aeat workflow next` seems like the entry point, but he has been burned before by running it too early, so he thinks first.

`aeat --help` lists top-level groups: `setup`, `doctor`, `bootstrap`, `deadlines`, `modelos`, `financial`, `submission`, `workflow`. He knows `financial` is where his data goes.

`aeat financial --help` shows three subgroups: `ingest`, `txs`, `invoices`. No ordering. No "start here" hint. No description of what the *workflow* is. `docs/getting-started.md` jumps straight from `aeat setup` to `aeat workflow next`, silently assuming the T1→T5 pipeline is populated.

★ **DP1 — No "start here" surface for data preparation.** There is no `aeat financial prepare --modelo 130 --period 2026Q1` that says "here are the six things to do, in order, before you can compute this filing." README, getting-started, and the CLI help are all silent on the data-prep phase. Kent has to guess the right ordering of `ingest` → invoices → classification → category assignment → verification.

### scene 2 — "what do I even need?"

Before he can ingest anything, Kent wants to know what the system expects. For Q1 2026 Modelo 130: three months of bank data? Every bank account? Just the business one? Only income, or also expenses? Invoices matter only for IVA modelos (303/390), or for 130 too?

He searches the CLI for a checklist command. None exists. Kent has to derive the input list from his own tax knowledge.

★ **DP2 — No per-period, per-modelo data-inventory checklist.** No `aeat financial requires --modelo 130 --period 2026Q1` emitting: "1. bank statement(s) covering 2026-01-01 through 2026-03-31, 2. invoices issued in this period, 3. received invoices for deductible expense categories X/Y/Z, 4. your Seguridad Social cuota for these three months, 5. your home-office ratio if claiming utilities." Without this, Kent can't even start preparing.

### scene 3 — the bank export

Kent logs into BBVA, exports the Q1 movements as `bbva_2026q1.csv`. He runs:

```
aeat financial ingest bbva_2026q1.csv
```

Terminal scrolls 247 `RawTransaction` JSON records past his eyes. The command completes. He runs `aeat financial txs list` — empty catalogue.

★ **DP3 — `aeat financial ingest` does not persist.** The command parses the CSV and prints the records to stdout, then exits. There is no `--persist` flag. The catalogue stays empty. Kent has to write a Python script to push the records into `TransactionCatalogue` — which is impossible for a non-developer autónomo.

(This is wall #14 from the first-file audit, already tracked as [#216](https://github.com/wgergely/aeat/issues/216). Restating because it is the load-bearing blocker for this entire scene onwards. Every data-prep wall downstream is moot until this closes.)

Assume, for the rest of the scenes, that #216 ships and `aeat financial ingest --persist` works.

### scene 4 — the invoice problem

Kent has 23 PDF invoices for Q1: eight he issued to his UK client, four to a Spanish client, eleven he received from suppliers. `aeat financial invoices list` — empty catalogue.

`aeat financial invoices --help`: **`list`, `show`, `link`, `reconcile`, `verify`, `unmatched`**. No `add`. No `ingest`. No `parse`. No `from-pdf`. No `create`.

Kent opens one of his PDF invoices. He sees: invoice number, issue date, supplier NIF, line items, IVA rate, base imponible, IVA importe, total. The `Invoice` pydantic model requires all of these fields plus a `SpendingCategory` per line. **To populate the catalogue, Kent must hand-author a JSON object for each of the 23 invoices** — every line, every IVA rate, every counterparty NIF, every cross-check amount. That is impossible for a real user.

★ **DP4 — There is no path from a PDF invoice to an `Invoice` record.** The `Invoice` pydantic model is Spanish-regulatory excellent (NIF/NIE/CIF checksum validation, IVA arithmetic reconciliation, strict counterparty country codes, 17 VAT categories with per-rule triggers). But no ingestion mechanism surfaces it: no PDF OCR, no LLM extraction, no CSV/XLSX import, no interactive `aeat financial invoices add` wizard. The Invoice catalogue is an ambitious empty room.

### scene 5 — the "sources" that aren't wired

Kent notices `AttachmentSource` enum values: `LOCAL_FILE`, `GMAIL`, `GOOGLE_DRIVE`, `URL`, `INLINE`. That looks promising — Kent's invoices live in Gmail, receipts in Drive. Does `aeat attachments` fetch from Gmail?

He runs `aeat attachments --help`. Three commands: `add`, `list`, `show`. `add` takes a local PATH. **Nothing fetches from Gmail or Drive.** The source enum values exist but no code produces attachments from those sources.

★ **DP5 — `GMAIL` / `GOOGLE_DRIVE` attachment sources are enum-only; no fetcher exists.** The Google Workspace MCP layer exists; `aeat drive` provides read operations; but nothing wires "pull all attachments labelled `invoices-q1`" from Gmail or "browse Drive folder X for receipts" into the attachment pipeline. Kent downloads each PDF manually and runs `aeat attachments add` one at a time.

### scene 6 — classification discovers its limits

Assume Kent has written a glue script to load his 247 transactions into the catalogue (the ones who can — a filter this audit should not have to apply in 2026). Now `aeat financial txs list --unclassified` shows 247 rows.

Kent picks the €42 Wise payment to Digital Ocean:

```
aeat financial txs classify tx-abc123 --as BUSINESS
```

It works. `business_classification = BUSINESS`. `classified_by = "manual"`. `classified_at = now()`.

Then he notices something is missing. This is cloud hosting — the `software_suscripcion` category. Where does he set that?

He re-reads `aeat financial txs classify --help`. Flags: `--as`, `--pct`. No `--category`. No `--category-id`. No `--spending-category`.

He greps the source. `Transaction.category_id` exists as a field on the model. `aeat financial txs classify` *does not touch it*. The only way to set `category_id` from the CLI is — there is none.

★ **DP6 — `aeat financial txs classify` cannot assign a `SpendingCategory`.** The 39-category taxonomy is unreachable from the classify command. `Transaction.category_id` is a field the data model defines and the CLI cannot set. Every downstream concern that needs a category — casilla aggregation, proportionality, deductibility, VAT classification — has nothing to bind to. This is the single largest hidden wall in the data-prep phase.

Without per-transaction category assignment, `aeat categories casillas MODELO_130` (which shows the category→casilla mapping) is a museum exhibit.

### scene 7 — proportionality, three flavours, one confusion

Kent has a €45 electricity bill. Home office, 21% business. He wants to record "21% of this is deductible."

**Three proportionality concepts exist in the codebase**, and Kent the user sees them as one question ("how much of this bill counts?"):

1. **Per-transaction business split.** `Transaction.business_classification = MIXED`, `business_pct = Decimal("0.21")`. Settable via `aeat financial txs classify --as MIXED --pct 0.21`. Correct surface for "this specific transaction is 21% business."

2. **Per-category proportionality rule.** `ProportionalityRule` on `CategoryProfile`. For `suministros_home_office_luz` the rule is `USAGE_RATIO_HOME_AREA` with `default_ratio`. A category-level default. Settable nowhere via CLI.

3. **Per-regulation VAT deductibility.** `VATRegulation.iva_treatment` and `requires_reverse_charge`. Whether the IVA portion of the expense is reclaimable. Surfaced read-only via `aeat vat show`.

These three concepts together answer Kent's question. The CLI exposes exactly one of them (#1) and makes Kent believe that is the whole picture.

★ **DP7 — No place to configure a user's usage ratios.** Kent's 21% home-office ratio is his — not a default for every autónomo. `CategoryProfile.proportionality.default_ratio` is a statutory default. There is no `aeat categories set-ratio suministros_home_office_luz --ratio 0.21` that persists Kent's own coefficient to a profile. He'd have to manually set `--pct 0.21` on every home-utility transaction he classifies as MIXED.

★ **DP8 — Three proportionality concepts are conflated in the user-experience and separated in the code.** Kent thinks "this €45 electricity bill is 21% business and my share of the IVA is deductible." The code has three models, three storage locations, and zero unified surface that renders the combined answer for a single transaction.

### scene 8 — VAT classification, engine without a wheel

Kent has a €89 invoice from a UK hosting provider. Post-Brexit this is `IMPORT_THIRD_COUNTRY` or (if the supplier treats him as an EU business customer) reverse-charge treatment. He doesn't know which.

The tool *has* the answer. `src/aeat/domain/financial/vat/_classification.py` is a 15-rule decision table that takes `VATClassificationCriteria` (counterparty country, VAT ID presence, intra-EU flags, supply type) and returns one of the 17 `VATCategory` values. A pure function. Typed. Tested (presumably).

**It is not wired to any CLI command.** Kent cannot run `aeat vat classify --from-invoice inv-xyz` or `aeat vat classify --counterparty-country GB --counterparty-has-vat-id --supply-type services`. He can browse the catalogue (`aeat vat categories list`) and read the regulations (`aeat vat show DOMESTIC_GENERAL_21`), but he cannot ask the engine for a verdict.

★ **DP9 — The VAT classification engine is a pure function with no CLI wiring.** The engine exists, works, has its decision table fully encoded — and no command surfaces it. A correct Spanish-VAT-compliant auto-classifier is sitting inside the repo, unused.

### scene 9 — "rule:<id>" ghosts

Kent notices `classified_by` accepts the shape `"rule:<rule-id>"`. He thinks: "aha, a rule engine!" He looks for `aeat financial rules list` or similar. Nothing.

Grepping the codebase: `_Rule` NamedTuples exist for *VAT classification*, *AEAT inbox notification classification*, and *deadline applicability*. None exists for *transaction business-classification or category assignment*. The `"rule:<id>"` shape is validated but has no producer. It is a promise the data model makes that the system does not keep.

★ **DP10 — `classified_by = "rule:<id>"` is a validated shape with no producer.** No rule engine exists for automatic transaction classification. No rule authoring surface exists for Kent. This is the single highest-leverage feature absent from the data-prep phase — auto-classify 200+ transactions via a handful of Kent-authored counterparty / amount / narrative rules would collapse his per-quarter manual work by an order of magnitude.

### scene 10 — period scoping

Kent's catalogue now carries transactions from all of 2025 + Q1 2026. He wants to focus on Q1 2026:

```
aeat financial txs list --period 2026Q1
```

Error. `aeat financial txs list` has one flag: `--unclassified`. No date range. No quarter. No year. No period.

★ **DP11 — No period scoping on the transaction catalogue CLI.** The catalogue is a flat map. Queries do not understand time. Kent has no way to say "show me Q1 2026 only" or "confirm no Q4 2025 transactions are pending classification." He must read the JSON directly or write a script.

### scene 11 — "am I ready?"

Kent has spent two hours. He thinks he's close. He wants to know.

He runs `aeat financial txs list --unclassified` → 14 rows. `aeat financial invoices verify` → clean. `aeat financial invoices unmatched` → 3 invoices without linked transactions. He mentally joins these three facts.

**There is no single readiness command.** There is no "Q1 2026 is 94% prepared; 14 transactions awaiting classification; 3 invoices unmatched; 2 categories unassigned; click here to continue." He cannot tell whether "done" is close or far.

★ **DP12 — No per-period readiness report.** `aeat pipeline status --period 2026Q1` is tracked as a future surface in EPIC [#238](https://github.com/wgergely/aeat/issues/238), not built. Until it ships, Kent joins disparate queries in his head.

### scene 12 — deductibility

Kent classifies his €45 electricity bill as MIXED, 21% business, category `suministros_home_office_luz`. He asks: how much of the €45 do I get to deduct? How much of the IVA can I reclaim?

There is no command that answers this.

The `ProportionalityRule` on `suministros_home_office_luz` is `USAGE_RATIO_HOME_AREA`. The default ratio is set in the category registry. The VAT treatment is `DOMESTIC_GENERAL_21` with 21% IVA. Composing these facts produces: deductible income-tax expense = €45 × 0.21 = €9.45; deductible IVA = (€45 × 21/121) × 0.21 = ~€1.64.

No code in `src/aeat/domain/financial/` produces this composition. No `Transaction.deductible_amount`. No `Transaction.deductible_iva`. No `aeat financial compute-deductible` command.

★ **DP13 — No service computes deductible amounts from proportionality + VAT rules.** The rules exist as data; the arithmetic is unimplemented. The T6 aggregation step ([#218](https://github.com/wgergely/aeat/issues/218)) is supposed to take classified+categorised transactions and produce casilla-level numbers — but DP13 is a prerequisite: without knowing what each transaction's deductible portion *is*, aggregation has nothing to sum.

### scene 13 — the simple case fails anyway

Kent steps back to the simplest possible case: his monthly Seguridad Social cuota, €312, direct debit from BBVA. This is 100% deductible. Category `cuotas_autonomos_ss`. Proportionality `FULL_DEDUCTIBLE` (no ratio math).

Even here the pipeline fails:

1. Ingest: blocked by DP3 (#216), pretend resolved.
2. Classify as BUSINESS: works.
3. Assign category `cuotas_autonomos_ss`: **blocked by DP6 (no CLI flag).**
4. Apply proportionality (FULL_DEDUCTIBLE): would be trivial but depends on (3).
5. Aggregate to Modelo 130 casilla: depends on (3) and (4).

Even the trivial case — a fully-deductible, fixed-amount recurring expense — cannot traverse the data-prep pipeline without writing Python.

---

## the thirteen walls, one-liner each

| # | Wall | Tracked |
|---|---|---|
| DP1 | No "start here" data-prep entry-point | [#260](https://github.com/wgergely/aeat/issues/260) — `aeat financial prepare` walkthrough |
| DP2 | No per-period, per-modelo data-inventory checklist | [#261](https://github.com/wgergely/aeat/issues/261) — `aeat financial requires` |
| DP3 | `aeat financial ingest` doesn't persist | [#216](https://github.com/wgergely/aeat/issues/216) |
| DP4 | No path from PDF invoice to `Invoice` record | [#254](https://github.com/wgergely/aeat/issues/254) — EPIC: PDF invoice ingestion (LLM + wizard + bulk) |
| DP5 | `GMAIL` / `GOOGLE_DRIVE` sources are enum-only; no fetcher | [#262](https://github.com/wgergely/aeat/issues/262) — Gmail + Drive invoice fetcher |
| DP6 | `classify` cannot assign a `SpendingCategory` | [#266](https://github.com/wgergely/aeat/issues/266) **CLOSED** (PR #288) |
| DP7 | No place to configure user-specific usage ratios | [#259](https://github.com/wgergely/aeat/issues/259) — profile usage ratios |
| DP8 | Three proportionality concepts conflated in UX | Subsumed by [#257](https://github.com/wgergely/aeat/issues/257) — its `proportionality_applied` + `vat_treatment_applied` + `trace` fields on `aeat financial txs show` *are* the unified surface |
| DP9 | VAT classification engine unwired to CLI | [#255](https://github.com/wgergely/aeat/issues/255) — wire `classify_vat` to CLI |
| DP10 | `classified_by = "rule:<id>"` has no producer | [#256](https://github.com/wgergely/aeat/issues/256) — EPIC: rule-based auto-classify |
| DP11 | No period scoping on catalogue CLI | [#263](https://github.com/wgergely/aeat/issues/263) — `aeat financial txs list --period` |
| DP12 | No per-period readiness report | [#238](https://github.com/wgergely/aeat/issues/238) — pipeline health dashboard |
| DP13 | No deductibility computation service | [#257](https://github.com/wgergely/aeat/issues/257) — `compute_deductible` service |

**All thirteen walls are tracked.** Nine new issues (#254–#263) were filed between this audit's original draft and its publication and close the "untracked" gaps the audit had flagged. DP8's "zero unified surface" concern is already answered by #257's `aeat financial txs show` design (explicit composition trace + rule + VAT treatment alongside the numeric answer). DP6 (#266) landed via PR #288 on the same day this audit was written — the "single largest hidden wall" is already closed.

This audit therefore ships as a **journey narrative** and a **structural finding** (data-model excellence vs CLI reach) — not as a backlog-seeding exercise. The walls and Kent's experience of them remain the authoritative reference even though each numbered pointer now lands on a tracked issue rather than an unfiled gap.

---

## the single structural finding

The repo ships an impressively ambitious data layer and an impressively stubbed-out CLI reach into it. Specifically:

- **39 spending categories** with trilingual labels, legal citations, proportionality rules, and per-modelo casilla mappings — browsable via `aeat categories`, **unassignable via `aeat financial txs classify`**
- **17 VAT categories** with regulatory metadata and a 15-rule classification engine — browsable via `aeat vat`, **unreachable from the transaction catalogue or invoice ingestion**
- **6 proportionality kinds** including usage ratios, statutory caps, fixed percentages — encoded in `ProportionalityRule`, **not applied anywhere in runtime code that Kent touches**
- **17 attachment kinds** and 5 sources (Gmail, Drive, URL, local, inline) — schema-complete, **sources partial to none in the fetcher layer**
- **Invoice model** with Spanish NIF validation and IVA arithmetic — populated by **hand-authoring JSON**

The gap is systematic. Someone built the data layer with great care and then stopped before the CLI could surface it. Kent cannot *use* what the repo *knows*.

---

## what the tool does well here (keep)

- The **category taxonomy** itself — 39 entries with legal citations and proportionality rules — is a genuine tax-compliance asset. When the CLI catches up, this data becomes the difference between "a tax tool" and "an autónomo-specific tool that knows Spanish law."
- The **VAT classification decision table** is correct-looking and complete. Wiring it is mechanical work; the hard thinking is done.
- The **strict `Invoice` model** (NIF checksum, IVA cross-check, 17 VAT categories) is regulatorily grounded. When ingestion exists, invoices will land in compliant form by construction.
- The **attachment content-addressed blob store** handles provenance and dedupe cleanly; it is ready to receive PDFs once a fetcher lands.

---

## roadmap implications

This section was drafted before the follow-up issues (#254–#263, #266) were filed. Retained here as the audit's historical proposals — every proposal has since been filed or closed:

- **DP6** — *Kent assigns a spending category.* Filed as [#266](https://github.com/wgergely/aeat/issues/266), closed by PR [#288](https://github.com/wgergely/aeat/pull/288).
- **DP4** — *Kent ingests PDF invoices end-to-end.* Filed as EPIC [#254](https://github.com/wgergely/aeat/issues/254).
- **DP9** — *Kent asks the tool to classify VAT.* Filed as [#255](https://github.com/wgergely/aeat/issues/255).
- **DP10** — *Kent writes rules that auto-classify his transactions.* Filed as EPIC [#256](https://github.com/wgergely/aeat/issues/256).
- **DP13** — *Kent sees how much of each expense is deductible.* Filed as [#257](https://github.com/wgergely/aeat/issues/257); also covers DP8's "unified surface" concern via `proportionality_applied + vat_treatment_applied + trace` on `aeat financial txs show`.
- **DP7** — *Kent configures his own usage ratios.* Filed as [#259](https://github.com/wgergely/aeat/issues/259).
- **DP1** — *`aeat financial prepare` walkthrough.* Filed as [#260](https://github.com/wgergely/aeat/issues/260).
- **DP2** — *`aeat financial requires` checklist.* Filed as [#261](https://github.com/wgergely/aeat/issues/261).
- **DP5** — *Gmail / Drive attachment fetcher.* Filed as [#262](https://github.com/wgergely/aeat/issues/262).
- **DP11** — *Period scoping on catalogue CLI.* Filed as [#263](https://github.com/wgergely/aeat/issues/263).

### refinements to existing tracked issues

- **[#217](https://github.com/wgergely/aeat/issues/217) bulk classify**: scope should include `--category` assignment (now covered by #266) and confirm rule format covers category + VAT category + proportionality override.
- **[#218](https://github.com/wgergely/aeat/issues/218) T6 aggregation**: explicit dependency on DP6 (#266, closed) and DP13 (#257). T6 cannot sum until per-transaction category + deductible amounts exist.
- **[#238](https://github.com/wgergely/aeat/issues/238) pipeline status**: acceptance should include categorisation coverage + deductibility-computation coverage, not only unclassified count.

---

## verdict

Kent cannot, today, traverse the data-prep phase from "here is my BBVA CSV" to "here is a validated and categorised catalogue of Q1 2026 business expenses with computed deductible portions" without writing custom Python at three separate points (T1→T2 bridge, per-transaction category assignment, proportionality + VAT composition into deductible amounts). The T1→T6 pipeline as a user-facing product exists in its data model and is near-absent in its CLI reach. The first-file audit flagged the start and end of this phase; this audit inventories the twelve specific in-between walls.

The strategic correction is small in aggregate effort and large in Kent-value: ten issues (mix of new and scoped) unlock the middle of the pipeline. Wire what the data model already knows.
