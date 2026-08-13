---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c6a771c3586ba717064e992e030cada4c753ab37854d6f7e959d8df2d6e16a9d'
step_id: 'S01'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Give CalculationSourceDiagnostic a typed place for an advisory to declare the provisions it asserts itself, distinguished on the diagnostic from the casilla-derived path that the one existing correct instance uses. The two are not alternatives and neither replaces the other. Record the subject distinction on the type so a future author copying the casilla-derived instance onto an eligibility-rule advisory is stopped by the type rather than by convention

## Scope

- `src/cadrumo/application/`
- `src/cadrumo/core/`

## Description

- Add `asserted_legal_refs: tuple[LegalRefId, ...] = ()` to `CalculationSourceDiagnostic`, alongside the existing `legal_refs`/`source_refs` pair.
- Docstring the new field as the ADVISORY-ASSERTED path: provisions the advisory's own message is a claim about, distinct from the CASILLA-DERIVED path (`legal_refs`/`source_refs`, read off a casilla's or binding's own registry grounding).
- Cross-reference both docstrings so a reader on either field sees the distinction, and name the specific failure mode (reading a casilla's whole-article refs onto a claim about one apartado of it) that copying the casilla-derived construction pattern onto this field would reproduce.
- Confirm the two fields default and coexist independently: neither field's presence implies or excludes the other.

## Outcome

`CalculationSourceDiagnostic` now carries a typed place for an advisory to declare provisions it asserts about itself, separate from the existing casilla/binding-derived `legal_refs`. The distinction is recorded on the type via distinct field names and paired docstrings, not left to convention. No existing construction site changed -- 83 sites still construct the model unchanged, and the two fields default to empty independently.

## Notes

Per-site adoption (deciding which catalogue entry each of the ~34 measured advisory sites should declare) is out of scope for this Step and left to the plan's P02 (per-site adjudication). CLI rendering (`entrypoints/cli/_modelo_rendering.py`'s `source_diagnostic_notice`, which projects `legal_refs`/`source_refs` into the operator-facing `Notice` context) does not yet project `asserted_legal_refs`; flagged here as a gap to close once P02/P03 populate the field on a real site, so grounding declared there does not silently fail to reach the operator.

**COMMIT HANDOVER — this file is contended, and a pathspec commit would take a peer's work.** `src/cadrumo/application/aggregation/_source_mesh.py` carries this Step's `asserted_legal_refs` field and docstring pair AND, in the same working copy, an unrelated peer's `relation_ids` field on the same model — a grouping channel for a diagnostic that speaks for several relations at once, with its own untracked test module. The two changes sit within about twenty lines of each other on one class.

`git commit -- <path>` takes WORKING-TREE content for the named path, so it would land the peer's field inside this Step's commit. Use the apply-cached drive instead: read the file's bytes from `HEAD`, apply only this Step's hunks to that copy, produce a HEAD-anchored own-only patch, `git apply --cached --check` then `git apply --cached`, confirm the staged set carries no foreign markers, then commit the verified index. Verify AFTER the commit against its own numstat rather than a pre-commit staged diff.

Recorded here rather than left in session chatter because the hazard belongs to whoever lands this Step, who may not be the author.
