---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:8346e72c63249c35d1fcaa6316bb08ef43428304c0c44abdc265a749a1e64312'
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

# `ci-lane-deconflation` audit: `P05 S130 code review`

## Scope

Independent review of S130 predecessor `dfdd054b32` and closure `80d4f65aa4`, the CI-lane plan and evidence ADRs, all five owner modules, direct consumers, terminal-precondition inventory, tests, size/baseline state, and current `HEAD`.

## Findings

No HIGH, CRITICAL, MEDIUM, or LOW findings.

## Recommendations

No follow-up is required from this review.

The split has coherent direct ownership: IVA screening, IVA refusal, Renta expenses, retenciones and support live in their respective defining modules, while `_modelo_bindings.py` keeps calculation-facing resolver assembly without a facade re-export. The terminal inventory includes the refusal and retenciones owners; M100/Renta, IVA/refusal and retenciones paths retain their real focused evidence. The execution record supplies executable commands and literal `20 passed` plus intentional M100 deselection evidence. All owners remain below the default ceiling; `_modelo_bindings.py`'s stale hub pin is explicitly deferred only to P05.S227, with no baseline raise.

