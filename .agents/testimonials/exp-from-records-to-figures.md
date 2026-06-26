# Testimonial — docs/explanation/from-records-to-figures.md

- **Doc path:** `docs/explanation/from-records-to-figures.md`
- **Persona:** A curious user reading this conceptual EXPLANATION page to understand how a bank movement becomes a figure in a numbered box on a tax form, and checking that every claim matches how the app actually behaves.
- **Date:** 2026-06-18

This is an explanation (conceptual) page, not a command tutorial — it prints no
commands. Verification therefore = (1) claim-by-claim check against the live CLI
and the registry data, (2) cross-link / glossary-term resolution, (3) judging the
narrative against known implementation behaviour (ledger→casilla aggregation,
bindings, legal provenance, period windowing, the mixed-cost split).

## Walkthrough (claim-by-claim verification)

### Claim 1 — "modelos … made of casillas" and the `{term}` glossary refs
- **Expected:** `{term}\`AEAT\`` and `{term}\`casillas <casilla>\`` resolve to real,
  rendered glossary entries.
- **Actual:** `src/aeat/_data/terminology/concepts/aeat.toml` and `casilla.toml`
  both exist and both carry `lifecycle = "approved"` (so they render in the
  generated glossary and Pagefind search per `glossary-concepts-are-taxpayer-facing`).
- **Verdict:** OK.

### Claim 2 — A bank movement is "just a date and an amount"; tax meaning is added
- **Expected:** raw imported rows carry no tax classification until the user adds it.
- **Actual:** confirmed against the ledger model — `RawTransaction` carries the
  movement; classification (`business_classification`, `category_id`, `taxable_base`,
  `iva_rate`, `iva_amount`) is layered on afterward (`_ledger_read_cli.py:820`
  readiness line enumerates exactly these added fields).
- **Verdict:** OK.

### Claim 3 — A tax-ready record carries (a) business/personal/mixed decision,
(b) a category, (c) a business-vs-personal split for mixed costs
- **Expected:** these three are real fields/decisions in the app.
- **Actual:** `business_classification` (BUSINESS/PERSONAL/MIXED), `category_id`
  (categories registry `domain/categories/_registry.py`), and business-share ratios
  (`application/ledger/_ratios.py`, `domain/usage_ratios/_model.py`) all exist.
- **Verdict:** OK. Link `[Classify transactions](../how-to/classify-transactions.md)`
  resolves (file exists).

### Claim 4 — Three ways to split a mixed cost: per-record %, category default,
profile-fact ratio
- **Expected:** all three split sources implemented.
- **Actual:** all three are grounded: per-record proportion + a category-level
  default share + a derived ratio from registration facts
  (`domain/usage_ratios/_model.py`, `application/ledger/_ratios.py`,
  `domain/renta/_ledger_expenses.py`). The narrative ("the size of a registered
  home office against the size of your home") matches the usage-ratio fact model.
- **Verdict:** OK — strongest-matched section; accurately describes the implementation.

### Claim 5 — Readiness check flags missing decision / category / IVA base|amount|rate
/ missing split reference / unconvertible currency, and "changes nothing"
- **Expected:** a real readiness surface that reports these without mutating.
- **Actual:** `aeat app modelo readiness` exists (help: "Informa de si el perfil
  activo está listo para presentar…"; read-only). The ledger readiness issue line
  (`_ledger_read_cli.py:820`) reports `classification`, `category_id`,
  `taxable_base`, `iva_rate`, `iva_amount`, plus `reason`/`detail` — a 1:1 match for
  the page's first four bullets. Currency-conversion + split-reference flags are
  grounded in the FX/ratio machinery.
- **Verdict:** OK. NOTE (DOC, minor): the page sends readiness to the
  "readiness section of [Import bank statements]" how-to, but the actual top-level
  command is `aeat app modelo readiness`. Acceptable for a conceptual page (it links
  to a how-to, not a command), but the readiness verb living under `modelo` rather
  than under import is a slight surprise vs. where the link points.

### Claim 6 — "A calculation is always for one form, one year, one period"; the
period becomes a start/end window keeping only in-window records; "1Q sees Jan–Mar,
a March filing sees only March"
- **Expected:** period tokens (quarter/month/year) resolve to date windows.
- **Actual:** confirmed. `readiness --period` help: "0A anual, 1T-4T trimestres,
  01-12 meses". This is exactly quarter/month/year, and `Period.contains()` is the
  single boundary authority (`period-filter-single-boundary-authority` rule). Links
  `[choose-modelo]` and `[filing-periods]` both resolve.
- **Verdict:** OK.

### Claim 7 — "The tool reads … your tax-ready records and your profile … applies
the rules the agency publishes … which input feeds which box … add, subtract, apply
rates … total income minus deductible costs … a rate applied to reach tax due"
- **Expected:** boxes are routed and computed from formulas, not hand-wired.
- **Actual:** `aeat app modelo formulas 130` shows exactly this:
  `03 = 01,02` (rendimiento neto = ingresos − gastos),
  `04 = 03, irpf.direct_estimation_fractional_payment_rate` (a rate applied),
  boxes feeding boxes up to `19` (resultado final). `casillas 130` shows each box's
  `input` kind: `bound` (routed from records), `manual` (entered), `computed`
  (derived). This is a precise, accurate description of the engine.
- **Verdict:** OK — narrative faithfully matches the formula/binding/casilla model.

### Claim 8 — "You don't wire any of this by hand"
- **Actual:** routing is declared in the registry (bindings + formulas), not by the
  user. `aeat app modelo bindings` is a real subgroup. Matches.
- **Verdict:** OK.

### Claim 9 — Every figure keeps the rule + the law article + the manual section;
input figures carry the same trail
- **Expected:** legal_refs (law) + source_refs (manual) + formula_id (rule) on every
  casilla, including manual inputs.
- **Actual:** registry casilla defs carry e.g.
  `legal_refs = ["rd-439-2007:art-110", "ley-35-2006:art-99", …]` (law articles) and
  `source_refs = ["aeat-modelo-130-instructions", "aeat-dr-130-2019-v12"]` (the
  manual/official source). Even `input_kind = "manual"` boxes carry the same
  `legal_refs`/`source_refs`. The `formula_id` is the rule. This matches the page's
  three-part trail precisely and aligns with `aeat-calculation-grounding`.
- **Verdict:** OK — accurate, not overstated.

### Claim 10 — "Nothing is a black box" / justify every number to an inspector
- **Actual:** consistent with grounding rules + bundled evidence
  (`ledger-derived-revisions-bundle-evidence`). Conceptually accurate.
- **Verdict:** OK.

### Claim 11 — "Where this sits": links to overview (`index.md`) and next stage
(`editing-and-verifying.md`)
- **Actual:** both `docs/explanation/index.md` and
  `docs/explanation/editing-and-verifying.md` exist.
- **Verdict:** OK.

### Cross-reference to the 303 attribution step (brief-specified known finding)
- The page is generic across modelos; it does not claim a 303-specific attribution
  step, so there is nothing to contradict. The "rules add, subtract, apply rates"
  abstraction holds for 303's attribution/prorrata as it does for 130. No
  overstatement found.

## Findings

1. **[MINOR] [DOC]** Readiness command location vs. where the link points. The page
   routes the reader to "the readiness section of [Import bank statements]" but the
   live read-only verb is `aeat app modelo readiness` (under `modelo`, requiring
   `--modelo --revision-id --year`). For a conceptual page this is tolerable, but a
   reader who clicks through expecting an import-time check may be mildly surprised
   the canonical verb sits under `modelo`. *Suggested fix:* ensure the linked how-to
   actually surfaces `aeat app modelo readiness` (or a wrapper), or point at the
   modelo-readiness how-to if one exists.

2. **[NIT] [DOC]** No mention that a master-key passphrase is required. Per the
   brief, a page that never warns of this would block a naive non-interactive user.
   This is an *explanation* page that prints no commands, so the omission is
   defensible here — the warning belongs on the how-to pages it links to. Flagged
   only for completeness; not actionable on this page.

3. **[NIT] [DOC]** Spanish/English friction. All CLI help renders in Spanish (e.g.
   "Informa de si el perfil activo está listo…") while the docs are English. The page
   itself doesn't expose this (no commands), so no concrete trip — noting the
   ecosystem friction only.

No BLOCKER or MAJOR findings. No factual/technical claim on this page was found to
overstate or misdescribe the implementation.

## Testimonial

As a curious reader I came away genuinely well-served: the page promised to explain
where the numbers come from, and every load-bearing claim it made checked out against
the actual engine — boxes really are computed from declared formulas (`03 = 01 − 02`,
a rate applied at `04`), records really do carry the three things it lists, and every
figure really does keep its law article and manual reference attached, manual inputs
included. The three-way mixed-cost split and the period→date-window explanation were
especially accurate. The only place I half-tripped was the readiness pointer — the
real verb lives under `aeat app modelo readiness`, not obviously in the import flow
the link suggests — but that's a signpost nit, not a broken promise. For a conceptual
page, it set expectations honestly and the app delivered what it described.

## Scorecard

- **Doc clarity:** 5/5
- **App capability (as described):** 5/5
- **Findings by severity:** BLOCKER 0 · MAJOR 0 · MINOR 1 · NIT 2
