---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bae77b159cba946243077dcaa713f9a9c8c6b372330ec1f504a2d46c7581e828'
step_id: 'S75'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Extend the packaging smoke lane with the uninstall step proving every guarded surface returns to the instructive install refusal after the extra is removed

## Scope

- `dev/packaging`

## Description

- Derive the guarded-surface set from the production `require_optional_extra` call sites by AST walk over the gated subpackage, attributing each guard to the outermost enclosing definition.
- Key the walk on the registry symbol the extra resolves to rather than a literal, and refuse when the derived set is empty.
- Return the extra's exclusive distributions from the artifact check, so the uninstall removes exactly what the wheel says the extra adds.
- Add a second venv installed WITH the extra, and prove every derived guarded surface opens there before anything is removed.
- Uninstall the exclusive distributions and require every derived guarded surface to return to the instructive install refusal.
- Gate the derivation itself against the live tree and against synthetic trees exercising the shapes a text scan gets wrong.

## Outcome

The lane's uninstall claim quantifies over a set the production guard defines, not one the lane's author kept. A guard added to a new entry point enrols itself; a hand list enrols it only when someone remembers. The walk is structural throughout, so a guard nested inside a branch or a helper is found, and prose or a string literal naming the guard is not mistaken for one.

Exclusions are printed rather than dropped. Surfaces driven for reachability that carry no guard of their own, and guarded definitions the package does not export, are both named in the run output and recorded in the manifest, so the coverage is legible instead of implied. The reverse direction fails: a guarded surface the driver never reaches is a hole in the claim, not a note.

A derived set that came back empty would make every downstream assertion vacuously true and read as a pass, so it refuses. The surface driver refuses on an empty outcome list for the same reason.

The positive control is what makes the refusal mean anything: with the extra installed, no guarded surface may report it as missing. What is asserted there is narrow on purpose — only that the extra refusal is absent. A guarded call driven with a deliberately empty input is expected to fail on its own terms, and demanding a success would be asserting that the feature works rather than that the gate opened.

## Verification

    uv run --no-sync pytest dev/packaging/tests/test_absent_llm_uninstall_derivation.py -n0 -p no:cacheprovider -q
    11 passed in 0.31s

The derivation was exercised against the live tree, which yields one guarded surface, `rasterise_pdf_pages_to_base64_png`, and prints the four driven-for-reachability surfaces that carry no guard of their own.

Four mutations were applied from outside the repository. Making the walk match source text instead of the AST reddened the prose-is-not-a-guard test. Downgrading the coverage check to a note reddened the unreached-surface test. Permitting an empty derived set reddened the empty-tree refusal.

The fourth mutation, walking every node instead of the module body so an inner helper is attributed alongside its public callable, came back FULLY GREEN on the first attempt. That is the tell for an ineffective patch, but the patch had landed — the gap was the test, which asserted the reachable set and ignored the unexported one. The nested-helper test now asserts both, and the mutation reds.

## Notes

The full lane was NOT run: it requires a built Python cohort and two real virtualenvs, and building one in this shared worktree is not available here. The re-run command is `uv run --no-sync python -m dev.packaging.smoke_absent_llm --cohort-dir <dir>`. The originating plan row is left unchecked on that basis.

Two live findings emerged and belong to the packaging lane rather than to this Step. The extra's registered probe target is supplied by an unconditional core requirement, which a shipped gate already reds; while that holds, the extra can never probe absent in a core install, and this Step's uninstall assertion would fail loudly rather than pass falsely. Separately, the driver inventory demands the extra's refusal from four surfaces that carry no such guard, which the derivation added here now makes visible.
