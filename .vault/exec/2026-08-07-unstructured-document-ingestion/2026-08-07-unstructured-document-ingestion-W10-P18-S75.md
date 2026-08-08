---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6f54aa582fcad95afa88705557f8d7c05203cb37f6a94230af685924b3c1acbd'
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

A later pass closed the gap that kept this lane from ever running, and re-measured the two findings above.

Both findings are now resolved upstream. The extra's probe target was repointed from the package the core closure supplies to one only the extra declares, so the extra can probe absent in a core install. The guard count rose from one to six, and the derivation now yields six operator-reachable guarded surfaces with none unreached by the driver; the driven-but-unguarded set fell from four to the two convenience wrappers, which refuse transitively through the guarded constructors they build.

The lane itself was invoked by nothing. It was named in no campaign lane registry, no justfile recipe and no workflow step, while every other lane module in the directory had at least one dispatch path. Every assertion it makes was true and none had ever been evaluated, which reads identically to a passing lane in every report. It is now registered as a standalone lane, with its own invariant, and selected by both the host-portable profile and the CI superset. Standalone rather than a core form because the core lane asks whether the product works once installed and this one asks what it says when a model-bearing surface is reached without the model-bearing dependencies; and cohort-consuming, unlike the developer lane, because only the built wheel's own metadata can settle whether the extra is real.

A gate now enforces the property rather than the enrolment. Lanes legitimately dispatch three ways, so requiring registry membership would red the four lanes that correctly use a recipe or a workflow instead; what cannot be legitimate is a lane reachable from none of the three. No tally is pinned: both sides are derived at read time.

    uv run --no-sync pytest dev/packaging/tests/test_smoke_lane_dispatch_reachability.py dev/packaging/tests/test_campaign.py -n0 -p no:cacheprovider -q
    16 passed in 1.77s

The reachability gate was mutation-proven by reconstructing the registry as it stood before the enrolment, from outside the repository and with nothing on disk changed. It reddened naming exactly the orphaned lane, and returned green when the real registry was restored. Its positive control drives the detector with a constructed module no surface names, so a detector that returned the empty set unconditionally would fail there rather than pass silently.

The full lane still has NOT been executed end to end, and the reason is now measured rather than assumed. The immutable cohort builder refuses to build against a working tree carrying any drift, and this shared worktree carries peer drift permanently by design; the refusal enumerated twenty dirty paths, none of them this lane's. So the lane cannot be run from this tree at all, and the originating row stays unchecked on that basis. What changed is that CI can now reach it: before the enrolment no profile, recipe or workflow would ever have invoked it, so the run this row waits on could not have happened anywhere.
