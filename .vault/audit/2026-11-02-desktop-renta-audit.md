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

## P01 re-review, 2026-11-03 (base bf3d502618, target a66305e9c0): revision required

The prior findings are resolved except s09-docstring-stale (partly) and fixture-source-key. The recorded decisions on settlement composition, the dated instalment split, the kept-apart outline groups, the projection region and revision check, and the shared household NIF validator hold. Tax grounding is from the bundled corpus: Orden HAC/277/2026 for the 60/40 split, LIRPF art. 97.6 for 0693/0694, the 2024 and 2025 AEAT dictionaries for RESINGDEV [0700] and TCNN112 [0695], and LIRPF art. 50.3 for the compensation of negative general bases.

### settlement-waived-refund-pre-2025 | high | Revisions without a computed 0700 pay out the whole refund after the filer waives part of it

`settlement_casilla.py:226-248` and fact `0159-modelo-result-casillas.toml:96` stop settlement only on 0693. Box 0694 (refund waived, art. 97.6 a)) is placed on the 2022 to 2024 layouts, and no production code reads it. With 0670 = -1,000 and 0694 = 400 the export writes DEV_IMPORTE 1,000 instead of 600. Reopens S25.

### art-50-3-gate-fails-open | high | The Art. 50.3 gates pass any applied compensation once the stock or the ceiling is zero or missing

`verification_predicates.py:359-363` returns true when its ceiling is missing or at most zero, and both 2025 gates (`2025/verification_predicates/0001-declarations.toml:13,23`) use it. With 1388 = 0 and 1389 = 5,000 verification passes and 0501 lowers the base with no pending negative base behind it. Art. 50.3 also requires the maximum amount. This predates P01 and needs its own Step.

### instalment-zero-refusal-words | medium | A split refused because the second instalment would be nothing reads as a failure to write the file

`export_settlement.py:221-224` raises `export_draft_write_failed`, and `require_instalment_election_admissible` (`export_accounts.py:404-427`) does not check the condition. Reopens S25.

### typed-0700-pre-2025 | medium | The 2024 revision keeps 0700 (RESINGDEV) as an optional typed box beside a settlement that ignores it

`2024/casillas/0001-declarations.toml:27-33`. A typed 0700 can disagree with ING_IMPORTE or DEV_IMPORTE in the same file. Reopens S25.

### plan-step-text-contradicts-decision | medium | S28 and S29 are closed with Step text that no longer matches what was built

The S28 row describes reading A, while f9796d30e5 implements reading B. The S29 row still includes the remedy offer that moved to S31.

### settlement-unsupported-words | low | The refusal says the official file cannot express a suspended part

The 2020 to 2024 designs do carry the remainder (TCPP112 [0695], PAGONOFRACC). Cadrumo does not compute it.

### s09-docstring-stale | low | The family rows docstring says no command writes ascendants

`family_rows.py:17`, contradicted by the S24 writer.

### fixture-source-key | low | The fixture generator still uses the feature tag as a source key

`native/desktop/frontend/scripts/modelo_fixtures.py:1130`.

### household-limit-modelo-constant | low | The profile writer's row limit hard-codes Modelo 100

`household_row_limit.py:20`.

### nif-error-chaining | low | A refused NIF keeps the typed value in the chained exception

`descendant_rows.py:111-114` and `ascendant_rows.py:94-98` raise inside `except IdentityError` without `from None`.

### Recommendations

- Settlement and 0700 findings reopen S25. The art. 50.3 finding needs its own Step; the maximum-amount requirement is a settled rule of art. 50.3 and is enforced, not offered as a choice.
- Follow-on decision: whether the advisory cent rounding written into ING_IMPORTE_PF1/PF2 can be grounded or must be named as Cadrumo's own in the export receipt.

### m200-art-26-1-ceiling | medium | Modelo 200 compensation maximum stays positive when the base is not positive

Observed during S33, outside the desktop-renta scope: `bin-aplicada-maxima` = min(stock, max(1M, 70% of the base)) remains positive when the taxable base is zero or negative. LIS art. 26.1 limits compensation to the positive base before compensation. Needs checking and an owner in the corporate-tax registry work.
