---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S17'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Re-home the verify_setup_answers cross-field checks into flow-scope validators, enrolling section scope where a check's inputs are complete at phase exit

## Scope

- `src/cadrumo/application/wizard/_verifier.py`

## Description

- Ground the three dormant `verify_setup_answers` checks against Art. 82.1 LIRPF read verbatim from the bundled corpus before re-homing any of them.
- Collapse the joint-vs-situación check and the monoparental-requires-hijos check into one Art. 82.1.2ª rule in `src/cadrumo/application/wizard/_setup_legal_validators.py`: joint declaration plus non-married situación plus no minor children refuses; extend `monoparental_required()` in `src/cadrumo/domain/contribuyente/_renta_codes.py` to all four non-married modalities and upgrade the finding from warning to blocking verdict.
- Drop the obligations-consistency check: no legal or coherence relation between incoming-withholding coverage and the outgoing-retención obligation, and its antecedent field is collected by no setup page.
- Register the merged rule as a `familia` section-exit cross-field validator via `attach_setup_legal_validators` in the `_prepare_interactive_flow` build seam, mirroring the format-hints decoration seam.
- Delete the dead `_verifier.py` and its four test files; re-home the live `SetupAnswers` model-validator coverage; add 12 law-derived real-engine tests in `test_setup_legal_validators.py`.
- Pre-render the wizard success and save-exit notice messages in the command-entry language in `src/cadrumo/application/wizard/_commands.py` so the emitted notice carries the localized string.
- Pin the minor-children proxy rationale in the validator docstring and add a bad-string-token rejection assertion for `situacion_familiar` (review dispositions).

## Outcome

Landed as `5c684d0785` (12 files) plus the review-disposition follow-up `4aae6cfeca`. Independent code review verdict: pass, no critical or high findings; the commit corrects a pre-existing legal defect (childless registered domestic partnerships were previously couple-eligible for conjunta, which Art. 82.1 does not permit). Wizard and flows suites green except the one tracked cross-command language-leak red, owned by the follow-on migration step.

## Notes

- The modify-honesty rendering test stays red at this step's landing: the notice pre-render closes only the first of two stacked causes; the second is a cross-command language-override leak (the mid-walk override remains ambient at the next in-process command entry), fixed in the non-interactive migration step whose acceptance gate is that test green unweakened.
- Review medium (legal edge): a monoparental unit whose only qualifying child is an adult judicially incapacitated child under prorogated patria potestad is a legitimate Art. 82.1.1ª(b) unit the flow cannot represent; the hard refusal is exact within the declared data model and the assumption is now documented at the predicate. Adding that modality later requires widening the predicate and the registry conjunta-reduction signal together.
- Review medium (atomicity): this step's facade export in `__init__.py` was swept into the preceding descendant-group commit by a pathspec commit over the entangled file, leaving that single intermediate commit non-collecting until this step's commit landed the module. Recorded as the pathspec-takes-working-tree incident; parallel executors now receive the full entangled-file exclusion set.
- Orphaned by the verifier deletion: eleven `wizard.setup.verifier.*` locale keys queued for CLI removal in the coordinator's locale window; the surviving rule deliberately reuses `wizard.setup.verifier.monoparental_requires_hijos_warning` whose prose matches the grounded rule.
