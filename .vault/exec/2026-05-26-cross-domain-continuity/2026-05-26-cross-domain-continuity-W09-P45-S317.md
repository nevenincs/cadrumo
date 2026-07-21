---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S317'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add NEXT_ACTION guidance hints to work_verify work_list work_status work_history success/failure outputs per discovery3 #121

## Scope

- `work_calculate already has this pattern (lines 2082-2093 emit explicit next-step guidance)  -  mirror it across the sibling verbs`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

The plan Scope line-refs are stale: the single `_modelo.py` module named in the Step row was split into per-verb transport modules, and the cited `work_calculate` line range no longer exists. The four sibling read/verify verbs (`work list`, `work status`, `work history`, `work verify`) emitted no post-action next-step guidance, whereas `work calculate` already nudges the operator via its saved-confirmation line.

- Add an info-severity `next_action_notice()` helper in `_modelo_rendering.py`, the sibling of the existing `advisory_notice()`, so a post-action next-step hint rides the one uniform Notice channel per the `cli-notices-are-the-only-diagnostic-channel` rule rather than a bespoke result field. Being info severity it never flips the envelope status away from success.
- Emit a next-action Notice on `work list` and `work status` in `_modelo_work_lifecycle_cli.py` (list -> inspect one unit then draft; status -> draft/recalculate then verify, with a copy-paste `work calculate <id>` suggestion).
- Emit a next-action Notice on `work history` in `_modelo.py` (review current state via `work status`, with a concrete suggestion).
- Emit a granted/not-granted next-action Notice on `work verify` in `_modelo_work_verification_cli.py`: granted -> export the filing artefact; not-granted -> resolve the blocking items, recalculate, then re-verify.
- Author five locale leaves (`list_next_action`, `status_next_action`, `history_next_action`, `verify_next_action_granted`, `verify_next_action_incomplete`) across es/en/ca/hu through the sanctioned `python -m aeat.locales set` verb, with genuine translations (not scaffold placeholders), so parity holds and the translation-honesty ceiling does not trip. Message prose cites only bare `aeat ...` command paths so the self-referential-string conformance gate resolves them against the live tree; concrete ids ride the runtime `suggestion` field.
- Update the granted-verify assertion in `test_modelo_work_natural_key.py` (previously `notices == []`) to expect the single info next-action notice; the expected code is derived from the spec, not copied from output.

## Outcome

Behavior-preserving addition of operator next-step guidance on all four sibling verbs. Gates green under sequential pytest: ruff + ruff format clean, ty clean, `python -m aeat.locales scaffold --check` and `audit` ok, and `test_parity` + `test_locale_translation_honesty` + `test_self_referential_string_conformance` = 22 passed (the self-referential gate confirms the new locale command strings resolve against the live CLI tree). Regression sweeps across the work-verb CLI surface: 175 of 177 in the work-ux + natural-key files (the one failure is the pre-existing tracked #53 profile-resolution defect, a Typer usage error at profile setup with no verify involved), plus 52 and 76 passed in two further batches. The originating plan checkbox is deferred to the coordinated plan-reconciliation pass (the plan file is contended); this record stands as the execution evidence.

## Notes

The Step's `work_calculate lines 2082-2093` reference is stale and was not followed literally; the pattern was mirrored semantically. Landing was blocked for over ten minutes by a stale zero-byte `index.lock` (owner process gone) held by a peer; the lock was escalated to the coordinator rather than force-removed, and the source/locale/test commit was armed to land the moment the tree frees, staging only the explicit nine-file pathspec with a zero-foreign guard.
