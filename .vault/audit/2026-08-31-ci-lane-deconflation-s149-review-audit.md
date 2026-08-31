---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c08f649154470b002921fb7eace234aa974ac7772ea4e7e706ec51940e55672d'
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

# `ci-lane-deconflation` audit: `Review P05 S149 identity resolution split`

## Scope

Independent review of immutable P05.S149 commit `673af7656b`, excluding the later peer plan-only commit. Reviewed the governing plan step, execution record, identity-resolution source and direct consumers, existing real-outcome tests, source budget, baseline/policy scope, and current HEAD. This review made no source, plan, execution-record, or shared-index change.

## Findings

No HIGH or CRITICAL findings. The 205-to-159-line public resolver keeps its verified and ambiguous branches intact and delegates only the no-verified-candidate branch to the cohesive local `_unanchored_identity_resolution` helper. The helper preserves the distinct absent and checksum-unverified outcomes, including grounding, findings, note text, own-identity qualification, and unresolved-role condition. It is private, has no external consumer or export, and the public resolver remains the direct defining contract for production and test callers. Existing real tests cover absent, unverified, positively evidenced anchored, and competing-evidence ambiguous outcomes; in the current advanced peer worktree the focused lane collects and passes 19 tests. The record accurately attributes its historical pre-collection exit 4 to peer storage code importing absent `SensitivityClass` from a then-nonexistent `core.classification` module. Ruff and format evidence pass, the callable remains 159 of 180, and the immutable diff contains no policy or baseline change.

## Recommendations

Approve P05.S149. Keep the four real outcome classes together whenever the resolver's no-verified-candidate branch is further refactored.
