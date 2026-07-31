---
tags:
  - '#adr'
  - '#verifactu-sii-scope-stance'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:5b05c863721326a5c617f7d9c3b753a68c1b632a3223741b44b02d301fba5f20'
related:
  - "[[2026-05-21-sii-digital-iva-ledger-adr]]"
  - "[[2026-04-27-live-submit-permanently-forbidden-adr]]"
  - '[[2026-07-10-verifactu-sii-scope-stance-research]]'
---

# `verifactu-sii-scope-stance` adr: `Verifactu and SII scope stance` | (**status:** `accepted`)

## Problem Statement

GitHub issue #278 asks for an explicit in/out scope ruling on two AEAT
anti-fraud / IVA-transparency regimes: VERI*FACTU (RD 1007/2023 -- certified
invoicing-software requirements) and SII (Suministro Inmediato de Informacion,
RD 596/2016 -- near-real-time IVA Libros registro supply). Both are invoked
by name throughout the codebase (locale strings, registry topics, a
terminology stub) without a single record stating which is a modelled product
capability and which is not. An operator or contributor reading the code
cannot tell whether "SII" support means the tool tracks the obligation or
transmits it.

The ambiguity is asymmetric: `2026-05-21-sii-digital-iva-ledger-adr`
already modelled SII as a taxpayer-profile enrolment axis that reshapes other
obligations (Modelo 347/390 suppression, Modelo 303 monthly cadence), and that
model is implemented in production code (`sii_enrolled` on
`src/cadrumo/domain/deadlines/_models.py`, `src/cadrumo/domain/deadlines/_profiles.py`,
the wizard catalogue, and the M303 monthly-cadence commits `d3d49b29f` /
`2dbe9d6e8`) -- yet that ADR's own status field still reads `proposed`. VERI*FACTU
has only a registry topic (`src/cadrumo/_data/registry/aeat/topics/verifactu.toml`)
and a draft, uncurated terminology stub
(`src/cadrumo/_data/terminology/concepts/tema-verifactu.toml`) -- no behavioural
model, no profile fact, no obligation representation. This ADR closes the gap:
it ratifies the SII stance retroactively (matching what already shipped) and
issues the first explicit VERI*FACTU ruling.

## Considerations

- **The product's contract is `produce -> verify -> export`, never submit.**
  `2026-04-27-live-submit-permanently-forbidden-adr` and the controlling
  safety charter (issue #116) make live AEAT transmission permanently
  forbidden at the runtime-refusal level (`LiveSubmitForbiddenError`,
  `AeatAccessGate.require_live_write()`). Any regime whose obligation is
  fundamentally a transmission duty -- SII's four-day electronic supply of
  invoice records, VERI*FACTU's real-time or near-real-time record submission
  to AEAT -- cannot be executed by this product regardless of how the
  regime's tracking is modelled.
- **SII and VERI*FACTU are legally distinct regimes**, confirmed and kept
  separate by the SII ADR itself (Consideration "VERI*FACTU is a different
  regime", the `topics/sii-verifactu.toml` -> `topics/sii.toml` +
  `topics/verifactu.toml` split closed 2026-06-29). SII concerns the IVA
  Libros registro (an accounting-ledger transparency duty tied to IVA
  settlement periodicity); VERI*FACTU concerns certified invoice-issuing
  software (a technical requirement on the software that issues invoices,
  RD 1007/2023 Art. 3). Scoping them identically would be a category error
  the prior ADR already avoided; this ADR preserves that separation.
- **SII obligation-tracking is a taxpayer-status fact the deadline engine
  needs regardless of transmission.** A gran empresa, REDEME, or grupo-de-IVA
  taxpayer's SII enrolment changes what other modelos are due and when
  (347/390 suppression, 303 monthly cadence) -- facts this tool's core purpose
  (accurate modelo scheduling and calculation) already depends on. Refusing to
  track SII enrolment would silently mis-schedule Modelo 303/347/390 for every
  SII-enrolled taxpayer, a `no-silent-under-declaration`-class defect for a
  population the tool otherwise serves.
- **VERI*FACTU obligates the invoice-issuing software, not the modelo-filing
  tool.** RD 1007/2023 Art. 3 obligates producers and users of "sistemas
  informaticos de facturacion" (SIF) -- software that issues invoices -- to emit
  records to AEAT (voluntarily in real time, or via the VERI*FACTU-certified
  path) at or near the moment of invoicing. This project has no invoice-issuing
  surface: the ledger domain models `payable_invoice` / `collectible_invoice`
  as evidence records for tax calculation (bytes ingested from bank
  statements, scanned receipts, or `doclink`-fetched documents -- see
  `sensitive-financial-data-secure-storage-only`), not an invoicing engine that
  emits new invoices with a QR code and a chained hash under RD 1007/2023's
  technical schema. VERI*FACTU has no attachment point in the current product
  surface.
- **Target user is a modelo-filing individual, not necessarily an invoice
  issuer.** The `aeat` product journey (issue #197: auth -> ingest -> compute
  -> verify -> export) serves an autonomo or small taxpayer preparing personal
  or business tax returns from already-existing financial records. Many such
  users never issue invoices themselves (salaried-plus-rental, capital-gains,
  wage-earner personas already exercised in the persona-testimonial audits).
  A VERI*FACTU stance is only relevant to the subset who issue invoices --
  today, out of the tool's functional reach either way.
- **Phase-in timeline gives runway, not urgency.** RD 1007/2023 Disposicion
  final cuarta phases VERI*FACTU-population obligations in from 2027-01-01
  (IS taxpayers under Art. 3.1.a) and 2027-07-01 (remaining Art. 3.1 obligated
  taxpayers) -- confirmed in the SII ADR's "Closed 2026-06-29" consequence.
  There is no near-term compliance cliff forcing an immediate VERI*FACTU
  build.
- **Existing terminology/registry stubs for VERI*FACTU are pre-positioned,
  not committed scope.** The `topics/verifactu.toml` topic and the draft
  `tema-verifactu` terminology concept exist so the SII/VERI*FACTU split could
  cite BOE article-level `legal_refs` (RD 1007/2023 Art. 3, Disposicion final
  cuarta) accurately wherever VERI*FACTU is mentioned (e.g. explaining to a
  user why SII and VERI*FACTU are different regimes). They do not imply a
  behavioural commitment; per `glossary-concepts-are-taxpayer-facing` the
  concept stays `draft` (unpublished) until curated.

## Considered options

- **A -- Both in scope, tracked as taxpayer obligations (no transmission).**
  Model SII enrolment (done) and add a VERI*FACTU enrolment/compliance-status
  fact, informing the operator of both duties without ever transmitting.
  Rejected for VERI*FACTU: no invoice-issuing surface exists to attach a
  meaningful compliance status to; a "VERI*FACTU applicable: yes/no" flag with
  no corresponding product capability would be a stub the tool cannot honestly
  act on, inviting the false-signal risk the issue itself warns against.
- **B -- Both out of scope entirely, including SII.** Retire the SII enrolment
  model and stop tracking it. Rejected: SII enrolment already ships and is
  load-bearing for correct Modelo 303/347/390 scheduling for the SII-enrolled
  population; retracting it would regress a real, working obligation-derivation
  feature and reopen the exact scheduling defect the SII ADR fixed.
- **C -- SII in scope (obligation-tracking only, transmission always out);
  VERI*FACTU out of scope until the product gains an invoice-issuing
  surface.** Matches what is already built for SII, keeps VERI*FACTU
  explicitly and honestly absent rather than half-modelled, and states the
  reopening condition. **Chosen.**
- **D -- Defer the decision, leave both ambiguous.** Rejected outright: the
  issue explicitly asks for an ADR that scopes each explicitly in or out;
  deferring reproduces the exact ambiguity (silent product-capability
  assumptions) the issue was filed to close.

## Constraints

- Per `aeat-safety-legal-gates`, no future SII or VERI*FACTU work may add a
  live-transmission path. If either regime's tracking is ever extended,
  transmission (SII's four-day electronic supply, VERI*FACTU's real-time
  record emission) remains permanently out of reach of this product, matching
  `2026-04-27-live-submit-permanently-forbidden-adr`.
- SII's obligation-tracking scope is bounded by
  `2026-05-21-sii-digital-iva-ledger-adr`: enrolment state
  (`not_enrolled` / `mandatory` / `voluntary`), the derived Modelo 347/390
  suppression and Modelo 303 monthly-cadence switch, and the rolling
  four-day obligation surfaced as a standing (non-dated) overview item. This
  ADR does not expand that scope; it ratifies it and updates that ADR's status.
- A VERI*FACTU reopening (Option A revisited) requires its own ADR -- this one
  does not pre-authorize any VERI*FACTU behavioural model. The trigger
  conditions are named explicitly under Consequences.
- Any VERI*FACTU-adjacent `legal_refs` citation added elsewhere in the
  registry or terminology (e.g. explaining the SII/VERI*FACTU distinction to
  an operator) must continue to point at RD 1007/2023 Art. 3 /
  Disposicion final cuarta per `legal-grounding-verifies-bundled-authoritative-corpus`,
  and the `tema-verifactu` terminology concept stays `draft`
  (unpublished/deprecated-eligible) until a future ADR curates it for
  publication, per `glossary-concepts-are-taxpayer-facing`.

## Implementation

No new implementation lands from this ADR. It is a scope ruling:

- `2026-05-21-sii-digital-iva-ledger-adr`'s status is corrected from
  `proposed` to `accepted` in a follow-up housekeeping edit, since its model
  is already implemented and load-bearing in production
  (`src/cadrumo/domain/deadlines/_models.py`, `_profiles.py`,
  `src/cadrumo/application/wizard/_catalogue.py`, `src/cadrumo/core/setup_answers.py`,
  and the M303 monthly-cadence commits).
- VERI*FACTU remains at its current state: a registry `topics/verifactu.toml`
  stub (legal-reference anchor only) and a `draft` terminology concept, with
  zero behavioural code. No profile fact, no obligation class, no CLI surface
  is added for VERI*FACTU by this decision.
- README/ROADMAP or user-facing docs that reference these regimes should state
  the stance in plain language: "this tool tracks whether you are enrolled in
  SII so your other filing deadlines are computed correctly, but never
  transmits SII records to AEAT; VERI*FACTU (certified invoice-issuing
  software) is not supported -- use dedicated invoicing software for that
  obligation." That documentation update is tracked as a follow-up, not part
  of this decision record.

## Rationale

The two regimes divide cleanly along the axis that already governs every
other scope decision in this project: does the obligation attach to
producing tax filings from existing financial records (this tool's job) or
to issuing invoices in real time (a different tool's job)? SII's enrolment
state is a fact about the taxpayer that reshapes filing schedules this tool
already computes -- tracking it (never transmitting it) is a direct extension
of the tool's existing purpose, and it is already built. VERI*FACTU's
obligation attaches to invoice-issuing software emitting certified records at
the moment of invoicing; this tool has no invoice-issuing surface, so there is
no honest attachment point for a VERI*FACTU compliance model today. Modelling
a "VERI*FACTU status" flag with no underlying capability would create exactly
the false-signal risk the issue's acceptance criteria warn against ("the tool
emits no false signal about Verifactu compliance"). Keeping VERI*FACTU out
until the product gains an invoice-issuing surface -- and stating that
condition explicitly -- is more honest than either silence or a hollow flag.

## Consequences

- **SII**: in scope, obligation-tracking only. The taxpayer-facing surface
  (overview engine, deadline schedule, Modelo 303/347/390 applicability) keeps
  the enrolment-derived behaviour already shipped.
  `2026-05-21-sii-digital-iva-ledger-adr`'s deferred items (exact
  Modelo 347/390 exemption article, four-day clock holiday-calendar precision,
  fuel/warehouse-depot collective scope, voluntary opt-in/opt-out census
  timing) remain open follow-up grounding work, not blocked by this ADR.
- **VERI*FACTU**: out of scope. No profile fact, no obligation class, no CLI
  surface. The existing `topics/verifactu.toml` and `tema-verifactu` stubs are
  retained as legal-reference anchors only (they are what let the SII ADR
  correctly disambiguate the two regimes) and are not a commitment to build.
- **Reopening condition**: VERI*FACTU tracking (never transmission) may
  re-enter scope if the product ever grows an invoice-issuing capability (i.e.
  a surface that emits, not merely ingests-as-evidence, invoices) for a
  taxpayer population subject to RD 1007/2023 Art. 3. That reopening requires
  its own ADR; this record does not pre-authorize it.
- **Honesty risk closed**: before this ADR, a reader encountering "SII" and
  "VERI*FACTU" strings scattered across locales, registry topics, and a
  terminology stub had no way to know which was a real capability. This
  record removes that ambiguity for both regimes in one place, satisfying
  issue #278's acceptance criteria.
- **Cost accepted**: users who issue invoices and are VERI*FACTU-obligated
  must use separate certified invoicing software; this tool will not warn them
  of that obligation beyond documentation. That gap is accepted deliberately
  rather than filled with an unverified compliance signal.
