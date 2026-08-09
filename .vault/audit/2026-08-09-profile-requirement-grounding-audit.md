---
tags:
  - '#audit'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6e49709a792aec95e7738478d9b0bb82a4d8e3711fb03cb261c1f009ff50917b'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# `profile-requirement-grounding` audit: `code review of the requirement-row enrichment across the three consumer surfaces`

## Scope

Mandatory P04.S10 code review of the campaign's implementation (P01-P03), run by a fresh-context reviewer agent against the live file content (the shared `.git/index.lock` in this actively multi-agent worktree was unreliable during the review window, so this was a content review, not a diff review). Files reviewed: `application/user_profile/_commands.py`, `application/user_profile/_preflight.py`, `application/modelo/_profile_readiness_gate.py`, `application/state_projection.py`, `entrypoints/cli/_config_payloads.py`, `entrypoints/cli/_config/_profile_inspect.py`, `entrypoints/cli/_modelo_payloads.py`, `entrypoints/cli/_modelo_readiness_cli.py`, and the touched test modules.

**Verdict: revision required.** All findings below have since been actioned in this same session; the disposition line under each finding records what happened.

## Findings

### label-bypasses-canonical-resolver (high)

Both requirement builders read `field.description` (long-form authority prose, deliberately mixed-language) as the operator label instead of `profile_field_label()`, the canonical locale-backed resolver in `domain/user_profile/_labels.py` whose module docstring exists specifically to forbid this. Confirmed a real regression: `identity.tax_id`'s description (`NIF/NIE/CIF used as filing identity.`) rendered where the catalogue label (`Tax ID (NIF/NIE/CIF)` / `NIF/NIE/CIF de identificación`) should have.

**Fixed.** Both builders now call `profile_field_label(section_key, field)`.

### indexed-repeatable-paths-render-raw (high)

`ProfileSchemaDefinition.field()` splits on the first dot only, so a repeatable-section path (`activities.0.description`) never resolves and the blocking gate still printed a bare dotted path for exactly the defect class this campaign exists to remove. Five schema sections are repeatable.

**Fixed.** Both builders now reduce through the canonical `section_field_key()` reducer (`domain/user_profile/_values.py`) before the schema lookup and before splitting into `section_key`/`field_key`.

### grounding-union-dropped-on-baseline-and-validation-rows (high)

`_requirement_for_profile_path` took no `grounding_index` parameter, so baseline and validation-issue rows (built outside `ProfilePreflightService`) never received the registry-binding union even on the two surfaces that pass `authority`. `identity.tax_id` - present in the grounding index with real `legal_refs` - reaches every surface exclusively through this route, so its grounding was silently inert everywhere.

**Fixed.** `_requirement_for_profile_path` and `_validation_missing_requirements` both gained an optional `grounding_index` parameter; `modelo_work_profile_preflight_report` computes the index once (when `authority` is supplied) and threads it into both.

### hot-path-authority-tradeoff-unmeasured (high)

The blocking gate's rationale for omitting `authority` ('an uncached registry walk on every hot-path call would be a real cost') does not survive measurement: the reviewer measured 0.7ms for `build_profile_grounding_index` over the full registry, and the gate already resolves the same authority via `_report_for_target`'s `snapshot()` call. Because both baseline paths (`identity.tax_id`, `activities.description`) declare empty schema `legal_refs`, the blocking gate - the surface the ADR names first - ships label-only with zero legal grounding by design, not as an emergent property.

**Deferred, tracked.** Reopening this (memoising `build_profile_grounding_index` per authority, threading it into `require_profile_ready_for_modelo_work` while keeping `require_existing_profile_baseline_ready_for_modelo_work` registry-free) is tracked as `P06.S18`. The docstring on `modelo_work_profile_preflight_report` was corrected in this session to state the omission is a deliberate scope decision, not a performance necessity. The ADR's Consequences section was also corrected to state the blocking gate does not deliver legal grounding today.

### amendment-rows-never-opened (high)

At review time, plan phase `P05` (implementing the accepted 2026-08-09 ADR amendment on the empty per-operation axis and silent `ready=True` grant) carried prose but zero Step rows.

**Superseded by concurrent work.** A separate session opened `P05.S12`-`S17` and landed `S12` (the `per_operation_requirements_assessed` distinguishing signal on `ProfilePreflightReport`) while this review was in flight. `S13`-`S17` remain open in the plan and are that session's continuing scope, not duplicated here. The plan's `P05` phase description now states this ownership explicitly.

### modelos-field-carries-two-different-meanings (medium)

The `modelos` field meant two different things depending on which of four code routes built the row: the schema-required branch folded in the call's target modelo plus the registry union; the export-identity, conditional, and (pre-fix) baseline/validation branches used only the union or only the target. A single JSON response could carry rows meaning "the target needs this" and "a different modelo's bindings consume this" under one field name with no discriminator.

**Fixed.** `modelos` is now uniformly the grounded registry union (`build_profile_grounding_index` result) and nothing else, in every route; the ad hoc target-modelo folding was removed rather than generalised, per the amendment's ruling 2 ("populated from grounded evidence, never by inference") - folding the call's target modelo into a field named for registry-grounded consumers was exactly the kind of inference that ruling forbids. The ADR's Consequences section now states this is by design and that a row's grounding can name a modelo other than the caller's target.

### duplicate-requirement-builder (medium)

`ProfilePreflightService._requirement` and `_requirement_for_profile_path` independently perform the same job (split, schema lookup, label/legal_refs, grounding union) with drifting behaviour.

**Partially addressed, not merged.** Both builders were brought back into behavioural parity (same label source, same path reduction, same grounding-union semantics) as part of the fixes above, but remain two functions rather than one shared implementation - `_requirement_for_profile_path` operates on module-level `resources()` state while `ProfilePreflightService._requirement` is a bound method reading `self._schema`, and unifying them is a small refactor that was judged separable from closing the correctness gap. Tracked as `P06.S19`.

### modelos-absent-from-both-text-surfaces (low)

The text-line renderers for both `config profile preflight` and `app modelo readiness` printed `label` and `legal_refs` but not `modelos`, unlike their JSON payload siblings.

**Fixed.** Both renderers now append a `modelos` column.

### preflight-builds-the-report-twice (low)

`config profile preflight` builds the full report twice on the ready path (an unresolved-revision probe, then a resolved-revision rebuild), each with its own `authority`-driven grounding-index computation.

**Not fixed, accepted, tracked.** At the measured 0.7ms per build this is negligible; folding it into the hot-path memoisation follow-up is the natural place to remove the duplicate work, not a standalone fix. `P06.S18`'s scope now explicitly names `entrypoints/cli/_config/_profile_inspect.py` to carry this.

### sibling-surfaces-still-emit-raw-keys (low)

`config profile status`, the wizard status surface, and overview diagnostics all read the separate `ProfileKey`-derived `profile_health.missing_required` mechanism and still emit raw dotted paths. Correctly out of scope - the ADR explicitly defers `ProfileKey`/`_DEADLINE_RELEVANT_FIELDS` reconciliation - but the campaign's Consequences paragraph should not be read as covering these three surfaces.

**Not fixed, correctly deferred.** No plan Step exists for this because the ADR already defers the reconciliation this would require. The ADR's Consequences section now names these three surfaces explicitly rather than leaving the deferral implicit.

## What was already correct

The authority split between the hot blocking gate (no `authority` passed) and the two explicit surfaces (`authority` passed) was implemented consistently with no leaks in either direction. `ProfileKey` and `_DEADLINE_RELEVANT_FIELDS` were correctly left untouched - nothing in the campaign's code depends on their reconciliation. Every production construction site of the three enriched types was found and enriched; none were missed. All four locale catalogues carry the message key. No crash path exists on the new required `label` field given its feeding sources' length bounds.

## Recommendations

All high and medium findings are either fixed at this HEAD or carry a named plan Step (`P06.S18`-`S21`); the two low findings marked "accepted"/"correctly deferred" have no further action pending beyond what those same Steps and the corrected ADR text already carry. No new Step is recommended beyond what is already tracked as of this document's last edit.

## Standing-goal note

Per this project's campaign-close discipline: the campaign's Consequences paragraph claims operators get a labeled "why" on every incomplete-profile signal, which is true of the three surfaces this ADR named and false of at least three further surfaces (`config profile status`, wizard status, overview diagnostics) that read the separate `ProfileKey` mechanism. That gap is correctly out of this campaign's chosen scope, but the standing goal ("operators can see why a profile is incomplete, everywhere the CLI says so") still asks for those three surfaces, and nothing currently tracks closing them.
