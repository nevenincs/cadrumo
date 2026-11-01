---
tags:
  - '#adr'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-11-01'
body_schema: 'body-v1'
body_hash: 'sha256:31d4316565921c7c63897ec4e1675cc300a91b5cd1a0b96e952930b5c454f060'
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
