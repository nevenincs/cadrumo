---
tags:
  - '#research'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - '[[2026-05-30-docs-architecture-adr]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
  - '[[2026-06-08-filing-architecture-docs-adr]]'
---
# `docs-lifecycle-tutorials` research: `lifecycle tutorials for the taxpayer-question-driven user documentation rebuild`

This research grounds the `docs-lifecycle-tutorials` feature: rebuilding the
user-facing tutorial surface around the questions a taxpayer actually asks
("How do I file my Modelo 130?", "How do I file my Modelo 349?", "How do I do
my IVA calculations?", "How do I get my expenses and invoices into the
application so I can calculate my modelo?"), replacing the current single,
dense, Modelo-130-only tutorial with a small number of LIFECYCLE tutorials
that walk a taxpayer through a whole fiscal-year pipeline. It carries forward
a prior documentation-structure survey (phase 1 of this campaign) and adds a
CLI-verified gap analysis and two tutorial wireframes per the operator's
phase-2 ruling.

## Operator ruling (verbatim intent, phase 2)

- The docs-educational-surface ADR is not wrong; Diataxis stands.
  `architecture/` stays the developer surface.
- User documentation must be rebuilt around the questions taxpayers actually
  ask: "How do I file my Modelo 130?", "How do I file my Modelo 349?", "How
  do I do my IVA calculations?", "How do I get my business expenses and
  invoices into the application so I can calculate my modelo?"
- Existing tutorials are too dense and there are too few. The mandated shape
  is LIFECYCLE tutorials that take the user through a whole pipeline year.
  Minimum two: (1) the income-tax (IRPF) annual lifecycle, quarterly Modelo
  130 instalments through the annual Modelo 100 Renta; (2) the IVA lifecycle
  through one year, periodic Modelo 303 through the annual Modelo 390
  summary, and where Modelo 349 fits for intra-community operators.
- The docs-educational-surface ADR chartered the Tutorial quadrant as
  SINGULAR ("a single on-rails lesson"). Multiple lifecycle tutorials
  therefore need a small companion or amending ADR. This research grounds
  that ADR; the ADR itself is a later phase, not authored here.

## Findings

### 1. Phase-1 survey carried forward (documentation-structure baseline)

The phase-1 survey confirmed the taxonomy on disk is a genuine Diataxis set,
governed by two accepted ADRs, and found one real structural weakness the
operator's ruling now resolves directly: `docs/tutorials/index.md` is a
single, dense, Modelo-130-only walkthrough that duplicates roughly 80% of
`docs/how-to/quickstart.md` (same profile, same NIF, same two ledger rows,
same Modelo 130 for 2026/1T), and the Tutorial quadrant otherwise has no
other member. Full findings, preserved for continuity:

**Inventory and taxonomy** (`docs/` tree, excluding `_build`, `_generated`,
`api/`, `conf.py`):

- `docs/index.md` — landing page, route grid of 6 cards into `how-to/` and
  `tutorials/`.
- `docs/how-to/` — 29 files plus index; task-scoped imperative recipes
  covering onboarding, profile setup, censo, applicability, calendar,
  periods, notifications, transactions, classification, invoices, evidence,
  review queue, Modelo 036, calculation review, Google Sheets review, filing
  workflow, Modelo 303, Modelo 390, prorrata, LLM classification (3 pages),
  agent connection, data protection, troubleshooting, filing at AEAT,
  reconciliation, justificante receipts.
- `docs/tutorials/` — `index.md` only; one complete, fully worked ~250-line
  tutorial ("Build your first Modelo 130 filing"), not a stub.
- `docs/explanation/` — 5 pages plus index ("Understanding the AEAT
  pipeline" cluster): `from-records-to-figures.md`,
  `editing-and-verifying.md`, `building-on-earlier-filings.md`,
  `reviewing-and-exporting.md`, `recording-a-filing-and-the-boundary.md`.
  Every page links out to the relevant how-to guide and back to the shared
  index; none carries an executable command.
- `docs/architecture/index.md` — a ~325-line developer-facing codebase map
  (hexagonal layers, registry pipeline, modelo lifecycle, persistence and
  safety boundary), a genuinely separate audience from the taxpayer-facing
  surfaces. `docs/architecture.md` is a one-line orphan redirect into it.
- Stray root-level files worth a follow-up check against the docs-hygiene
  clause in the architecture ADR: `ADRS.md`, `HARNESS-USERDOCS-KICKOFF-BRIEF.md`,
  `USERDOCS-KICKOFF-BRIEF.md` (not opened in phase 1; names suggest
  project-management metadata that should not live in the documentation
  tree).

**Two-segment hypothesis (phase-1 verdict, still standing):** the operator's
original framing (actionable vs. detached conceptual) was directionally
right but needed a correction: the real split is `how-to/` plus `tutorials/`
(actionable) versus `explanation/` (conceptual), with `architecture/` as a
third, developer-only segment that should not be folded into either
taxpayer bucket. `explanation/` is not detached — every page links into its
relevant how-to guide and states plainly that it is background reading, for
example `docs/explanation/from-records-to-figures.md`: "This is background
reading. When you're ready to actually do each step, follow the links to
the how-to guides." The phase-2 operator ruling confirms this reading and
narrows the actionable work to the Tutorial quadrant specifically, leaving
`explanation/` as chartered.

**Governing ADRs (both accepted, both still binding):**

- `2026-05-30-docs-architecture-adr` sets the top-level four-surface
  taxonomy (repo-bootstrap markdown, in-source docstrings, generated API
  docs, deferred user-help) and the domain-driven-filenames constraint
  (clause 3a: the documentation tree "MUST NOT encode any
  documentation-framework or project-management metadata").
- `2026-06-01-docs-educational-surface-adr` is the ADR that actually
  created the Tutorial / How-to / Explanation split inside the deferred
  user-docs surface, as a disciplined Diataxis set. It states the cardinal
  failure mode explicitly: "The four documentation needs (Tutorial,
  How-to, Reference, Explanation) are kept strictly separate; mixing
  them — a how-to bloated with theory, a tutorial drifting into
  reference — is the cardinal failure mode." Its Implementation section
  charters the Tutorial quadrant as **singular**: "Tutorial — a single
  on-rails lesson taking a new operator through one modelo end to end
  (profile -> ledger import/classify/allocate -> `aeat app modelo work` ->
  `aeat app verify` -> export/borrador -> human files outside the app). One
  worked example, no decision points, no theory." It also mandates that
  every educational document is produced through the full
  `vaultspec-documentation` skill pipeline (wireframe, fresh-context
  refinement, context gathering, isolated drafting, technical review,
  zero-context editorial review) and that a single-source conformance gate
  parses educational docs and asserts every referenced `aeat ...` verb and
  fenced example resolves against the live CLI surface — the same
  discipline `operator-harness-cites-live-cli-surface` and
  `aeat-cli-pull-and-file-standard` apply elsewhere in the project.
- `2026-06-08-filing-architecture-docs-adr` mandates persona-driven
  tutorials with generalized identity terminology (NIF, CIF, DNI, NIE, NII)
  covering preparation, verification, and local filing, audited against
  live surfaces. This is compatible with, and does not block, a
  lifecycle-tutorial redesign.

**Why the singular-Tutorial charter needs an amending ADR, not a silent
violation:** the operator's ruling to ship a minimum of two lifecycle
tutorials directly contradicts the "one worked example... no decision
points" sentence in the accepted `2026-06-01-docs-educational-surface-adr`.
Per the project's own architecture-boundaries discipline, decisions are
superseded or amended explicitly, never silently overridden by landing
contradictory content. A small companion or amending ADR is therefore a
precondition for landing the lifecycle tutorials, not an optional
formality — this research exists to ground that ADR, which is authored in
the next phase after operator review of this document.

### 2. Gap analysis: modelo coverage versus how-to pages

`aeat app modelo list` enumerates roughly 80 registered modelos across
every tax domain (IVA, IRPF, IS, IRNR, censo, informative declarations,
special taxes). Most of that catalogue is `supported-model-level` for local
work-unit creation; a small number are `unsupported-local-work` by design
(Modelo 151 impatriados, Modelo 210 IRNR non-resident, Modelo 714 wealth
tax, Modelo 721 foreign virtual currencies) with an explicit refusal message
naming the legal basis and directing the taxpayer to file at the AEAT sede
directly.

The full ~80-modelo catalogue is not the right scope for a taxpayer-facing
how-to/tutorial backlog: most of those modelos are narrow, ad-hoc, or
professional-advisor-only surfaces (informative declarations for financial
institutions, DAC6/DAC7 cross-border reporting, special excise taxes). The
shipped agent-skill set is a better proxy for "the application actively
guides a taxpayer through this modelo end to end": it names 18 modelos with
a dedicated `aeat:preparar-modelo-NNN` skill plus `aeat:preparar-modelo-036`
(alta/modificacion/baja) — 100, 111, 115, 130, 131, 180, 190, 193, 200, 202,
303, 309, 322, 349, 353, 369, 390, plus 036. These are the modelos the
project already treats as first-class guided-preparation surfaces; a
taxpayer-question-driven how-to backlog should track this set, not the raw
registry list.

Cross-referencing that 18-modelo set against the existing modelo-specific
how-to pages (`docs/how-to/modelo-036.md`, `docs/how-to/modelo-303.md`,
`docs/how-to/modelo-390.md` — the only three that exist today) gives the
priority-ordered missing-page list:

**Tier 1 — named directly by the operator, or load-bearing for the two
mandated lifecycle tutorials:**

1. Modelo 130 (IRPF pago fraccionado, estimación directa) — quarterly,
   named explicitly by the operator; currently only covered by the dense
   `tutorials/index.md` walkthrough and `how-to/quickstart.md`, neither of
   which is a dedicated "how do I file Modelo 130" recipe in the same shape
   as `how-to/modelo-303.md`.
2. Modelo 100 (IRPF declaración anual, RENTA) — annual, named explicitly by
   the operator; no how-to page exists at all today. `explanation/building-
   on-earlier-filings.md` describes the annual-return concept in prose but
   has zero commands.
3. Modelo 349 (declaración recapitulativa de operaciones intracomunitarias)
   — named explicitly by the operator; no how-to page exists.
4. The expense/invoice-ingestion path — "how do I get my business expenses
   and invoices into the application so I can calculate my modelo" — named
   explicitly by the operator. This spans three existing how-to pages
   (`import-bank-statements.md`, `manage-invoices.md`, `ledger-evidence.md`)
   plus the `classify-transactions.md` page, so the gap here is not a
   missing page but a missing **synthesis** — no single page currently
   answers the compound question end to end (import, invoice recording,
   evidence attachment, classification, in one arc).

**Tier 2 — required for the two mandated lifecycle tutorials but not named
directly:**

5. Modelo 190 (resumen anual de retenciones del trabajo y actividades) —
   only relevant if the lifecycle tutorial's persona withholds retenciones;
   optional branch, not core path.
6. Modelo 111 / 115 / 180 / 193 — same withholding-branch caveat as above;
   lower priority unless the chosen persona is an employer or landlord.
7. Modelo 202 / 200 (IS pago fraccionado / IS anual) — only relevant if a
   `legal_entity` persona is added; the operator named IRPF and IVA
   lifecycles specifically, not IS, so this is explicitly out of scope for
   the two mandated tutorials but worth flagging as a plausible third
   lifecycle in a future wave.
8. The IVA-wallet balance/seed/correct workflow (`aeat app modelo
   iva-wallet balance / seed / correct / override`) — identified as a real
   gap in the phase-1 survey: currently documented only in prose in
   `explanation/building-on-earlier-filings.md`, with no how-to page,
   despite being load-bearing for the IVA lifecycle tutorial (a
   first-period IVA credit opening balance is exactly the kind of thing a
   taxpayer moving through a full fiscal year needs to set once and then
   understand the correction-refusal guard for).

**Tier 3 — present in the modelo-303/309/322/353/369/369-adjacent IVA
family, out of scope for the two mandated tutorials but worth noting for
completeness:** Modelo 309 (ad-hoc IVA), Modelo 322/353 (grupo de
entidades), Modelo 369 (OSS/IOSS) each have a preparer skill but no how-to
page. None of these are named by the operator and none are prerequisites
for the two mandated lifecycle tutorials; they are a plausible later wave.

**Recommended priority order for page authorship** (independent of the two
lifecycle tutorials, which are wireframed separately below): Modelo 130 →
Modelo 100 → Modelo 349 → the expense/invoice-ingestion synthesis page →
IVA-wallet how-to → the Tier 2 withholding pages only if the chosen
lifecycle persona needs them.

### 3. CLI surface verified live for the wireframes below

Every verb named in the wireframes in Finding 4 was confirmed against the
live CLI tree on this branch (`aeat app modelo --help`, `aeat app modelo
work --help`, `aeat app ledger --help`, `aeat app ledger invoice --help`,
`aeat app overview --help`, `aeat app modelo iva-wallet --help`, `aeat app
modelo reconcile --help`), per the `operator-harness-cites-live-cli-surface`
and `aeat-cli-pull-and-file-standard` discipline — no verb below is cited
from memory or from the existing docs prose.

Confirmed top-level surfaces relevant to both tutorials:

- `aeat app modelo work {create, calculate, verify, file, revisions,
  revision, observations, history, dependencies, wizard, amend,
  amend-wizard, compare-taxation}` — the shared filing-target lifecycle
  chain used identically by every modelo.
- `aeat app modelo {export, reconcile pull, reconcile file, reconcile
  history, iva-wallet balance, iva-wallet seed, iva-wallet correct,
  iva-wallet override, m036 alta/modificacion/baja, describe, casillas,
  requires, bindings}` — export, official-evidence reconciliation, and
  IVA-wallet state.
- `aeat app ledger {add, import, classify, allocate, invoice add/list/view,
  evidence add/list/view, attach, doclink, pull-folder, preflight, status,
  prorrata elect-general/elect-especial/declare-sector}` — the
  expense/invoice-ingestion surface both tutorials share.
- `aeat app overview {calendar, agenda, backlog, explain, prepare,
  pipeline, status}` — the calendar/readiness surface that should frame
  each lifecycle stage transition ("what is due now that the quarter has
  closed").

### 4. Two lifecycle tutorial wireframes (proposals only — not authored under `docs/` in this phase)

Both wireframes below share one taxpayer persona and one continuous
dataset across the fiscal year, rather than two disconnected personas, for
three reasons: (a) it mirrors how a real autónomo actually experiences the
year — IRPF and IVA obligations interleave on the same ledger, not on two
separate books; (b) it lets each tutorial cross-reference the other at the
quarter boundary without re-deriving setup from scratch; (c) it keeps the
persona/profile-creation step (name, NIF, activity, activity-start-date)
authored exactly once and referenced, rather than duplicated verbatim in
both tutorials the way `tutorials/index.md` and `how-to/quickstart.md`
duplicate it today. Recommendation for the amending ADR to confirm: **one
shared persona and one shared ledger dataset, two tutorial documents that
each walk a different modelo family over the same year.**

#### Wireframe A — the IRPF annual lifecycle (Modelo 130 quarterly through Modelo 100 annual)

Narrative arc across a fiscal year, one stage per quarter plus a close:

1. **Setup.** Create the taxpayer profile (`aeat config profile create`)
   with activity-start-date scoping out prior periods; record the first
   quarter's business income and expense rows (`aeat app ledger add`, or
   `aeat app ledger import` for a bank statement); classify them (`aeat app
   ledger classify`); attach an invoice or evidence document to at least
   one row (`aeat app ledger invoice add`, `aeat app ledger evidence add`,
   `aeat app ledger attach`) so the tutorial demonstrates the
   expense/invoice-ingestion path in place, not just narrated.
2. **Q1 — Modelo 130 (1T).** `aeat app modelo work create --modelo 130
   --year YYYY --period 1T`, `calculate` (first-period bindings all zero),
   `verify`, `export`. Check what else is due with `aeat app overview
   agenda` before moving on.
3. **Q2/Q3 — Modelo 130 (2T, 3T).** Repeat the create/calculate/verify/
   export chain, but this time the prior-period bindings are NOT zero — the
   tutorial demonstrates `aeat app modelo work revision --select
   latest-verified` (or the equivalent binding-carry mechanics already
   described in `how-to/review-calculation-values.md`) so the reader sees
   the cumulative nature of Modelo 130 in a lived example, not just told
   about it in prose (this is the load-bearing "calculation is a saved
   version, carried forward" fact identified in the phase-1 explanation
   extraction).
4. **Q4 — Modelo 130 (4T) and closing the year.** Same chain; introduce
   `aeat app overview calendar` to show the annual Modelo 100 window
   opening.
5. **Annual close — Modelo 100.** `aeat app modelo work create --modelo
   100 --year YYYY --period 0A` (period token to be confirmed against the
   live registry at authoring time), `calculate`, `verify`, `export`. This
   stage is where the tutorial demonstrates the cross-period carry-forward
   concept from `explanation/building-on-earlier-filings.md` for real: the
   four quarterly Modelo 130 instalments feed the annual settlement, and the
   tutorial shows what happens if a quarter is missing versus present
   (visible gap, not a guessed zero — the load-bearing fact from that
   explanation page).
6. **Filing and reconciliation.** `aeat app modelo work file`, then `aeat
   app modelo reconcile file` (or `reconcile pull` if a live-AEAT
   demonstration is in scope) to close the loop, matching the boundary
   narrative in `explanation/recording-a-filing-and-the-boundary.md`.

#### Wireframe B — the IVA lifecycle through one year (Modelo 303 periodic through Modelo 390 annual, with Modelo 349 for intra-community operators)

Narrative arc, sharing the same persona and ledger as Wireframe A (the same
income/expense rows already carry IVA fields, since `ledger add` requires
`--taxable-base`/`--iva-rate`/`--iva-amount` on IVA-relevant rows):

1. **Setup (shared with Wireframe A) plus IVA-specific facts.** If the
   persona needs it, elect a prorrata regime (`aeat app ledger prorrata
   elect-general` or `elect-especial`) — optional branch, called out as
   optional in the tutorial rather than mandatory, since most taxpayers use
   neither.
2. **First period — Modelo 303 (1T) and the IVA-wallet opening balance.**
   Before the first `calculate`, seed the IVA-wallet opening balance if the
   persona is not a true first-ever filer (`aeat app modelo iva-wallet
   seed`); otherwise demonstrate `aeat app modelo iva-wallet balance`
   returning zero for a genuine first filer. This is the identified gap
   page (Tier 2, Finding 2) folded directly into the tutorial rather than
   left as an isolated how-to.
3. **Q2/Q3 — Modelo 303 periodic filings.** Same create/calculate/verify/
   export chain; demonstrate a quarter that carries an IVA credit forward
   (`aeat app modelo iva-wallet balance` showing a non-zero active balance)
   so the reader sees the credit-carry mechanic live.
4. **Intra-community branch — Modelo 349.** Introduced as a labelled
   optional branch at whichever quarter the persona's ledger first carries
   an intra-community operation, using `aeat app modelo work create
   --modelo 349 ...` and the same calculate/verify/export chain. Framed
   explicitly as "if your activity includes intra-community operations,
   this filing runs alongside your quarterly IVA" rather than folded silently
   into the main IVA narrative, since not every taxpayer has this obligation
   (mirrors the `aeat:intra-community-operator` skill's own framing, which
   gates on profile facts rather than assuming universality).
5. **Q4 and the annual summary — Modelo 390.** `aeat app modelo work
   create --modelo 390 ...`, `calculate`, `verify` — demonstrating the
   reconciliation-against-the-four-quarters check described in the
   `aeat:preparar-modelo-390` skill and in `explanation/building-on-earlier-
   filings.md` ("Modelo 390... summarises the year's Modelo 303 IVA
   filings"), `export`.
6. **Filing and reconciliation.** Same closing shape as Wireframe A.

#### Relationship to the existing `tutorials/index.md` and `how-to/quickstart.md` duplication

Recommendation: **`tutorials/index.md` is absorbed into Wireframe A**
(its Modelo 130 single-quarter content becomes the "Q1" stage of the IRPF
lifecycle tutorial, extended forward through Q2-Q4 and the annual close),
and **`how-to/quickstart.md` survives unchanged** as the short, single-page,
copy-paste "shortest path to one exported file" reference it already is —
the phase-1 survey's recommendation to differentiate rather than delete
both applies directly here: quickstart stays terse and single-modelo;
the tutorial quadrant becomes the narrative, multi-stage, full-year surface.
This also resolves the ~80% content duplication identified in phase 1
without deleting either surface's distinct job.

## Open questions for the amending ADR

1. **How many lifecycle tutorials, and is a third (IS/sociedad) lifecycle
   in scope now or deferred?** The operator named a minimum of two (IRPF,
   IVA). The ADR should state explicitly whether "minimum two" leaves room
   for a later IS lifecycle (Modelo 202/200) as a third Tutorial-quadrant
   member, and whether the ADR's amendment should generalize the charter to
   "N lifecycle tutorials, one per major obligation family" rather than
   hard-coding two.
2. **Does the amended Tutorial charter still require "no decision points"?**
   The two mandated lifecycles both contain a genuine decision point (the
   Modelo 349 intra-community branch in Wireframe B, and potentially a
   withholding-obligation branch in Wireframe A if the persona employs
   staff or pays professional fees). The ADR must decide whether "no
   decision points" is relaxed to "no more than one clearly labelled
   optional branch per lifecycle" or whether branches are pushed out to a
   how-to cross-reference instead of appearing inside the tutorial.
3. **One shared persona/dataset across both tutorials, or two independent
   ones?** This research recommends one shared persona and dataset (see
   Finding 4 preamble); the ADR should ratify or override that
   recommendation, since it affects whether the two tutorial documents can
   be read independently or must be read in a fixed order.
4. **Does the single-source CLI-conformance gate need extending to
   lifecycle-scale tutorials?** The existing gate (per
   `2026-06-01-docs-educational-surface-adr`) parses fenced example
   invocations and asserts every verb resolves live. A lifecycle tutorial
   is an order of magnitude longer than the current single-modelo
   tutorial (roughly 4x the create/calculate/verify/export cycles per
   document); the ADR should confirm the existing gate's design scales to
   that length without a new mechanism, or name what changes.
5. **Where does the Modelo-100/130/349 how-to backlog (Finding 2, Tier 1)
   sit relative to the lifecycle tutorials?** Whether each lifecycle stage
   should link out to a dedicated how-to page for that modelo (once
   authored) the way `how-to/modelo-303.md` already exists independently of
   any tutorial, or whether the lifecycle tutorial is meant to supersede
   the need for some of those individual how-to pages. This research
   recommends the how-to pages still get authored independently (per the
   Diataxis charter: how-to guides serve competent operators returning to
   one task, tutorials serve the guided first pass), but the ADR should
   rule on it explicitly.
6. **Exact annual period token for Modelo 100 and Modelo 390.** Wireframe A
   step 5 and Wireframe B step 5 use a placeholder annual period token;
   the actual token (confirmed shape used elsewhere in the registry, e.g.
   `0A` for Modelo 130's annual projection) must be re-verified against the
   live registry at authoring time, not copied from this research without
   a fresh check.

## Next steps

- Operator review of this research document and its open questions.
- Author the amending/companion ADR against `2026-06-01-docs-educational-
  surface-adr`, resolving the six open questions above.
- Only after ADR acceptance: plan and execute the actual `docs/tutorials/`
  and `docs/how-to/` changes. No file under `docs/` is touched in this
  phase.
