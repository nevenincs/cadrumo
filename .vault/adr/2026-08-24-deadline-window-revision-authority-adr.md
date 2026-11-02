---
tags:
  - '#adr'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-11-01'
body_schema: 'body-v1'
body_hash: 'sha256:f335a115739bf0aa3dad99d2c277c5103ad4f5c8ee0e0d4e6ce0b7c06fa9e164'
related:
  - "[[2026-08-24-deadline-window-revision-authority-research]]"
  - '[[2026-08-24-deadline-window-revision-authority-reference]]'
  - '[[2026-08-14-registry-temporal-coverage-adr]]'
  - '[[2026-07-09-m210-plazo-keying-adr]]'
---

# `deadline-window-revision-authority` adr: `deadline windows are revision-owned law facts` | (**status:** `accepted`)

## Problem Statement

Deadline-window rows can currently be copied across revisions and emitted multiple
times as distinct obligations, while periodic selectors can be represented by only a
few sample rows and silently omit the rest. A fleet-wide decision is needed for window
identity, revision ownership, cadence completeness, canonical projection, and M210's
non-standard plazo axes. Grounding is in the related research and reference.

## Considerations

- Revision selection remains law-derived from the canonical filing coordinate.
- Dates may fall in the following calendar year without changing tax-year identity.
- Registry validation must fail closed; runtime consumers must not arbitrate corrupt data.
- Periodic calendario coverage must be complete for every declared supported year.
- M210's resultado and tipo-renta axes are not profile predicates or period aliases.

## Considered options

**Runtime deduplication.** Rejected: it hides invalid authority and cannot safely choose
between conflicting dates, qualifiers, or provenance.

**Registry data cleanup only.** Rejected: it removes today's copies but permits the same
defect to recur.

**Modelo-level deadline catalogue outside revisions.** Deferred: it creates a broad new
authority structure while revision provenance and applicability remain necessary.

**Revision-owned canonical windows with strict validation.** Proposed: validate identity,
ownership, and semantic uniqueness during registry build; project only validated rows.

## Constraints

- `select_revision` and the validated-authority pipeline are stable parent authorities.
- `DeadlineWindowDefinition.filing_year` remains during migration but must equal
  `period.filing_year`; removal or derivation can follow as a separate schema change.
- M210 must complete its typed plazo-keying design before the fleet invariant can pass;
  no modelo-specific exemption is permitted.
- Deadline completeness consumes the shared supported-filing-year coverage declaration
  owned by the accepted registry-temporal-coverage architecture; it does not add a
  deadline-specific horizon. Validation makes no claim about unpublished future dates.
- Any changed legal date requires verification against bundled and official authority.
- Exact filing dates are revision-owned legal facts. Registry source-fidelity tests assert
  those literal values and provenance; architecture and fleet behavior tests derive their
  horizon from the supported-filing-year catalogue and assert relational or semantic
  invariants instead of copying a year list or exact-count pass condition.
- “Today” is not registry data or a durable legal fact. Status calculations accept an
  explicit reference date and default only through the canonical Europe/Madrid civil clock
  seam; deterministic tests inject or freeze that seam.
- Feature acceptance is attributable and finite. Revision-scoped whole-repository
  checkpoints remain honest release evidence, but unrelated concurrent failures do not
  become deadline-window defects or keep this feature open; this follows the accepted
  quality-gate-zero-closure decision.

## Implementation

Define the semantic coordinate as `(modelo, period.filing_year,
period.registry_token, typed deadline qualifiers)`. Registry validation requires
the redundant year to match the period year, the containing revision to be the unique
law-selected owner, and IDs and semantic coordinates to be unique across revisions.
For periodic schedules, validation requires every selected cadence token for each
filing year declared supported by the canonical temporal-coverage projection. Sparse
coverage is permitted only for an explicitly typed event schedule, never inferred
from missing rows.

Repair all affected modelo data. M190 and M193 align identity year while retaining
physical filing dates. M210 uses canonical `EVENT-N`/`0A` identity plus the existing
`ResultDisposition` and official two-digit tipo-renta code authorities as qualifiers,
completing rather than bypassing its plazo-keying decision. M303, M322, and M353 retain
rows only in their canonical revisions, including the M303 2024 cutover. The complete
measured periodic fleet—M111, M115, M123, M130, M131, M202, M216, M303, M322, M349,
M353, and M369—is materialised through the canonical declared supported-year horizon
from bundled official evidence. Open frontier revisions do not imply unpublished future
dates.

The authority deadline projection traverses validated canonical rows and asserts the
invariant defensively. The engine, overview application, workflow, declaration and
calculation notices, and CLI remain thin consumers and add no dedupe logic.

## Rationale

This is the only option that makes invalid registry state unrepresentable at the
production authority boundary while preserving one shared behavior for every consumer.
It composes with the established revision resolver and addresses M210 through typed tax
semantics instead of weakening the invariant.

## Consequences

- Calendar, agenda, backlog, workflow, filing-window lookup, and CLI regain exact-one
  obligation semantics from one repair.
- Future stale copies fail registry validation before reaching operators.
- M210 plazo completion expands the change beyond mechanical data deletion and requires
  careful legal and calculation-output integration.
- Fleet-wide and real CLI regressions become permanent gates on multiplicity.
- The calendar stops silently under-declaring monthly and quarterly obligations that
  were absent because only sample rows had been authored.

## Amendment 2026-11-01: projected domiciliación cutoff

Approved by the operator on 2026-11-01. The accepted body above is unchanged; where its
wording conflicts with this section, this section governs for the payment cutoff only.

### Ruling

- The domiciliación payment cutoff of a deadline window is a rule declared once in the
  registry and projected forward and backward through canonical governed-fact temporal
  selection, not a literal date authored once per filing year. The rule has two
  mapping facts: `deadlines.domiciliation-cutoff-clause`, the Orden EHA/1658/2009 Anexo II
  clause keyed by modelo and typed period selector, and
  `deadlines.domiciliation-procedure`, the art. 3.2 procedure on the submission-date
  axis with one variant before and one from 15 March 2025 (Orden HAC/241/2025). Each
  part's first variant reaches the support floor and its last stays open, so omission
  inherits and a legal change is a new dated variant. `DeadlineWindowDefinition` and the
  persisted authority schema are unchanged.
- A `payment_cutoff_on` authored on a window wins and need not agree with the rule. The
  rule fills only the windows that author none. Disagreement is a registry finding for
  review, never a runtime arbitration.
- A derived cutoff refuses a late domiciliación export exactly as an authored one does.
  The resolution carries its provenance: authored or derived, the clause and procedure
  variant ids, their legal and source references, the projection direction of each
  resolved fact, the art. 3.2.b extension, the margin cap and the holiday coverage. The
  export refusal names the source and, for a derived cutoff, the variants and legal
  references.
- When the rule cannot derive a cutoff, it is unavailable, never open: no clause or
  procedure covers the coordinate, a year the margin walk enters has no published
  holiday calendar, or the procedure's territory is not verified for that year. The
  existing unverified advisory path applies unchanged.
- AEAT's practice of replacing an Anexo II day that falls on an inhábil day with the
  latest business day that still meets the margin is a separate procedure variant,
  recorded as AEAT administrative practice grounded in AEAT's published domiciliación
  calendar, not in the Orden, and graded pending review. It applies from 1 January 2026,
  the first calendar the registry bundles that shows it.
- Projecting window opening and closing dates is out of scope and remains a separate
  decision. Those dates stay revision-owned literal facts, and windows are still not
  projected to unpublished years.

### Grounding

- Orden EHA/1658/2009 art. 3.2.a sends the domiciliación period to Anexo II; art. 3.2.b
  extends it by the days the filing period is extended when its last day is inhábil.
  Orden HAC/241/2025 art. segundo.Dos, in force 15 March 2025 without a transitional
  regime, requires at least "tres días hábiles o cinco naturales" before the end of the
  voluntary period and defines inhábil days by the municipality of AEAT's Departamento
  de Informática. The territory is declared as data (`ES-MD`); municipal holidays have no
  registry source, so derivations report that layer as unverified.
- Anexo II for Modelo 303 has not changed since Orden HFP/417/2017, before the support
  floor. Modelo 390 does not appear in Anexo II. Other modelos listed there are left to
  their owners.
- Both orders are enrolled in the legal catalogue
  (src/cadrumo/_data/registry/aeat/legal/domiciliacion-pago.toml:16) from bundled BOE
  texts BOE-A-2009-10326 (consolidated) and BOE-A-2025-5048 (as published).
- Measured against the bundled 2026 AEAT domiciliación calendar, the rule reproduces all
  16 Modelo 303 rows it prints, including 2026 1T, 2T and 3T, which authored no cutoff
  and now derive 15 April, 15 July and 15 October. Against the 75 authored Modelo 303
  cutoffs it agrees on 60. The disagreements are AEAT calendar practice that varied by
  year (2023 to 2025 weekend and holiday handling, and 1T 2025 published on the 15th
  where the rule gives the 16th) plus 12M 2026, which needs the unpublished 2027
  calendar. Those authored dates stay and win.

### Implementation

- One domain resolver supplies the cutoff of an already matched window:
  src/cadrumo/domain/deadlines/domiciliation_cutoff.py:629 returns the authored date when
  present and otherwise derives it (src/cadrumo/domain/deadlines/domiciliation_cutoff.py:538)
  through pure arithmetic (src/cadrumo/domain/deadlines/domiciliation_cutoff.py:335).
  Both facts are read through the existing governed-fact resolver
  (src/cadrumo/domain/calculations/registry/facts/resolution.py:390); there is no second
  loader, no newest-year fallback and no year in code.
- Window matching stays solely in src/cadrumo/domain/deadlines/plazo.py:31. Every
  consumer that read the window's literal field now reads the resolver: export accounts
  (src/cadrumo/application/modelo/export_accounts.py:322), the M210 plazo context
  (src/cadrumo/application/modelo/work_plazo.py:362), the overview calendar
  (src/cadrumo/application/overview/calendar.py:215) and the deadline engine
  (src/cadrumo/domain/deadlines/engine.py:376).
- The new facts publish as existing governed-fact components, so a new authority
  generation and its runtime adoption are required before the derived cutoffs reach an
  installed runtime. Source installation, publication and adoption are reported
  separately.

### Wording of the accepted body this amendment qualifies

- Constraints, "Validation makes no claim about unpublished future dates": this holds for
  window dates. A derived payment cutoff is a projection of declared law with explicit
  provenance, not a claim of a published date, and it is unavailable wherever the holiday
  calendar it needs is unpublished.
- Constraints, "Exact filing dates are revision-owned legal facts": this now covers the
  opening and closing dates. The payment cutoff is derived from the governed rule unless
  a window authors one, which wins. Cutoff source-fidelity tests compare derived values
  with the bundled AEAT domiciliación calendar as an independent oracle.
- Implementation, "Open frontier revisions do not imply unpublished future dates": window
  dates still do not project. The cutoff rule projects through its own governed-fact
  variants and yields a value only for windows that exist and years whose holiday
  calendar is published.
- Implementation, thin consumers: consumers read the resolver's typed result and add no
  cutoff logic of their own.
- Consequences: a missing per-year cutoff no longer downgrades a domiciliación refusal to
  an advisory wherever the rule and the holiday calendar cover the coordinate.

### Follow-up recorded, not decided here

- The proposed ADR 2026-08-19-registry-campaign-sequencing-deadline-window-reach-adr says
  a deadline must be read from AEAT's published calendar rather than derived from the
  statutory rule. Before it is accepted it must be narrowed to filing opening and closing
  dates, or otherwise reconciled with this amendment; it was not edited here.
- A registry agreement report comparing authored and derived cutoffs against a keyed,
  justified divergence list, a coverage gate requiring every periodic window of a modelo
  that declares domiciliación to have an authored cutoff or a covering clause, and the
  pruning of authored cutoffs equal to the derived value remain later steps.

## Amendment 2026-11-01 (2): projected filing windows

Approved by the operator on 2026-11-01 (decisions D1 to D6 of the window-projection
design). The accepted body and the first 2026-11-01 amendment are unchanged; where their
wording conflicts with this section, this section governs for the opening and closing
dates of the modelos that declare a filing-window clause, today Modelo 303 and Modelo 390.

### Ruling

- A filing window's opening and nominal closing dates are a rule declared once per modelo
  and typed period selector in the governed mapping fact `deadlines.filing-window-clause`
  and projected through canonical governed-fact temporal selection. The extension of an
  inhábil nominal close is the governed procedure `deadlines.filing-close-inhabil-shift`:
  the next día hábil on the national calendar of días inhábiles, graded as AEAT published
  practice and pending review. `DeadlineWindowDefinition` and the persisted authority
  schema are unchanged.
- A window exists only where the law-selected revision's filing schedule declares the
  period; the clause supplies dates, never the obligation.
- An authored window wins and need not agree with the rule; the rule fills only scheduled
  coordinates that no owning revision authors. Disagreement is a registry finding for
  review, never runtime arbitration. Administrative or territorial extensions the rule
  cannot derive (RD 1624/1992 art. 71.4, last paragraph) are authored windows.
- `closes_on` means the AEAT published close on the national basis. The filer's territory
  is applied afterwards by the effective-deadline service, whose behaviour is unchanged.
- Where the national holiday calendar of a year the shift consults is not published, the
  window's close is unknown. Its opening and nominal close are reported, the nominal close
  only as a lower bound; the obligation carries the status `UNKNOWN`, is never classified
  as due or overdue against the nominal date, and no lateness, recargo or payment cutoff is
  judged after it. It is never treated as open or as absent.
- Projection respects the shared support envelope: nothing below the floor; above the
  horizon the open frontier revision and the open fact variants carry forward, with the
  projection direction retained in the provenance.
- The domiciliación cutoff clause no longer carries the nominal close; it reads it from the
  filing-window clause, so the nominal close has one home.
- The 12M 2026 Modelo 303 window no longer authors `payment_cutoff_on` 2027-01-27 or the
  two 2026 calendar source references that supported it: the bundled 2026 AEAT
  domiciliación calendar prints no 12M 2026 row. Its cutoff is derived when the 2027
  holiday calendar is published and is unavailable until then.

### Grounding

- RD 1624/1992 art. 71.4 and Orden EHA/3786/2008 art. 7 fix the Modelo 303 plazos:
  twenty days after a quarter, thirty January for the fourth quarter and period 12, thirty
  days after a month for SII filers, and the end of February for January. Orden
  EHA/3111/2009 art. 8 fixes thirty January for Modelo 390. The clause variants cite the
  bundled BOE form orders as source text.
- Ley 39/2015 art. 30.5 moves a plazo ending on an inhábil day to the next hábil day;
  art. 30.2 and art. 31.3 make Saturdays, Sundays and declared holidays inhábil for
  electronic registers; DA 1ª.2 and Ley 58/2003 art. 7.2 apply the rule to tax procedure.
  The national-only basis is graded as AEAT published practice because the AEAT calendar
  publishes one close for all filers.
- The legal entries are enrolled in the existing catalogue files
  (src/cadrumo/_data/registry/aeat/legal/iva-flow.toml,
  src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml,
  src/cadrumo/_data/registry/aeat/legal/lgt-autoliquidacion.toml) from texts already in
  the bundled corpus.
- Measured against every authored window from the support floor to the horizon (80
  Modelo 303 and 5 Modelo 390 windows), with the national calendars of 2022, 2023 and
  January 2027 supplied where the authority publishes none, the rule reproduces all but
  one: Modelo 390 2026 authors Saturday 30 January 2027 and states that no weekend
  displacement is asserted, where the rule gives Monday 1 February. That authored date
  stays, wins and is listed as the one justified divergence; whether to correct it is a
  registry decision.

### Implementation

- The facts are src/cadrumo/_data/registry/aeat/facts/0172-filing-window-clause.toml and
  src/cadrumo/_data/registry/aeat/facts/0173-filing-close-inhabil-shift.toml; the nominal
  close keys left src/cadrumo/_data/registry/aeat/facts/0170-domiciliation-cutoff-clause.toml.
- One domain module projects a coordinate:
  src/cadrumo/domain/deadlines/filing_window_projection.py:259 resolves the clause through
  the existing governed-fact resolver, src/cadrumo/domain/deadlines/filing_window_projection.py:460
  applies the shift or reports the close unknown, and
  src/cadrumo/domain/deadlines/filing_window_projection.py:601 enumerates the unauthored
  scheduled coordinates of a year. There is no second loader, no newest-year fallback and
  no year in code.
- The deadline engine's year index adds the projections beside the authored windows and
  keeps close-unknown projections apart (src/cadrumo/domain/deadlines/engine.py:208); the
  schedule carries them as `close_unknown_obligations`
  (src/cadrumo/domain/deadlines/engine.py:675, src/cadrumo/domain/deadlines/models.py:950)
  with `ObligationStatus.UNKNOWN` (src/cadrumo/domain/deadlines/models.py:142).
- Window matching stays solely in src/cadrumo/domain/deadlines/plazo.py:35, which now
  returns a typed resolution: authored, projected, or projected with an unknown close.
  Consumers read the dated window where one exists: the effective deadline
  (src/cadrumo/application/modelo/effective_deadline.py:147), the work plazo and form
  header, export accounts, the workflow gate, and the overview calendar, which shows an
  unknown close as an `UNKNOWN` row (src/cadrumo/application/overview/calendar.py:559)
  that agenda, backlog, next-due and the TUI past scope leave out of their date cohorts.
- The domiciliación clause takes its nominal close from the window clause
  (src/cadrumo/domain/deadlines/domiciliation_cutoff.py:246).
- The agreement, precedence, future-year and unknown-close behaviour is tested in
  src/cadrumo/domain/deadlines/tests/test_filing_window_projection.py against the authored
  windows and an oracle written from the articles.
- The facts and the 303 window change publish as existing governed-fact and window
  components, so a new authority generation and its runtime adoption are required before
  projected windows reach an installed runtime. Source installation, publication and
  adoption are reported separately.

### Wording of the accepted body and the first amendment this section qualifies

- Constraints, "Validation makes no claim about unpublished future dates": a projected
  window is a projection of declared law with provenance, not a claim of a published
  date; its close is unknown until the holiday calendar it needs is published.
- Constraints, "Exact filing dates are revision-owned legal facts": authored windows
  remain so and win; projected dates are rule-derived and tested against the authored
  windows as an independent oracle.
- Implementation, periodic completeness: for a modelo with a filing-window clause, a
  coordinate is complete when an authored window or a covering clause exists.
- Implementation, "Open frontier revisions do not imply unpublished future dates": open
  frontier revisions with a covering clause now yield projected windows, dated or with an
  unknown close; without a clause they still do not.
- First 2026-11-01 amendment, "Projecting window opening and closing dates is out of scope":
  superseded by this section for the modelos that declare a clause. Its statement that the
  domiciliación clause carries the nominal close is replaced by the single home above.

### Follow-up recorded, not decided here

- Modelo 390 2026 authored close (Saturday 30 January 2027) against the rule's Monday 1
  February: correct the authored window or keep it as a reviewed divergence. Modelo 130
  2026 4T is likewise authored on Saturday 30 January 2027; Modelo 130 declares no clause,
  so it is outside this section.
- The workflow and state projections read only dated obligations and do not yet surface
  close-unknown obligations; the deadline engine's explain and applicability helpers read
  dated windows only.
- Review whether the taxpayer-territory shift (art. 30.6) applied by the effective-deadline
  service is right for electronic filing given art. 31.3.

## Amendment 2026-11-02 (3): national-only shift of filing closes

Ruled by the operator on 2026-11-02, settling the last follow-up of amendment (2). The
accepted body and the two earlier amendments are unchanged except where this section
governs: the effective close of a filing window.

### Ruling

- A filing close moves to the next business day only for Saturdays, Sundays and the
  national días inhábiles of the AGE calendar. A regional (CCAA) or local holiday never
  moves a filing close, for any filer.
- Ley 39/2015 art. 31.3 governs electronic filing at the sede and excludes art. 30.6, so
  the filer's territory has no bearing on the close. The AEAT Calendario del Contribuyente
  wording that a regional or local holiday moves the close was weighed and not followed.
- Every surface reads the same effective close: calculate, the work form, the
  declarations calendar and list, the overview and the workbench. No taxpayer territory
  enters the deadline path.
- The domiciliación cutoff is a different procedure and keeps the territory its registry
  declaration names (amendment 2026-11-01).

### Wording this section qualifies

- Amendment (2): "The filer's territory is applied afterwards by the effective-deadline
  service, whose behaviour is unchanged" no longer holds; `closes_on` on the national
  basis is the close every surface shifts, with no territory step.
- Amendment (2), follow-up: the art. 30.6 review is settled by this section.

### Follow-up recorded, not decided here

- The public-holiday facts still cite `ley-39-2015:art-30.6` in their `legal_refs`; the
  registry owner should review the citation against this ruling.
- `CalendarCcaaCatalogue.territory_for_tax_residence` has no caller outside its own test.
