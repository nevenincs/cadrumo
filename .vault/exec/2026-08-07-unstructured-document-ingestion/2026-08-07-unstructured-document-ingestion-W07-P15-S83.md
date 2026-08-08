---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:81d99fe7242146566c6674e2d296d4db33e0a53cda0578c06ca47cee85be16c3'
step_id: 'S83'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Activate the inference boundary in one commit by repointing the llm extra probe from PIL to pynvml and guarding the five unguarded cadrumo.llm entry points with require_optional_extra, gated by a meta-path-finder refusal test that proves each refusal without depending on the probe and by the absent-llm packaging lane whose precondition the repoint clears

## Scope

- `src/cadrumo/llm`

## Description

- Repoint the llm extra probe from `PIL` to `pynvml`, the extra's one exclusive requirement.
- Rewrite the rasteriser guard's justification, which named a base dependency the probe no longer reads.
- Guard the five unguarded inference constructors with `require_optional_extra`, each as the first statement.
- Declare `nvidia-ml-py` in the dev group, so the probe reads present where the suite runs.
- Extend the absent-llm lane's driven inventory to the three newly guarded exported constructors.
- Rewrite the refusal test to drive every guarded entry point and re-derive its own inventory from the guards.

## Outcome

The inference boundary is live rather than nominal. The probe previously named
`PIL`, which `pyproject.toml` declares as an unconditional base dependency, so
`optional_extra_available` was permanently true, every `require_optional_extra`
call behind it was a no-op, and the boundary reported healthy while failing
open. `pynvml` is supplied only by `nvidia-ml-py`, which the extra declares and
the core closure does not, so the probe is now true exactly when the extra is
installed.

Six entry points now carry the guard: the rasteriser, which already had one,
plus the vision transcriber, the text field extractor, the text classifier, the
vision classifier and the semantic column-role mapper. The two convenience
wrappers inherit it, because each constructs its class before doing anything
else. Guarding the constructor rather than the wrapper is what makes the
packaging lane's derivation attribute each guard to a name an operator can
reach.

The count in the row is honest but names a different five than the packaging
lane does. Of the lane's five driven surfaces only four were unguarded; the
five new guards include the column-role mapper, which the lane did not drive and
which the governing decision explicitly places on the extra's side as the point
the tabular lane splits at. Three newly guarded constructors were therefore
added to the lane's inventory, without which its own completeness check refuses.

Declaring the NVML binding in the dev group is a precondition, not a
convenience: without it the repointed probe reads absent wherever the suite
runs, every guard fires, and the inference tests refuse instead of executing.
The group already declares the other capability extras for exactly this reason.

## Verification

The probe gate that owns this claim already shipped and was red against the tree
this Step started from. Running its computation over the previous bytes and the
current ones, through the same registry reader, flips the result:

    HEAD  (probe=PIL)     dormant extras -> {'llm': ['pillow']}
    AFTER (probe=pynvml)  dormant extras -> {}

A non-empty mapping is the assertion's failure condition, so the gate was
failing on the prior probe and passes on this one.

    uv run --no-sync pytest src/cadrumo/llm/tests/test_missing_llm_extra_refuses_instructively.py dev/packaging/tests/test_absent_llm_boundary.py dev/packaging/tests/test_absent_llm_uninstall_derivation.py -m "unit or integration" -p no:randomly -q
    18 passed in 36.79s

Removing the guard from one constructor reds the refusal assertion, and names
the surface that stopped refusing rather than failing generically:

    AssertionError: these guarded surfaces did not refuse with 'pip install cadrumo[llm]': [{'name': 'LocalVisionLLMClassifier', 'outcome': 'succeeded', 'hint': ''}]

Dropping one entry from the driven inventory reds the coverage assertion, run
against the real derivation with the inventory as the mutated input:

    CONTROL  full inventory      -> uncovered: [] => PASS
    MUTATION one entry dropped   -> uncovered: ['SemanticColumnRoleMapper'] => FAIL

The positive control is a third test rather than an inference: with the probe
module importable, no surface reports the extra as missing, so a guard wired to
fire unconditionally would fail there.

The import-linter enrolment this Step shares with its sibling row was
re-confirmed by deliberate violation. Two probe modules were created (never an
edit to a tracked file), one reaching persistence from the inference package and
one reaching the inference package from core:

    cadrumo.llm is not allowed to import cadrumo.adapters.persistence:
    -   cadrumo.llm._violation_probe -> cadrumo.adapters.persistence.storage (l.5)
    cadrumo.core is not allowed to import cadrumo.llm:
    -   cadrumo.core._violation_probe -> cadrumo.llm (l.5)

Both probes were deleted and the contracts returned to `6 kept, 0 broken`.

## Notes

The tree churned heavily throughout. The inference package was unimportable
twice mid-run on other agents' in-flight work: first a classifier error subclass
carrying no error-code registry entry, then a module-level name resolving
against nothing. Both cleared on their own and neither was touched.

The working tree was swept into a peer's commit while this Step was in progress,
so the change landed inside `feat(cadrumo): land the in-flight source work`
rather than under its own subject. The one-commit contract is met in substance
and not in form. HEAD was re-read afterwards to confirm the swept content was
the restored version and not the deliberate mutation open moments earlier; all
six guards and the repoint are correct at HEAD.

A broad run over the inference and packaging lanes finished `41 failed, 826
passed` against 867 collected. None of the failures are on this surface: thirty
are one peer's cache-model datetime validation, one is a missing import in a
registry bindings module, one is an undeclared `pydantic_core` import in a
peer's test, and two are wheel-build lanes. No failure mentions the guard, the
extra or the refusal. The `llm-not-persistence` contract later went broken on a
peer's dirty test module reaching the outbound adapter; it was green in this
Step's own runs and the edge is not from this work.
