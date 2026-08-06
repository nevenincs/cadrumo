---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d0290ae92832def1a1bf4f9380a6be4db55222d87a17feb8e5c6d30a6b40befb'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
---
## Scope

Reviewed W01.P05.S08 against the accepted five-domain parity contract, the denominator research, the S07 construct-evidence fold, and the vaultspec-rag discovery results for the application conformance surface. The bounded change covers the application profile projection and a real bundled-registry projection test. The dev-side renderer remains a separate consumer boundary and was not changed because its file already carries peer work.

## Findings

### evidence-axis-separation | low | Revision evidence floors and construct evidence are now separate

The existing `model_law_coverage` field remains the revision-level evidence floor. Each validated revision row now carries a distinct `construct_evidence` ledger with one exact row for every formula, parameter, binding, relation, and selector. The projection does not infer construct proof from casilla membership or from the revision floor.

### casilla-producer-projection | low | Per-casilla producer traces preserve the typed schema inventory

Each row now exposes `casilla_provenance` projected from the S06 producer inventory. Formula, manual, upstream, relation, and informational paths retain their own reason and legal/source references. Relation-backed casillas emit one trace per relation declaration, preserving relation identity and multiplicity instead of flattening them.

### degraded-read-boundary | low | Degraded reads expose schema traces without claiming validated construct evidence

With `validate=False`, the profile keeps the revision's schema-derived producer traces visible but leaves both `model_law_coverage` and `construct_evidence` absent. The row-level `registry_validated=False` stamp makes the authority boundary explicit; absence is not reported as a zero or as a clean evidence result.

### renderer-follow-up | medium | The dev-side flattened renderer still needs a follow-up projection

The application conformance profile is now the source of truth for the two new axes, but the existing dev-side `RevisionConformancePayload` and text renderer do not yet carry the construct rows or casilla traces. That consumer projection must be completed in a subsequent owned wave without touching peer WIP. This is a reporting-surface gap, not a defect in the validated application fold.

## Recommendations

- Keep `model_law_coverage`, `construct_evidence`, and `casilla_provenance` as separate named axes in every downstream renderer.
- Add the dev-side payload projection in a disjoint consumer-owned step, preserving `None) for unmeasured validated axes and the full trace tuples for measured rows.
- Preserve relation multiplicity and producer-specific provenance in JSON; text may render counts and gap summaries but must not replace the machine-readable ledger.
- Keep the scoped basedpyright limitation visible: the current application module still reports 45 pre-existing dictionary-comparator type errors at its existing comparison constructors; the new projection test itself reports zero errors.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/application/registry/tests/test_conformance_profile.py` â€” 25 passed in 43.50s.
- `uv run --no-sync pytest -q src/cadrumo/application/registry/tests/test_conformance_provenance_projection.py` â€” 2 passed in 34.44s.
- `uv run --no-sync ruff check` on the two application projection modules and the new test â€” all checks passed.
- `uv run --no-sync ruff format --check` on the same three files â€” 3 files already formatted.
- `uv run --no-sync basedpyright src/cadrumo/application/registry/tests/test_conformance_provenance_projection.py` â€” 0 errors, 0 warnings, 0 notes.
- `git diff --check` on the S08-owned files â€” clean.
