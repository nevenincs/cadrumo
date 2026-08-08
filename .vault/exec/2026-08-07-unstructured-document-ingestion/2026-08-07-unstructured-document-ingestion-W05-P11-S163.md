---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:5be8efb9b73a93f85b39634c64e0bb5e708502bbcc91689931d277d77d9f629d'
step_id: 'S163'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Make the reinstated-consent-symbol set drive its own verification

## Scope

- `src/cadrumo/tests`
- `src/cadrumo/application/user_profile`

## Description

- Replace the bare `_REINSTATED_CONSENT_SYMBOLS` tuple's prefix-filtered loop with `_REINSTATED_CONSENT_VERIFIERS`, a mapping from each reinstated symbol to the callable that proves it.
- Assert the mapping is total over the declared set at module import, in both directions: a declared symbol with no verifier, and a verifier with no declared symbol, each raise before any test runs.
- Move the three hand-written verification lines into named verifier callables: a live-Settings-field check, a facade-importable-and-callable check on the consent predicate, and a live-enum-member-defaulting-off check on the capability.
- Correct the module docstring's "three names moved out" to four, and record why the shape changed.
- Correct two stale vacuity claims in the eligibility-bar gate: the module docstring and the sweep test's docstring both declared the minting-surface set empty by design; one production surface now mints and the sweep finds it.

## Outcome

The declared set now drives its own verification. Appending an unprefixed fifth member no longer passes silently: it stops the module at import, so the run errors before collection rather than reporting green. The verifier callables each carry teeth, proven separately.

`_MINTER` in the eligibility gate was left unchanged, deliberately: a one-name set that DERIVES its call sites by walking the production AST is the opposite of a hardcoded literal, and that function is the sole token constructor.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_cloud_transport_fully_deleted.py src/cadrumo/llm/tests/test_evidence_marker_declared_at_every_builder.py src/cadrumo/application/user_profile/tests/test_cloud_evidence_eligibility_bar.py src/cadrumo/llm/tests/test_column_role_mapping.py src/cadrumo/llm/tests/test_evidence_consent_gate.py -n0 -q -m unit
    69 passed in 41.92s

The complementary lane selects nothing, and that is stated rather than reported as a second green:

    uv run --no-sync pytest <the three changed gates> -n0 -q -m "not unit"
    17 deselected in 0.16s

Mutation proofs ran from an out-of-repo pytest plugin at module scope, loaded with `-p`, each printing a banner asserted present in the log. The plugin rewrites the gate's SOURCE TEXT in memory and pre-registers the module, so no tracked file was edited.

    MUTATION=none        5 passed in 2.56s   (control, banner printed)
    MUTATION=unprefixed  EXIT=1  AssertionError at import: reinstated consent symbols declared with no verifier: ('totally_nonexistent_consent_symbol',)
    MUTATION=prefixed    EXIT=1  AssertionError at import: same guard, ('cadrumo_totally_nonexistent_setting',)
    MUTATION=orphan      EXIT=1  AssertionError at import: verifiers declared for symbols outside the reinstated set: ('orphaned_verifier_symbol',)

The unprefixed case is the inversion this Step exists for: it passed before and now stops the run. The prefixed twin, which was the discriminating control that failed before, still fails -- now at import rather than in a loop, so the two cases no longer diverge on a name.

Each verifier callable was proven separately by renaming its declared symbol consistently in both the tuple and the mapping, so totality still holds and only the verifier can object:

    MUTATION=teeth_settings    1 failed, 4 passed
    MUTATION=teeth_predicate   1 failed, 4 passed
    MUTATION=teeth_capability  1 failed, 4 passed

## Notes

Both settings-field members share one verifier callable, so the settings teeth case proves that callable once rather than twice.

A concurrent tree-wide sweep commit landed part of this work before it was committed here; the residual delta was committed with an explicit pathspec and verified after the fact with a numstat on the resulting commit.
