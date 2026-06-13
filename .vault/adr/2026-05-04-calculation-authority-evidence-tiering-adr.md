---
tags:
  - '#adr'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-04-calculation-authority-evidence-tiering-research]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` adr: `Calculation authority evidence tiering` | (**status:** `accepted`)

## Problem Statement

The central registry ADR requires legal basis, source evidence, workbook/live
parity, and filing/export verification before a modelo can be considered
filing-grade. The codebase now needs a stricter decision about what different
AEAT and BOE artefacts are allowed to prove.

Without an explicit hierarchy, the system can make two unsafe mistakes. It can
treat AEAT record-design spreadsheets as tax calculation engines because they
contain spreadsheet formulas, or it can treat AEAT help services as the legal
source of a calculation rather than as a parity surface. Both mistakes would
undermine the registry's legal evidence model.

## Considerations

BOE law and regulations are the binding legal basis for tax calculations. AEAT
instructions and manuals are official filing and source guidance, and often
describe casilla-level calculations, but they must be tied back to legal basis
where the calculation is filing-grade.

AEAT web/help programs and Open simulators can provide strong executable parity
evidence if they are safe to use. They are not legal authority. Authenticated
or stateful surfaces must be forbidden for synthetic calculation tests unless
AEAT provides an explicitly authorized integration-test surface.

AEAT record designs are authoritative for import/export layout and field
format, not for tax calculation correctness. A record-design workbook remains
layout evidence even when it contains helper formulas for offsets, row numbers,
or field lengths.

## Constraints

- Filing-grade calculations must carry BOE legal references.
- AEAT instructions and manuals may be source evidence for casilla semantics,
  model-specific instructions, and calculation prose, but must not silently
  replace legal authority.
- Executable parity must use identical synthetic inputs for registry execution
  and the parity surface.
- Remote AEAT state must never be written by synthetic tests.
- Record-design XLS/XLSX/PDF artefacts must not be accepted as calculation
  proof.
- Unsupported or non-executable official artefacts are not blockers to source
  catalogue coverage, but they are evidence gaps for executable calculation
  parity.

## Implementation

Extend the registry validation and verification framework with a four-tier
authority model:

1. `legal_authority`: BOE law, BOE regulations, EU law, autonomous-community
   law, and other binding legal texts. Filing-grade calculations require this
   tier.
2. `official_source_guidance`: AEAT model instructions, AEAT manuals, and AEAT
   published filing guidance. This tier can support casilla semantics and
   formula interpretation when linked to legal authority.
3. `executable_parity_evidence`: AEAT Open simulators, authorized integration
   test services, and true formula-form workbooks. This tier can prove that the
   registry implementation matches an official executable surface, but only
   under remote-state guards and identical synthetic input sets.
4. `layout_authority`: AEAT record designs, file layouts, XSDs, and import or
   export specifications. This tier governs export/import schema and format
   verification only.

The workbook classifier must classify record-design XLS/XLSX artefacts as
layout authority, even when formulas are present. Formula-form classification is
reserved for workbooks that calculate tax/model outputs rather than workbook
layout positions.

Modelo completion gates must report all four tiers independently:

- legal authority coverage
- official guidance coverage
- executable parity coverage, including explicit gaps
- layout/export coverage

## Rationale

This decision prevents false confidence. A spreadsheet formula is not
automatically a tax formula. A web form calculation is not automatically legal
authority. A practical manual can explain filing behaviour but may still need
BOE legal grounding. The registry has to preserve those distinctions in schema,
validation, tests, and execution reports.

The complementary research found that all committed binary XLS files can be
converted to XLSX through LibreOffice, but that conversion exposes record-layout
helper formulas rather than authoritative tax calculations. Therefore the
proper fix is not simply to convert XLS files; it is to classify each converted
artefact by evidential role.

## Consequences

Modelo implementation waves become more rigorous. A modelo cannot claim
calculation parity merely because an AEAT spreadsheet exists. It must either
identify a true executable calculation surface or record that executable parity
is unavailable for that revision and strengthen BOE/AEAT instruction/manual
coverage plus behaviour tests.

The registry schema and validator will need explicit evidence-tier fields or
equivalent typed classifications. Workbook reports, source references, legal
references, and verification expectations must state the tier they satisfy.

The plan remains the governing rollout vehicle. This ADR extends its
verification framework before concrete modelo implementation waves continue.
