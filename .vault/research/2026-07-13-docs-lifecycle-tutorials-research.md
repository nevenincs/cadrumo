---
tags:
  - '#research'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:ff720a80e4fcfc1a2e6c831f56960c5fac670dd8fdd74522c6eaa5e9f230e0a9'
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
a prior documentation-structure survey (phase 1 of this campaign), a
CLI-verified gap analysis and two tutorial wireframes (phase 2), and a
full-site information-architecture proposal plus a dedicated Renta document
outline (phase 2 addendum).

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

## Operator addendum (verbatim intent, phase 2 continuation)

Received after the initial phase-2 wireframes; folded into this document as
binding direction for the proposal shape:

1. **Standing mandate: condense, never bloat.** Every document must end up
   highly actionable, well-grounded, and cross-referenced — something the
   user can use to actually perform a task or orient themselves. When
   extracting explanation-page signal into how-to targets, the receiving
   page must not grow into theory; tighten as you merge. Prefer
   removing/renaming/moving/rearranging existing pages over authoring new
   prose.
2. **Information architecture is the actual tax filing year.** The user
   docs organise around three axes: (a) the calendar (what is due when),
   (b) the profile (who the taxpayer is, what facts drive obligations),
   (c) the per-modelo filings. The wireframe proposal must show the full
   `docs/` IA restructured on these axes, mapping every existing how-to
   page to its new home (kept / renamed / moved / merged / retired), not
   just the two new tutorials.
3. **Renta (Modelo 100) gets its own dedicated full document** explaining
   how the Renta filing and its bindings work — how the annual return
   builds on the year's data, prior filings (Modelo 130 fold-in), and
   registry bindings. This is the one place where deeper mechanism
   explanation is sanctioned, because Renta is where users must understand
   how values arrive. Ground it against the real registry/CLI surface
   (bindings list/resolve, work dependencies, cross-period carry).
4. **The gap-fill list is:** per-modelo lifecycle pages (130, 100, 349
   first), the ledger lifecycle commands (import to review to classify to
   evidence to invoices to export), LLM-based categorization, and exports.
   Mostly the raw material already exists across how-to pages; the work is
   consolidation and gap-filling, not greenfield writing.

## Binding direction: condense, never bloat

This is a standing mandate for every document this feature touches or
authors, not a one-time instruction scoped to this research pass. It
applies to the plan phase, the ADR phase, and every eventual `docs/` edit:

- **Every document must end up highly actionable, well-grounded, and
  cross-referenced** — something a taxpayer can use to actually perform a
  task or orient themselves, not a description of the system for its own
  sake. This is the same discipline `aeat-user-docs-hardening` already
  states for individual instruction steps ("Create taxpayer profile," not
  "We will now set up the taxpayer profiles"), extended here to the
  document and site level: a page that only orients without letting the
  reader act, or that repeats what another page already covers, does not
  earn its place.
- **A receiving page must not grow into theory when explanation-page
  signal merges in.** Every extraction identified in Finding 1 and folded
  into a how-to target (Finding 3's disposition table) must land as a
  tightened, action-relevant addition — a checklist, a precise scope
  statement, a one-paragraph caveat — never as a restatement of the
  conceptual framing the source explanation page used. If a merge would
  make the receiving page read like explanation prose, the signal is
  either compressed further or left out.
- **Prefer removing, renaming, moving, or rearranging an existing page over
  authoring new prose.** The gap-fill list (addendum item 4) is explicit
  that the raw material mostly already exists; new pages are reserved for
  the three named Tier-1 gaps (Modelo 130, 100, 349) and the one sanctioned
  Renta deep-mechanism document (Finding 5). Every other change in this
  proposal is a disposition on an existing page — merge, move, rename, or
  retire — not new authorship.

The three-axis IA table (Finding 3) and the Renta document outline
(Finding 5) below are both built under this mandate: the table shows small,
targeted consolidation rather than a rewrite, and the Renta outline is
explicitly scoped as the one place a deeper narrative is sanctioned, not a
precedent for expanding any other page.

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
- `docs/how-to/` — 34 files plus index; task-scoped imperative recipes
  covering onboarding, profile setup, censo, applicability, calendar,
  periods, notifications, live AEAT reads, transactions, classification,
  invoices, evidence, ledger correction, review queue, Modelo 036, LLM
  classification (3 pages), agent connection, calculation review, Google
  Sheets review, filing workflow, Modelo 303, Modelo 390, prorrata,
  verification reports, filing readiness, filing at AEAT, reconciliation,
  justificante receipts, data protection, troubleshooting, AEAT
  authentication.
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
  `USERDOCS-KICKOFF-BRIEF.md` (not opened; names suggest project-management
  metadata that should not live in the documentation tree).

**Two-segment hypothesis (phase-1 verdict, still standing):** the operator's
original framing (actionable vs. detached conceptual) was directionally
right but needed a correction: the real split is `how-to/` plus `tutorials/`
(actionable) versus `explanation/` (conceptual), with `architecture/` as a
third, developer-only segment that should not be folded into either
taxpayer bucket. `explanation/` is not detached — every page links into its
relevant how-to guide and states plainly that it is background reading, for
example `docs/explanation/from-records-to-figures.md`: "This is background
reading. When you're ready to actually do each step, follow the links to
the how-to guides." The phase-2 operator ruling and this addendum both
confirm this reading: Diataxis stands, and the condense mandate applies
project-wide, not only to the explanation-to-how-to extraction identified in
phase 1.

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

### 2. Gap analysis: modelo coverage versus how-to pages (revised per addendum item 4)

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
`docs/how-to/modelo-390.md` — the only three that exist today) confirms the
gap the addendum names. Per the addendum's explicit priority and its "raw
material mostly already exists, consolidate rather than greenfield" framing,
the revised gap-fill backlog is:

**Tier 1 — per-modelo lifecycle pages, named directly by the operator:**

1. Modelo 130 (IRPF pago fraccionado, estimación directa) — quarterly.
   Currently only covered by the dense `tutorials/index.md` walkthrough and
   `how-to/quickstart.md`; neither is a dedicated "how do I file Modelo
   130" recipe in the shape of `how-to/modelo-303.md`. New how-to page
   authored on the `modelo-303.md` template; its lifecycle-scale narrative
   moves to the IRPF tutorial (see Finding 4).
2. Modelo 100 (IRPF declaración anual, RENTA) — annual. No how-to page
   exists today. Gets BOTH a condensed action-focused how-to page (create /
   calculate / verify / export, same shape as every other modelo how-to)
   AND the dedicated deep-mechanism Renta document mandated by addendum
   item 3 (Finding 5) — these are two different Diataxis quadrants serving
   two different needs, not a duplication.
3. Modelo 349 (declaración recapitulativa de operaciones intracomunitarias)
   — no how-to page exists. New page on the `modelo-303.md` template,
   including the ROI/intra-community enrolment prerequisite currently only
   described inside the `aeat:intra-community-operator` skill.

**Tier 2 — ledger lifecycle consolidation (raw material exists; the work is
merging and tightening, per addendum item 4):**

4. The expense/invoice-ingestion path — "how do I get my business expenses
   and invoices into the application so I can calculate my modelo." Spans
   four existing pages today (`import-bank-statements.md`,
   `classify-transactions.md`, `manage-invoices.md`, `ledger-evidence.md`)
   plus a fifth thin page (`review-queue.md`) that overlaps
   `classify-transactions.md`'s "what's left" concern. No single page
   currently answers the compound question end to end in one arc: import
   to review to classify to evidence to invoices to export. See Finding 3
   for the proposed consolidation.
5. LLM-based categorization — three existing pages
   (`classify-with-llm.md`, `classify-with-llm-evidence.md`,
   `setup-llm-classification.md`) doing one coherent job across three
   separate documents. Consolidation candidate (Finding 3).
6. Exports — `review-with-google-sheets.md` and `file-at-aeat.md` already
   cover the two export surfaces (spreadsheet review, fichero-BOE upload);
   the gap here is cross-linking and condensing the explanation-page
   signal identified in phase 1 (the xlsx-vs-Sheets distinction, the
   fingerprint's purpose), not new pages.

**Tier 3 — the IVA-wallet gap identified in phase 1, load-bearing for the
IVA lifecycle tutorial:** the `aeat app modelo iva-wallet balance / seed /
correct / override` workflow is currently documented only in prose in
`explanation/building-on-earlier-filings.md`, with no how-to page. Folded
directly into the IVA lifecycle tutorial (Finding 4, Wireframe B) rather
than authored as a standalone page, consistent with the condense mandate —
a taxpayer hits this exactly once a year at the first period, which is
tutorial-shaped, not how-to-shaped.

**Tier 4 — present in the modelo family but out of scope for the two
mandated lifecycles:** Modelo 309 (ad-hoc IVA), Modelo 322/353 (grupo de
entidades), Modelo 369 (OSS/IOSS), Modelo 200/202 (Impuesto sobre
Sociedades), Modelo 111/115/180/190/193 (withholding family) each have a
preparer skill but no how-to page and are not named by the operator or
required by the two mandated tutorials. Flagged as a plausible later wave,
not actioned here.

### 3. Full-site information architecture: the before→after page-level IA table (addendum item 2)

The addendum's mandate is structural, not additive: organise the whole
taxpayer-facing surface — `docs/how-to/`, `docs/tutorials/`, and
`docs/explanation/` — around the calendar / profile / per-modelo-filings
axes a taxpayer actually lives in during a filing year, and show a
page-level before-to-after disposition for EVERY existing page in all
three quadrants — kept, renamed, moved, merged into X, or retired after
extraction — not only the how-to pages and not only the two new tutorials.
This is the centrepiece proposal for operator review.

Proposed groupings (folder or clear sub-index groupings under `how-to/`,
exact folder-vs-flat-with-headings mechanics deferred to the plan phase):

- **Your profile** — who the taxpayer is, what facts drive obligations.
- **Your calendar** — what is due, and when.
- **Your ledger** — the expense/invoice-ingestion and classification
  lifecycle.
- **Your filings** — the per-modelo create/calculate/verify/export/file/
  reconcile chain, common mechanics plus per-modelo pages.
- Two small residual groups that do not map to a single axis: agent
  connection (a tooling concern) and troubleshooting (cross-cutting).

Page-level disposition table, covering every page found in the phase-1
inventory:

| Existing page | New axis | Disposition |
| :--- | :--- | :--- |
| `onboarding.md` | (cross-axis entry point) | KEEP — the whole-journey map; stays the how-to landing page |
| `quickstart.md` | (cross-axis entry point) | KEEP unchanged — short, single-modelo, copy-paste reference; explicitly NOT absorbed into the tutorials (differentiates from the narrative lifecycle tutorials per Finding 4) |
| `profile-setup.md` | Your profile | KEEP |
| `censo-update.md` | Your profile | KEEP |
| `authenticate-with-aeat.md` | Your profile | KEEP, tightly cross-linked from `profile-setup.md`; candidate for folding in as a subsection — flagged as an open question (Finding 6) rather than forced here |
| `choose-modelo.md` | Your profile to Your calendar bridge | KEEP — applicability is a profile-facts question with a calendar-facing answer |
| `protect-data-access.md` | Your profile | KEEP |
| `filing-calendar.md` | Your calendar | KEEP, becomes the primary calendar page |
| `filing-periods.md` | Your calendar | MERGE into `filing-calendar.md` as a "period tokens and dates" subsection — two thin pages answering one question ("what is due, expressed as which dates") |
| `check-aeat-notifications.md` | Your calendar | KEEP |
| `read-live-aeat-data.md` | Your calendar | RETIRE as a standalone page; it is a thin index of live-pull commands already covered by `check-aeat-notifications.md`, `censo-update.md`, and `reconcile.md` (post-merge, Finding below) — its content is redistributed to those three pages, not lost |
| `filing-readiness.md` | Your calendar to Your filings bridge | KEEP as its own page — it checks a different thing than `verification-reports.md` (data-presence readiness before calculation, versus completeness after calculation); tighten cross-links rather than merge; flagged as an open question (Finding 6) |
| `import-bank-statements.md` | Your ledger | KEEP — ledger lifecycle stage 1 (import) |
| `classify-transactions.md` | Your ledger | KEEP — ledger lifecycle stage 2 (classify); receives the extracted mixed-cost-split signal from `explanation/from-records-to-figures.md`, tightened, not expanded |
| `review-queue.md` | Your ledger | MERGE into `classify-transactions.md` as a "what still needs a decision" subsection |
| `ledger-evidence.md` | Your ledger | KEEP — ledger lifecycle stage (evidence) |
| `manage-invoices.md` | Your ledger | KEEP — ledger lifecycle stage (invoices) |
| `correct-ledger-entries.md` | Your ledger | KEEP — ledger lifecycle maintenance stage |
| `classify-with-llm.md` | Your ledger | MERGE (with the two below) into one consolidated "LLM-assisted classification" page |
| `classify-with-llm-evidence.md` | Your ledger | MERGE (see above) |
| `setup-llm-classification.md` | Your ledger | MERGE (see above), becomes the consolidated page's setup section |
| `prorrata.md` | Your ledger | MOVE from the "How does this work?" grid into Your ledger (it is ledger-scoped register state consumed by Modelo 303/390, not a standalone concept page) |
| `modelo-036.md` | Your filings | KEEP |
| `modelo-303.md` | Your filings | KEEP — becomes the authoring template for the new 130/100/349 pages |
| `modelo-390.md` | Your filings | KEEP |
| *(new)* `modelo-130.md` | Your filings | AUTHOR — Tier 1 gap |
| *(new)* `modelo-100.md` | Your filings | AUTHOR — Tier 1 gap (condensed how-to; deep mechanism lives in the new Renta explanation document, Finding 5) |
| *(new)* `modelo-349.md` | Your filings | AUTHOR — Tier 1 gap |
| `filing-spine.md` | Your filings | KEEP — the shared work-unit/revision mechanics page every modelo page links to; receives the extracted revision-immutability fact from `explanation/editing-and-verifying.md`, tightened |
| `review-calculation-values.md` | Your filings | KEEP |
| `review-with-google-sheets.md` | Your filings | KEEP; receives the extracted xlsx-vs-Sheets distinction from `explanation/reviewing-and-exporting.md` |
| `verification-reports.md` | Your filings | KEEP; receives the extracted verify-state taxonomy and "what verifying does not mean" list from `explanation/editing-and-verifying.md` |
| `file-at-aeat.md` | Your filings | KEEP; receives the extracted fingerprint-purpose signal from `explanation/reviewing-and-exporting.md` |
| `reconcile.md` | Your filings | KEEP; receives the extracted reconcile-scope-precision signal from `explanation/recording-a-filing-and-the-boundary.md`; absorbs `justificante-receipts.md` (see below) |
| `justificante-receipts.md` | Your filings | MERGE into `reconcile.md` as a "pull and store the justificante" leading section — reconciliation always needs the justificante fetched first, so the two-hop split serves no reader |
| `connect-an-agent.md` | (residual, tooling) | KEEP unchanged |
| `troubleshooting.md` | (residual, cross-cutting) | KEEP unchanged |
| `tutorials/index.md` | (Tutorial quadrant) | RETIRE as a standalone single tutorial; ABSORBED into the new `tutorials/irpf-lifecycle.md` as its Q1 stage (Finding 4, Wireframe A) |
| *(new)* `tutorials/irpf-lifecycle.md` | (Tutorial quadrant) | AUTHOR — Wireframe A, absorbs `tutorials/index.md` |
| *(new)* `tutorials/iva-lifecycle.md` | (Tutorial quadrant) | AUTHOR — Wireframe B |
| `explanation/from-records-to-figures.md` | (Explanation quadrant) | KEEP, TIGHTEN — extract the mixed-cost-split and readiness-check signal into `classify-transactions.md` / `import-bank-statements.md` (Finding 1), trim the source page once each signal has a how-to home |
| `explanation/editing-and-verifying.md` | (Explanation quadrant) | KEEP, TIGHTEN — extract the verify-state taxonomy and the immutable-revision fact into `verification-reports.md` / `filing-spine.md`, trim after extraction |
| `explanation/building-on-earlier-filings.md` | (Explanation quadrant) | KEEP, TIGHTEN — extract the no-fabricated-prior-period guarantee into `review-calculation-values.md`; the IVA-wallet mechanics fold into the IVA lifecycle tutorial (Tier 3 gap) rather than staying prose-only here |
| `explanation/reviewing-and-exporting.md` | (Explanation quadrant) | KEEP, TIGHTEN — extract the xlsx-vs-Sheets distinction and the fingerprint's purpose into `review-with-google-sheets.md` / `file-at-aeat.md` |
| `explanation/recording-a-filing-and-the-boundary.md` | (Explanation quadrant) | KEEP, TIGHTEN — extract the reconcile-scope-precision fact into the merged `reconcile.md` |
| *(new)* `explanation/renta-and-bindings.md` (working title) | (Explanation quadrant, sanctioned deep-mechanism page) | AUTHOR — Finding 5; the one explanation page allowed to stay CLI-command-dense rather than tightened toward brevity |
| `architecture/index.md`, `architecture.md` | (developer surface, out of taxpayer scope) | KEEP unchanged — confirmed out of scope by the operator ruling ("Diataxis stands... `architecture/` stays the developer surface") |

Net page-count effect of this table: 34 existing how-to pages become
roughly 27 (7 merges: filing-periods to filing-calendar, read-live-aeat-data
retired/redistributed, review-queue to classify-transactions, three
LLM pages to one, justificante-receipts to reconcile); 1 tutorial page
becomes 2 (the lifecycle split); all 5 explanation pages are kept but
tightened as their extracted signal lands on how-to pages; 3 new per-modelo
how-to pages (130, 100, 349) and 1 new dedicated explanation document
(Renta) are authored. Net growth is small and concentrated exactly where
the operator named a real gap, not a general expansion — consistent with
the condense-never-bloat mandate above.

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

Every stage below cites the how-to pages it condenses per the addendum's
"consolidate, don't bloat" mandate — the tutorial narrates the arc; the
mechanics of each single step stay on the how-to page it links to.

#### Wireframe A — the IRPF annual lifecycle (Modelo 130 quarterly through Modelo 100 annual)

Narrative arc across a fiscal year, one stage per quarter plus a close:

1. **Setup.** Create the taxpayer profile (`aeat config profile create`)
   with activity-start-date scoping out prior periods; record the first
   quarter's business income and expense rows (`aeat app ledger add`, or
   `aeat app ledger import` for a bank statement); classify them (`aeat app
   ledger classify`); attach an invoice or evidence document to at least
   one row (`aeat app ledger invoice add`, `aeat app ledger evidence add`,
   `aeat app ledger attach`) so the tutorial demonstrates the
   expense/invoice-ingestion path in place, not just narrated. Links out to
   the consolidated Your-ledger pages rather than re-explaining flags.
2. **Q1 — Modelo 130 (1T).** `aeat app modelo work create --modelo 130
   --year YYYY --period 1T`, `calculate` (first-period bindings all zero),
   `verify`, `export`. Check what else is due with `aeat app overview
   agenda` before moving on. Links to the new `modelo-130.md` how-to.
3. **Q2/Q3 — Modelo 130 (2T, 3T).** Repeat the create/calculate/verify/
   export chain, but this time the prior-period bindings are NOT zero — the
   tutorial demonstrates the cumulative nature of Modelo 130 in a lived
   example (the load-bearing "calculation is a saved version, carried
   forward" fact identified in phase 1), linking to `filing-spine.md` and
   `review-calculation-values.md` for the mechanics rather than repeating
   them.
4. **Q4 — Modelo 130 (4T) and closing the year.** Same chain; introduce
   `aeat app overview calendar` to show the annual Modelo 100 window
   opening.
5. **Annual close — Modelo 100.** `aeat app modelo work create --modelo
   100 --year YYYY --period 0A` (period token to be confirmed against the
   live registry at authoring time), `calculate`, `verify`, `export`. This
   is the stage that hands off to the new dedicated Renta explanation
   document (Finding 5) for readers who want the mechanism, and to the new
   `modelo-100.md` how-to for readers who just want the commands — the
   tutorial itself stays narrative and does not duplicate either.
6. **Filing and reconciliation.** `aeat app modelo work file`, then `aeat
   app modelo reconcile file` (or `reconcile pull` if a live-AEAT
   demonstration is in scope) to close the loop, linking to the merged
   `reconcile.md` (which now also covers pulling the justificante).

#### Wireframe B — the IVA lifecycle through one year (Modelo 303 periodic through Modelo 390 annual, with Modelo 349 for intra-community operators)

Narrative arc, sharing the same persona and ledger as Wireframe A (the same
income/expense rows already carry IVA fields, since `ledger add` requires
`--taxable-base`/`--iva-rate`/`--iva-amount` on IVA-relevant rows):

1. **Setup (shared with Wireframe A) plus IVA-specific facts.** If the
   persona needs it, elect a prorrata regime (`aeat app ledger prorrata
   elect-general` or `elect-especial`) — optional branch, called out as
   optional in the tutorial rather than mandatory, since most taxpayers use
   neither. Links to the moved `prorrata.md` (now grouped under Your
   ledger).
2. **First period — Modelo 303 (1T) and the IVA-wallet opening balance.**
   Before the first `calculate`, seed the IVA-wallet opening balance if the
   persona is not a true first-ever filer (`aeat app modelo iva-wallet
   seed`); otherwise demonstrate `aeat app modelo iva-wallet balance`
   returning zero for a genuine first filer. This is the Tier 3 gap folded
   directly into the tutorial rather than left as an isolated how-to.
3. **Q2/Q3 — Modelo 303 periodic filings.** Same create/calculate/verify/
   export chain; demonstrate a quarter that carries an IVA credit forward
   (`aeat app modelo iva-wallet balance` showing a non-zero active balance)
   so the reader sees the credit-carry mechanic live.
4. **Intra-community branch — Modelo 349.** Introduced as a labelled
   optional branch at whichever quarter the persona's ledger first carries
   an intra-community operation, using `aeat app modelo work create
   --modelo 349 ...` and the same calculate/verify/export chain, linking to
   the new `modelo-349.md` how-to. Framed explicitly as "if your activity
   includes intra-community operations, this filing runs alongside your
   quarterly IVA" rather than folded silently into the main IVA narrative.
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
this resolves the ~80% content duplication identified in phase 1 without
deleting either surface's distinct job, and is reaffirmed unchanged by the
condense mandate: quickstart is already the condensed page for its purpose.

### 5. The dedicated Renta (Modelo 100) document (addendum item 3)

This is the one place where deeper mechanism explanation is sanctioned,
because Renta is where the year's data, prior filings, and registry
bindings all converge into a single settlement figure, and a taxpayer must
understand how a value arrived, not just that it did. It lives in
`explanation/` (the Diataxis quadrant already chartered for
mechanism-level narrative in `2026-06-01-docs-educational-surface-adr`), as
a sixth page in that cluster, cross-linked from both the new `modelo-100.md`
how-to page and the IRPF lifecycle tutorial's annual-close stage, rather
than duplicating either.

Outline, grounded against the live registry/CLI surface (every command
below confirmed against the live `--help` tree in this session, none cited
from memory):

1. **What Modelo 100 pulls together over the year.** The annual settlement
   concept — rendimientos, base imponible, cuota íntegra, deducciones,
   cuota líquida, retenciones and pagos a cuenta, cuota diferencial —
   contrasted explicitly with the quarterly modelos' narrower, single-
   period scope.
2. **Where the year's ledger data comes from.** Modelo 100's calculation
   reads the FULL fiscal year's classified ledger, not a quarter's window —
   the same `aeat app ledger classify` / `aeat app modelo work calculate`
   mechanics as any other modelo, but with a year-wide date window. Cross-
   references `filing-periods.md`'s period-token mechanics (post-merge,
   Finding 3) rather than re-deriving them.
3. **How Modelo 130's quarterly instalments fold in.** Explains the
   cross-modelo fold-in as a registry-declared relation (per the project's
   `calculation-source-canonical-mechanism` convention: cross-modelo
   fold-ins are modelled as relations, not a second binding), demonstrated
   live with `aeat app modelo work dependencies --modelo 100 --year YYYY
   --period 0A`, which surfaces the Modelo 130 filing-history dependency
   and the clean-state gate that blocks the annual return until the
   quarters are filed and evidenced.
4. **How to inspect exactly which casilla came from where.** Walks
   `aeat app modelo bindings list --modelo 100 --year YYYY --period 0A` and
   `aeat app modelo bindings resolve` to preview binding sources before
   calculating, and `aeat app modelo work observations` to see the typed
   provenance (legal_refs, source_refs, formula_id) on the saved revision
   after calculating — this is where the "every figure traces back to the
   law" claim, stated but not demonstrated anywhere else in the docs, gets
   a concrete, reproducible walkthrough.
5. **Retenciones and pagos a cuenta.** How amounts withheld by others
   (fed from Modelo 111/115/190/193 if the taxpayer has those obligations)
   and the taxpayer's own quarterly Modelo 130 pagos fraccionados combine
   to net the final cuota diferencial — a resultado a pagar or a devolución.
6. **What happens when a dependency is missing or blocked.** Demonstrates
   the clean-state guard live via `aeat app modelo work dependencies`,
   cross-referencing the "visible gap, not a guessed zero" guarantee
   already established in `explanation/building-on-earlier-filings.md`
   rather than re-arguing it.
7. **Where to go next.** Links to `modelo-100.md` (the condensed
   action-only how-to) for readers who just want the commands, and to the
   IRPF lifecycle tutorial for readers who want the whole year narrated.

This document is explicitly NOT a template for other modelos — it is
sanctioned as a one-off because Renta is uniquely where the fold-in,
binding-resolution, and provenance concepts a taxpayer needs to trust the
figure all converge in one filing. Other annual-summary modelos (180, 190,
193, 390) already have a lighter version of the same "reconciles against
the four trimestrales" check and do not need a matching deep document
unless a future audit finds the same trust gap there.

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
5. **Ratify the page-level disposition table in Finding 3, or amend it.**
   Several dispositions are genuine judgment calls this research flags but
   does not consider settled: whether `authenticate-with-aeat.md` folds
   into `profile-setup.md` or stays separate; whether `filing-readiness.md`
   stays a distinct page from `verification-reports.md` or merges; the
   exact folder-vs-flat-with-headings mechanics for the three new axis
   groupings. The ADR (or the plan phase that follows it) should rule on
   each explicitly rather than leaving them as this research's default
   lean.
6. **Where do the Tier-1 how-to pages (130/100/349) sit relative to the
   lifecycle tutorials?** Whether each lifecycle stage should link out to
   its dedicated how-to page (the pattern this research assumes throughout
   Finding 4) or whether the lifecycle tutorial is meant to supersede the
   need for some of those individual pages. This research recommends the
   how-to pages still get authored independently (per the Diataxis
   charter: how-to guides serve competent operators returning to one task,
   tutorials serve the guided first pass), but the ADR should rule on it
   explicitly.
7. **Exact annual period token for Modelo 100 and Modelo 390.** Wireframe A
   step 5 and Wireframe B step 5 use a placeholder annual period token;
   the actual token must be re-verified against the live registry at
   authoring time, not copied from this research without a fresh check.
8. **Where does the Renta document sit in Diataxis — the explanation
   quadrant as proposed, or a how-to hybrid?** This research places it in
   `explanation/` (Finding 5) because Diataxis reserves mechanism-level
   narrative for that quadrant and the operator's own framing ("the one
   place where deeper mechanism explanation is sanctioned") matches that
   quadrant's charter. But the outline is unusually CLI-command-dense for
   an explanation page — it walks `bindings list/resolve`, `work
   dependencies`, and `work observations` live, closer to how-to register
   than the other five zero-command explanation pages. The amending ADR
   must place it explicitly: (a) a sixth `explanation/` page, tightened
   toward narrative with commands used only as illustration; (b) a
   distinctly labelled "deep dive" page still inside `explanation/`,
   signalling it is denser than its siblings; or (c) a genuine how-to/
   explanation hybrid — a new, one-off Diataxis exception documented as
   such — that a taxpayer reaches from the calculate step itself. This
   research leans toward (b) but does not consider it settled.

## Next steps

- Operator review of this research document and its open questions.
- Author the amending/companion ADR against `2026-06-01-docs-educational-
  surface-adr`, resolving the open questions above.
- Only after ADR acceptance: plan and execute the actual `docs/tutorials/`
  and `docs/how-to/` changes, including the page-level merges, moves, and
  retirements in the Finding 3 disposition table, the three new modelo
  how-to pages, and the dedicated Renta document. No file under `docs/` is
  touched in this phase.
