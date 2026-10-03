# Renta expense rules and activity-asset amortization

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-149` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 19 files, 4,317 manifest-counted lines, 181,477 bytes, and 40,377 measured tokens. All eight bounded pages were read through their listed ranges. This is static inspection only; I did not import or execute the application, modify `src/`, run tests, or verify the cited tax rules externally.

## Product capabilities

The Renta expense path evaluates a typed ledger expense against a dated category profile and operator/context facts, then turns an eligible result into a first-slice Modelo 100 binding observation. It handles full, fixed-percentage, usage-ratio, statutory-cap, non-deductible, and exclusive-use rules. The expense basis can include input IVA that is not recoverable under the supplied IVA-deduction ratio. Refunds and reversals use negative signs and must link to invoices. Routing from category to casilla is selected from a dated registry mapping matched to the selected Modelo 100 revision; snapshot checks confirm the revision has the target casillas expense evaluation (`src/cadrumo/domain/renta/ledger_expenses.py`) non-recoverable IVA basis (`src/cadrumo/domain/renta/ledger_expenses.py`) dated routing (`src/cadrumo/domain/renta/_first_slice_routing.py`) cross-domain target integrity (`src/cadrumo/domain/renta/first_slice_routing_integrity.py`).

The activity-asset domain records immutable acquisition/election revisions, separates whole-property, taxpayer-owned, and already business-allocated basis so ownership and business-use factors cannot be applied twice, and distinguishes known opening amortization from missing history. It supports linear, constant-percentage, sum-of-digits, approved-plan, useful-life and several bounded free-depreciation methods. Registry-selected schedule authority turns a half-open service interval into a cent-rounded forecast capped at the remaining lawful basis. Separate append-only claims record what was actually claimed; exact retries are reused, overlap conflicts are refused, and explicit supersession replaces the effective claim without erasing history. Projections refer to claim IDs and amounts for M100 or dated cumulative M130 fields basis stages and asset revision (`src/cadrumo/domain/renta/actividad_asset/lifecycle.py`) method election (`src/cadrumo/domain/renta/actividad_asset/election.py`) schedule calculation (`src/cadrumo/domain/renta/actividad_asset/schedule.py`) claim history (`src/cadrumo/domain/renta/actividad_asset/claims.py`) M100/M130 projections (`src/cadrumo/domain/renta/actividad_asset/claims.py`).

Supporting contracts validate vehicle affectation, evidence for low-value/renewable/charging infrastructure methods, employment-based investment conditions, workforce commitments, and transaction-edit lineage. The domain explicitly refuses unsupported shapes such as unapproved vehicle use, missing opening history, unenrolled statutory methods, and a DA 41 tuna-fleet exemption lacking EU state-aid clearance. Maritime helpers calculate Art. 7.p and REBECA exempt amounts with registry fact provenance and expose the RETMAR mandatory-filing gate vehicle affectation (`src/cadrumo/domain/renta/actividad_asset/vehicle_affectation.py`) workforce tests (`src/cadrumo/domain/renta/actividad_asset/workforce.py`) maritime exemptions (`src/cadrumo/domain/renta/maritime_exemption.py`).

The chunk also supplies a rental-reduction token transport type, a registry-routed M130 retenciones output, and a pure retention-floor assessment over filed records. The retention calculation resolves the floor from dated registry data and returns blocking records plus the latest safe-erase instant; it does not itself access storage or delete anything M130 route (`src/cadrumo/domain/renta/retenciones_routing_integrity.py`) retention floor assessment (`src/cadrumo/domain/retention/floor.py`) erase decision helper (`src/cadrumo/domain/retention/floor.py`).

## How it works and knowledge

Expense category profiles, proportionality rules and citations live outside this chunk. The Renta context carries a profile year, use ratios, exclusive-use confirmation, cap inputs, CCAA and the IVA deduction percentage. A missing use ratio or cap yields an ineligible result instead of a fabricated value; a wholly eligible result retains citations. The territorial override resolver is deliberately empty for current categories. A M130 retenciones route and the maritime rates/fractions are registry facts rather than duplicated statutory constants deductibility context (`src/cadrumo/domain/renta/ledger_expenses.py`) maritime fact resolution (`src/cadrumo/domain/renta/maritime_exemption.py`) rental token boundary (`src/cadrumo/domain/renta/rental_reduction.py`).

Schedule arithmetic separates authority selection from calculation. Method-specific authority fields are required or forbidden by a shape validator. Linear and other rate methods use actual calendar-year days; constant percentage, useful-life, and sum-of-digits paths use cumulative curves whose rounded endpoints telescope across adjacent periods. Method changes are restricted to tax-year boundaries, and from-start methods cannot be adopted after an incompatible election has already generated claims. Workforce-conditioned investment caps apply to the asset investment, while the separately requested period charge remains bounded by remaining basis schedule authority (`src/cadrumo/domain/renta/actividad_asset/schedule.py`) method continuity (`src/cadrumo/domain/renta/actividad_asset/schedule.py`) workforce cap (`src/cadrumo/domain/renta/actividad_asset/schedule.py`).

The retention assessment anchors the floor to `filed_at` because no filing deadline is carried on the structural record protocol. It shifts that instant by whole calendar years using the registry-selected floor and conservatively retains a late-filed record longer than a deadline-anchored calculation would. The registry effective date is the assessment date, not the filing date retention record protocol and assessment (`src/cadrumo/domain/retention/floor.py`) safe-erase calculation (`src/cadrumo/domain/retention/floor.py`).

## Security and implementation assessment

The principal safeguards are explicit evidence and refusal: schedule amounts are finite nonnegative euro cents, intervals remain within the tax year, missing opening history blocks computation, repeated claims cannot overlap, and statutory election evidence is structurally tied to the selected method. Asset revisions use stable hashes and preserve acquisition identity; first-slice expense observations re-check their date-scoped route when validated. No live portal or repository access is performed by these domain contracts.

One result-to-source invariant is missing in `build_renta_deductible_expense_observation`. The function refuses ineligible results and checks that the fact and result categories match, but it does not check that `result.transaction_id` and `result.invoice_id` match the supplied fact, or that `result.profile_year` matches the requested observation tax year. It then copies identifiers and dates from the fact but amounts and profile year from the result. A caller that accidentally pairs a result from another expense could therefore construct a structurally valid observation with mixed provenance and values. Add identity and year checks at this public pairing boundary result shape (`src/cadrumo/domain/renta/ledger_expenses.py`) observation builder (`src/cadrumo/domain/renta/ledger_expenses.py`).

Several authority lookups default to the current Madrid date when callers omit a filing/devengo date: the Art. 7.p cap and REBECA fraction explicitly allow that fallback, and the M130 retenciones route always queries today while its snapshot checker discards the supplied `filing_year`. Current-date defaults can select a later declaration during historical corrections. Verify callers always supply the intended coordinate or make it required on filing-grade paths maritime date defaults (`src/cadrumo/domain/renta/maritime_exemption.py`) M130 current-date selector (`src/cadrumo/domain/renta/retenciones_routing_integrity.py`).

The retention package initializer and error-module documentation disagree about live integration: the initializer says the guarded erase was withdrawn and that nothing raises `RetentionFloorError`, while the error module says the configuration reset raises it immediately before destruction. The floor module itself only returns an assessment and decision predicate. Reconcile the documentation with the current application flow before relying on the error’s claimed guard package statement (`src/cadrumo/domain/retention/__init__.py`) error statement (`src/cadrumo/domain/retention/errors.py`) pure assessment boundary (`src/cadrumo/domain/retention/floor.py`).

No tests are included in the assigned chunk. This inspection cannot establish how callers validate schedule authority against current legal catalogues, whether returned incomplete-workforce commitments are followed up, or whether the actual erase path consumes the retention assessment.

## Dependencies and follow-up

At the Renta observation boundary, bind every result to its source transaction/invoice and filing year. Require explicit temporal coordinates for historical maritime and M130 route resolution. Trace activity-asset schedule resolution and claim recording through their secure repository/workflow caller, including claim history and workforce commitments. Reconcile the retention package’s contradictory integration claims and verify the destructive operation has one authoritative, guarded assessment path.

## Complete assigned-file coverage

- `src/cadrumo/domain/renta/__init__.py`
- `src/cadrumo/domain/renta/_first_slice_routing.py`
- `src/cadrumo/domain/renta/actividad_asset/__init__.py`
- `src/cadrumo/domain/renta/actividad_asset/claims.py`
- `src/cadrumo/domain/renta/actividad_asset/election.py`
- `src/cadrumo/domain/renta/actividad_asset/errors.py`
- `src/cadrumo/domain/renta/actividad_asset/lifecycle.py`
- `src/cadrumo/domain/renta/actividad_asset/schedule.py`
- `src/cadrumo/domain/renta/actividad_asset/vehicle_affectation.py`
- `src/cadrumo/domain/renta/actividad_asset/workforce.py`
- `src/cadrumo/domain/renta/errors.py`
- `src/cadrumo/domain/renta/first_slice_routing_integrity.py`
- `src/cadrumo/domain/renta/ledger_expenses.py`
- `src/cadrumo/domain/renta/maritime_exemption.py`
- `src/cadrumo/domain/renta/rental_reduction.py`
- `src/cadrumo/domain/renta/retenciones_routing_integrity.py`
- `src/cadrumo/domain/retention/__init__.py`
- `src/cadrumo/domain/retention/errors.py`
- `src/cadrumo/domain/retention/floor.py`
<!-- /preserved:article -->
