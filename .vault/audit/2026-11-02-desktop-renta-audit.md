---
tags:
  - '#audit'
  - '#desktop-renta'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:879e54a9196178d7c7340292a1c7bb4e16c222d8802d985bb801955214eae6dc'
related:
  - "[[2026-11-02-desktop-renta-plan]]"
---

# `desktop-renta` audit: `Desktop Renta review`

## Scope

Phase-close review of Phase P01 (Steps S01 to S10) of the desktop Renta plan, on the integrated tree at `bf3d502618`, against the plan, the desktop Renta ADRs and the project rules. Gate verdict: fail; S02, S06 and S07 are reopened.

## Findings

### household-row-state | high | A stated non-zero descendant count with no stored rows is served as known-empty

`src/cadrumo/application/modelo/profile_row_binding.py:72` records an enumeration trace whenever the count path holds any value, and `src/cadrumo/application/modelo/work_form_records.py:255` reads that trace as proof the group is empty. A count of two with no rows is served as `rows_known=True` with no rows, contrary to the canonical-family ADR, which allows known-empty only for a stated zero.

### compare-taxation-caveat-words | high | The comparison's advisory caveat is English in every locale

`src/cadrumo/application/modelo/taxation_comparison.py:111` supplies `individual_branch_caveat`, and `taxation_comparison_operation.py:160` serves it, while `words_language` names the requested language.

### settlement-amount-source | high | The export pays box 0670 when box 0700 says the amount to pay is 0695

`src/cadrumo/application/modelo/export_settlement.py:60` reads the settlement amount from 0670, but the 0700 formula makes the amount 0695 whenever 0693 is above zero, and 0693 is editable on the 2025 layout. The exported payment amounts can then disagree with the declared result.

### credential-gate-regression | medium | The new ascendant schema description trips the credential declaration gate

`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1693` describes the ascendant entry in Spanish with the phrase "clave de discapacidad", which fails `test_the_shipped_schema_declares_every_presumed_credential_secret`.

### waived-refund-refusal | medium | A declared refund waiver refuses the whole calculation

`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/formulas/0001-declarations.toml:288` requires 0694 to be zero. The implementing session's decision recorded in the plan is that only 0700 stays unresolved; P01.S21 carries it out.

### instalment-capability-table | medium | The two-instalment capability is a hard-coded modelo set in core

`src/cadrumo/core/payment_instalment_election.py:56` lists the modelos that allow the split, and `work_form_export_offer.py:347` branches on that list, where every other settlement axis comes from registry facts.

### instalment-rounding-grounding | medium | The 60/40 cent rounding has no cited official rule

`src/cadrumo/core/payment_instalment_election.py:73` rounds the first instalment half-up and writes it into the export without an advisory mark.

### s09-docstring-stale | low | The family rows docstring says the schema has no ascendant object

`src/cadrumo/application/user_profile/family_rows.py:12` predates the ascendant object; the ascendant follow-up rewrites it.

### fixture-source-key | low | The fixture generator uses a development tag as a source key

`native/desktop/frontend/scripts/modelo_fixtures.py:1008` uses the feature tag as a synthetic source key.

## Recommendations

- household-row-state: record the trace only for stored rows or a stated zero, and test a non-zero count with no rows (reopens S02).
- credential-gate-regression: reword the description in English without the phrase, keeping its sensitivity (S02).
- compare-taxation-caveat-words: serve the caveat from the catalogue in four locales (reopens S06).
- settlement-amount-source: compose the settlement from the declared result box, or refuse while 0693 is above zero, and test the export path (reopens S07).
- instalment-capability-table and instalment-rounding-grounding: declare the split as a dated registry fact, and ground or mark the rounding as advisory (S07).
- fixture-source-key: use a neutral synthetic key.
- Link `2026-11-02-desktop-renta-renta-family-canonical-adr` from the plan.
