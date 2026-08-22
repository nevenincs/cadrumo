---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:ed791a6c867958a7a09b051a069cffc256f986c9b069df0c570d99c3ba253399'
step_id: 'S12'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-registration-password-policy with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-08-22-profile-registration-password-policy-plan placeholders are machine-filled by
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
     The Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then delete repository-wide policy bloat and stale prose, reconcile docstrings, and regenerate only feature-owned API and operator documentation and ## Scope

- `repository profile credential documentation surface` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then delete repository-wide policy bloat and stale prose, reconcile docstrings, and regenerate only feature-owned API and operator documentation

## Scope

- `repository profile credential documentation surface`

## Description

- Sweep source, tests, shipped documentation, locale references, and generated API surfaces for retired profile-credential policy and compatibility paths.
- Remove the remaining password-shaped recovery exception path and give recovery representation and proof a dedicated typed custody refusal.
- Reconcile password and recovery exception docstrings with prospective representation and cryptographic proof semantics.
- Regenerate API stubs and retain only feature-owned custody and user-profile additions.
- Prove exact obsolete-symbol absence, focused recovery behavior, error-registry binding, formatting, and generated-stub state.

## Outcome

No shipped operator guide or README states the retired policy, so no user-facing documentation rewrite was required. No eight-character profile policy, removed policy symbol, alias, shim, or raw presentation diagnostic remains. Recovery no longer raises or catches `ProfileCustodyPasswordError`; the dedicated recovery refusal is exported and registry-bound. Feature-owned API stubs now expose the recovery codec and the authentication and prospective-password modules.

## Notes

Focused recovery unit tests passed 10 tests and its integration lane passed 27 tests. Error-registry tests passed 23 tests plus 7 enforcement tests. Ruff lint and format checks pass on the owned surface. The API generator was run in apply, check, and audit modes; after retaining only feature-owned deltas it reports unrelated baseline drift in operator-surface and source-connectivity modules. The broad exception-hygiene scan is also blocked by unrelated concurrent `ContentDigest` facade drift. These baselines belong to other active work and were not consumed.
