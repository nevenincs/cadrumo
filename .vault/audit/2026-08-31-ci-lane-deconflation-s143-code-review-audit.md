---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:8ddf1e4e1c84cfe6f7fb614402301d8cc8cee5e52d18e9bbe49dc6965e26f06d'
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

# `ci-lane-deconflation` audit: `P05 S143 independent code review`

## Scope

Independent review of P05.S143 at `80417ba85fd2dc394d81a32c92c60751aa7aada5`, with current HEAD confirmed at that revision. Reviewed the CI-lane plan, applicable rules and audit template, S143 execution record, and all eight changed paths. Checked M200/M390 ownership, direct import routes, old-name removal, semantic behavior, peer-hunk exclusion, evidence completeness, size, and policy/baseline scope.

## Findings

### s143-code-review | high | The execution record omits the reproducible validation evidence required to attest the relocation

The S143 execution record is only 28 lines and records ruff, collection, and semantic-test checks merely as `pass`. It omits complete ruff and format commands/results, compile evidence, the exhaustive 23-name old-route absence proof, literal 32-test collection with zero deselection, the twelve-pass semantic result, and the 1,209/416/120 module measurements against the unchanged cap. A bare success label cannot establish what ran or reproduce the claimed result. Append exact executable commands and literal outputs with exit statuses for each required check.

Source disposition is otherwise clean. The old snapshot module uses private aliases for the moved M200 and M390 contracts; an independent exhaustive check found all 23 moved names absent. `_m200_projection.py` and `_export_producer.py` import the M200 contract directly from its defining sibling. Independent ruff, format, compile, 32-test collection, semantic twelve-pass, and size checks succeed; dimensions are 1,209, 416, and 120 under the unchanged 1,250 limit. The peer target import-order hunk is not part of the commit, and no policy or baseline path changed.

## Recommendations

Repair the HIGH in the execution record only. Add the exact commands, literal outputs, and exit statuses for ruff, format, compile, 23-name absence, collection/deselection, semantic suite, and dimensions; do not change source behavior.
