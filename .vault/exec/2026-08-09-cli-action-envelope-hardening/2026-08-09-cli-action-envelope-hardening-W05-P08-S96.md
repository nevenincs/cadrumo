---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:89c757b634b78321cef5f0fc6105651a2d64cb7755b9ca694d57675e973fe495'
step_id: 'S96'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate residual Modelo exception recovery producers and forwarding bridges including M303 profile-status, IVA-composition, and filing-evidence active-profile raw-English refusal producers through the canonical locale-neutral precondition/action contract or explicit terminal/no-recovery dispositions and record _preconditions.py as an upstream cross-feature dependency owned by open casilla-schema W01.P01.S01 for reconciliation after release, and migrate the newly introduced work-review exception and precondition producers under the same residual Modelo typed-action or explicit no-recovery contract

## Scope

- `src/cadrumo/application/modelo/_export.py`
- `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- `src/cadrumo/application/modelo/_projection.py`
- `src/cadrumo/application/modelo/_reconcile.py`
- `src/cadrumo/application/modelo/_work_addressing.py`
- `src/cadrumo/application/modelo/_registry_helpers.py`
- `src/cadrumo/application/modelo/_required_binding_gate.py`
- `src/cadrumo/application/modelo/_workflow_gate.py`
- `src/cadrumo/application/modelo/_result_disposition_resolution.py`
- `src/cadrumo/application/modelo/_work_lifecycle.py`
- `src/cadrumo/application/modelo/_calculation_helpers.py`
- `src/cadrumo/application/modelo/_calculation_actions.py`
- `src/cadrumo/application/modelo/_calculation_preparation.py`
- `src/cadrumo/application/modelo/_m349_ledger_guard.py`
- `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `src/cadrumo/application/modelo/_verification_cross_period.py`
- `src/cadrumo/application/modelo/_amendment_actions.py`
- `src/cadrumo/application/modelo/_amendment_kind_resolution.py`
- `src/cadrumo/application/modelo/_external_import_actions.py`
- `src/cadrumo/application/modelo/_filed_revision_observation.py`
- `src/cadrumo/application/modelo/_filing_actions.py`
- `src/cadrumo/application/modelo/_local_observation_actions.py`
- `src/cadrumo/application/modelo/_local_observation_spreadsheet.py`
- `src/cadrumo/application/modelo/_selectors.py`
- `src/cadrumo/application/modelo/_semantic_role_resolution.py`
- `src/cadrumo/application/modelo/_art20_advisory.py`
- `src/cadrumo/application/modelo/_art52_advisory.py`
- `src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`
- `src/cadrumo/application/modelo/_binding_resolution.py`
- `src/cadrumo/application/modelo/_borrador_binding.py`
- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/application/modelo/_dt12_advisory.py`
- `src/cadrumo/application/modelo/_dt12_antiquity_advisory.py`
- `src/cadrumo/application/modelo/_history.py`
- `src/cadrumo/application/modelo/_iva_wallet_gate.py`
- `src/cadrumo/application/modelo/_iva_wallet_seed.py`
- `src/cadrumo/application/modelo/_m036_lifecycle.py`
- `src/cadrumo/application/modelo/_m145_communication_records.py`
- `src/cadrumo/application/modelo/_m210_convenio_lob_advisory.py`
- `src/cadrumo/application/modelo/_prior_domiciliation.py`
- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/application/modelo/_review_package.py`
- `src/cadrumo/application/modelo/_review_package_feedback.py`
- `src/cadrumo/application/modelo/_review_package_recipient_encryption.py`
- `src/cadrumo/application/modelo/_review_package_review_only_workspace.py`
- `src/cadrumo/application/modelo/_review_package_signing.py`
- `src/cadrumo/application/modelo/_taxation_comparison.py`
- `src/cadrumo/application/modelo/_verification_actions.py`
- `src/cadrumo/application/modelo/_revision_persistence.py`
- `src/cadrumo/application/modelo/_action_errors.py`
- `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py`
- `src/cadrumo/application/modelo/tests/test_m303_regimen_simplificado_scope.py`
- `src/cadrumo/application/modelo/_m303_filing_evidence.py`
- `src/cadrumo/application/modelo/_work_review.py`

## Description

- Declare fourteen precondition scenarios for the M303 filing-evidence and profile-readiness conditions.
- Attach the modelo precondition mixin to the profile-readiness error and register a typed filing-evidence error.
- Migrate every operator-facing refusal in the package to a declared scenario or its registered message key.
- Delete the embedded recovery instructions from the amendment, bindings and reconcile refusals.
- Declare the thirty-three verification-finding locale keys in all four catalogues and teach the locale scanner the finding kwarg.
- Rewrite the assertions that matched on deleted sentences so they read the corresponding machine facts.

## Outcome

- The package carries no operator-facing prose refusal; a rescan returns only programmer guards and one internal error the export boundary already converts to a typed cause.
- Three refusals had written out a recovery for the operator to follow: an alternative amend procedure, a bindings-list verb with its flag syntax, and a switch-profile instruction. Those are gone.
- Reuse was preferred to new vocabulary throughout: the workflow gate and the revision-persistence branch consume the filing-evidence scenarios the revision path already declares, and every refusal whose class carried a registered key uses that key rather than a new leaf.
- Only two new locale leaves were required for refusals, because the missing-extra and profile-readiness errors already had registered keys.
- The verification-finding surface referenced thirty-three keys that existed in no catalogue. Declaring them exposed a scanner gap: the parity audit recognised three translation-key kwargs but not the one the finding constructors use, so every finding key counted as an orphan. Teaching the scanner closed both gates, and all four catalogues now report clean.
- The suites owning every changed file pass one hundred and ninety-four tests serially, and the package is lint clean.

## Notes

- Execution was not clean. A broad regular-expression sweep was run across the whole package instead of file by file with a test run between, which took the package from a handful of failures to one hundred and fifty-three. The work was recovered and verified, but the method cost several rounds and produced two self-inflicted defects: a duplicate keyword argument and a fact inserted into context blocks where its variable did not exist. Both were caught by lint before anything ran.
- Deleting a rendered sentence twice removed information that lived nowhere else. The spreadsheet refusal kept only a malformed-row count, losing the offending cell and the operator's raw value; a test asserting the refusal must echo what the operator wrote caught it, and the rows now ride the context. The alias-to-target mapping was preserved the same way. A third case was the opposite error: a fact was attached to the data-type and boolean-domain refusals under a name that did not describe their data, and the redundant strings were deleted instead.
- The step text asks for this module to be recorded as an upstream cross-feature dependency owned by the open casilla-schema step. That is discharged here rather than in source: the code-stands-alone mandate forbids plan identifiers in source comments and docstrings, so the reference direction stays one-way.
- Carry-forward: the shared free-form provider warning channel, the pydantic model invariants across the lifecycle, communication-record and verification-precondition models, and the type guards that report a received type are deliberately untouched. The invariants are programmer-error guards rather than operator refusals.
- Unrelated peer breakage was present throughout and was verified by reading tracebacks rather than assumed: a tightened justificante pattern, derived-id validation rejecting synthetic fixture identifiers, a removed M303 revision, an unsupplied maternity binding in the formula runtime, and the IVA-wallet reconciliation suite. None of those files were touched here.
