---
tags:
  - '#research'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-fresh-cli-persona-repair-plan]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
---

# Fresh CLI persona capability-gap design

Design note for `fresh-cli-persona-repair` `P02.S05` and `P02.S08`.

## P02.S05 - Profile-filtered obligation explanation

Current surface:

- `aeat app overview explain MODELO --year YEAR` already decomposes a
  modelo's applicability against the active profile.
- The application service returns `applicable`, `verdict`, `rationale`,
  `legal_refs`, optional scheduling rationale, and the profile facts the
  decision depends on.
- Persona feedback shows operators did not discover this path after
  profile creation. They inferred applicability from `modelo list`,
  `modelo describe`, and whether `work create` succeeded.

Target shape:

- Keep `overview explain` as the canonical "applies because" command.
- Add post-profile guidance that names `aeat app overview explain
  MODELO --year YYYY` or `aeat app overview calendar` before generic
  `modelo work create` guidance.
- Make the profile-create/edit `next` output depend on taxpayer model
  facts when possible:
  - autonomo/direct-estimation profiles should point to Modelo 130
    explain/calendar discovery;
  - IVA general profiles should point to Modelo 303 explain/calendar
    discovery;
  - legal entities should point to 303/200/202 discovery rather than
    personal IRPF flows;
  - incomplete profiles should point to the exact profile-edit fields
    needed before obligation discovery.
- Do not make profile creation perform filing-calendar decisions itself;
  it should delegate operators to the overview surfaces that already own
  applicability reasoning.

Acceptance criteria:

- A newly created autonomo profile sees a next step that includes
  obligation discovery, not only `aeat app modelo work create`.
- `overview explain 130` for a direct-estimation autonomo states the
  applicable verdict, rationale, legal refs, and relevant profile facts.
- Legal-entity profile creation does not suggest spouse/family IRPF
  work as the next action.

## P02.S08 - Modelo 100 rental-income ledger traceability

Current surface:

- Modelo 100 2025 exposes capital-inmobiliario rental casillas such as
  0109, 0113, 0115, and 0131 as manual casillas.
- The committed ledger-backed Modelo 100 bindings currently target
  economic-activity expense casillas 0186, 0192, 0199, and 0203.
- Persona feedback from Clara was correct: rental deductible expenses
  are visible, but capital-inmobiliario expense traceability from
  ledger/finca records is not available through the current binding set.

Target shape:

- Treat rental-income traceability as a capability gap, not a CLI typo.
- Do not silently map generic economic-activity expense bindings onto
  rental-property casillas.
- The implementation path should first decide the source of truth:
  rental ledger, finca records, amortization ledger, or a source-mesh
  resolver that composes those records.
- Once a source resolver exists, Modelo 100 capital-inmobiliario
  casillas can be enrolled as source-backed bindings with explicit
  readiness diagnostics.

Acceptance criteria:

- The CLI can tell a landlord that capital-inmobiliario casillas are
  currently manual or source-blocked, instead of implying ledger
  traceability exists.
- A future source-backed implementation has per-casilla source refs for
  rental community fees, utilities, local taxes, amortization, and
  retention fields.
- Calculation must not silently calculate rental expenses as zero when
  the operator expected source-backed rental traceability.
