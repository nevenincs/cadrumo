---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5b2979b8977f8ec8a2248299b18af360d2fa238b79149ea336db478977f77819'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `Review P05 S225 machine-secret channel tests`

## Scope

Independent review of immutable P05.S225 commit `e694afb6b6`, its exact five-path scope and execution record, the successful and refusal subprocess families, shared support topology, cleanup fixtures, live storage ownership imports, size/baseline/policy effects, and immutable plan isolation from peer P02 state.

## Findings

No triaged findings. `_machine_secret_channels_support.py` cohesively owns the real subprocess harnesses, transport helpers, registration/recovery material, snapshots, assertions, and keychain cleanup. The success/recovery/certificate family and the refusal family both import that support directly; the support does not import either test family, so no cross-test facade was introduced. Each test module retains a local autouse cleanup fixture, and a representative success/refusal run exercised both: 3 passed.

The harness imports the live storage builders directly from the defining `_profile_custody.py` and `_profile_login_session.py` modules, not the former storage facade. Rerun ruff and formatting passed. Independent collection reproduced 70 integration cases; the immutable execution record provides an executable command and literal JUnit result of `70 passed in 487.26s` with exit 0. The original test module is 654 lines, below the 1250 cap, and the feature diff has no baseline or policy change.

The immutable plan diff changes only the generated `body_hash` and P05.S225 checkbox. Its parent and commit blobs are distinct from the current peer worktree/default-index plan blob, which preserves unrelated P02 hunks; those peer changes are not attributable to S225.

## Recommendations

Approve P05.S225 as reviewed.
