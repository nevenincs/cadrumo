---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S36'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S36 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The bind the classification finding detail bound to the field it mirrors and add the missing case whose single blocker exceeds it so the truncation branch is proven rather than reasoned and ## Scope

- `src/cadrumo/domain/calculations/registry/_classification_coherence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# bind the classification finding detail bound to the field it mirrors and add the missing case whose single blocker exceeds it so the truncation branch is proven rather than reasoned

## Scope

- `src/cadrumo/domain/calculations/registry/_classification_coherence.py`

## Description

- Add a `_field_max_length` reader that returns a field's declared `max_length` from its own constraint metadata, or `None` when the field carries no upper bound.
- Move the detail bound below the finding model and derive it from `ClassificationCoherenceFinding.model_fields["detail"]` instead of restating the literal beside the field it mirrors.
- Give the clamp an injectable `max_length` defaulting to the derived bound, name the ellipsis as a constant rather than inlining it, and treat `None` as "unbounded field, nothing to clamp".
- Add six cases: the binding assertion, a two-way proof that the reader reads (a 40-bounded and an unbounded synthetic model), the truncation branch driven directly, a lowered-bound proof that the cut point moves, the load-bearing proof that an oversized detail refuses to construct without the clamp and validates with it, and a headroom case built from ids at their schema maxima.
- Re-point the pre-existing many-blockers assertion at the derived bound, removing the last hand-copied 512 in the module's tests.

## Outcome

Both halves of the finding reproduced, and the second one turned out to be sharper than reported. The bound was a hand-copied literal joined to `Field(max_length=512)` by a docstring phrase and nothing executable, and no shipped test reached the truncation branch: the existing many-blockers case lands at 312 characters, comfortably inside the bound, because it exercises the sampler rather than the clamp.

The requested shape — a case whose SINGLE blocker exceeds the bound — is not constructible from legal registry data, and that was measured rather than assumed before deviating. The blocker sentence is built from the modelo id (three digits by pattern), the revision id (128 characters at its schema maximum), the casilla id (64 at its maximum) and the longest `InputKind` repr, which caps a single blocker at 334 characters; wrapped into the divergence sentence that is 472, and the widest case overall — two blockers, so the sampler appends its remainder count — is 495. Manufacturing a longer one would have required bypassing schema validation to build an illegal object, so the truncation branch is instead driven directly against the real function with a real over-bound string, which proves the same branch without asserting behaviour on data the registry forbids.

That measurement produced a finding of its own worth keeping. The widest legal divergence sentence sits 17 characters under the bound. The clamp is therefore not dead code — it is a net with a very thin margin behind the sampler, and a single widened id bound or a slightly longer sentence template would start truncating real findings, silently dropping the prose a reader needs. The headroom case records the measurement as a gate: it asserts the widest legal sentence is not truncated, so losing the margin reds with the measured length in the message. That is the early warning the clamp cannot give, because the clamp's whole job is to absorb the overflow quietly.

Mutation proofs, all three flipping assertions rather than killing fixtures, run by copying the module aside and restoring it byte-identically (`restored identical: True`) rather than by any git operation.

Neutering the clamp to `return detail` fails three: `3 failed, 19 passed in 18.53s`, the failures being the truncation case, the lowered-bound case, and the load-bearing case, the last with a real `ValidationError: String should have at most 512 characters`.

Lowering the field bound to 256 while the constant stays DERIVED fails two: `2 failed, 20 passed in 18.69s`, and — the point — neither is a `ValidationError`. The clamp tracked the bound down to 256 on its own and the fold kept constructing findings. The two failures are the intended early warnings: the headroom case with `the widest legal divergence sentence is being truncated at 256 characters`, and the many-blockers case losing its remainder-count suffix to the cut.

Lowering the same field bound to 256 while the constant is hardcoded back to 512 — the pre-fix code — fails five: `5 failed, 17 passed in 16.34s`, including `ValidationError: String should have at most 256 characters` raised from inside the fold at the finding construction site. That contrast between the second and third runs, same bound change, is the whole value of the binding: derived, the fold degrades gracefully; hand-copied, it aborts the governance read.

Verification, actual output. The owning module plus the composer that consumes it: `74 passed in 19.70s`, collected 74 (22 in the classification module, up from 16). `ruff format` reports `2 files left unchanged`, `ruff check` `All checks passed!`, `ty check` `All checks passed!`. Measured figures for the record: field bound 512, existing 40-blocker case 312 characters, widest legal case 495 and untruncated, headroom 17 characters, direct clamp 562 in and 512 out ending in the ellipsis.

## Notes

Semantic discovery was explicitly waived by the operator for this Step: the RAG index is broken and the service stopped, so grounding was `rg` plus whole-file reads, and the service was not started, restarted, or reindexed.

The deviation from the Step's literal wording is the one thing a reader should check. The Step asks for a case whose single blocker exceeds the bound; no such case exists in legal registry data, and the measurement above is the evidence. The branch is proven directly instead. If a future author wants the fold-level version, it needs either a widened id bound or a longer sentence template — at which point the headroom case reds first and names the problem.

The clamp was deliberately kept rather than removed as unreachable. It is unreachable only while the sampler holds and only by 17 characters, and its absence would convert a prose-length surprise into an aborted governance read on exactly the disagreement the fold exists to surface.
