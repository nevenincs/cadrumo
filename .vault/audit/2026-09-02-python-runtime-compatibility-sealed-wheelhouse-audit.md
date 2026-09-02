---
tags:
  - '#audit'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9e00791ddc21f50ad6fd6b676b98056c5d5b9c67d38f3959df36db746233f503'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
  - "[[2026-09-02-python-runtime-compatibility-adr]]"
  - "[[2026-09-02-python-runtime-compatibility-research]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace python-runtime-compatibility with a kebab-case feature tag, e.g. #foo-bar.
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

# `python-runtime-compatibility` audit: `Sealed runtime wheelhouse review`

## Scope

Audited the runtime-specific sealed wheelhouse planner, immutable cohort handoff,
offline binary installer, plugin consumer, and detector tests against the accepted
runtime-compatibility decision and `P06.S71`. The review covered lock and cohort
digest binding, per-runtime selection, platform closure, archive member integrity,
missing-wheel attribution, and preservation of the exact CPython 3.13.11 builder.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW findings were identified. The binary probe now
extracts only the manifest-selected runtime subtree, installs every third-party
dependency with `--offline`, `--no-index`, `--find-links`, `--only-binary :all:`,
and `--require-hashes`, and records the observed runtime before a missing-wheel
selection failure. Real CPython 3.13 and 3.14 probes passed from one clean cohort;
the advisory 3.15 closure remains explicitly attributable to `pydantic-core` and
`pyyaml` wheel gaps.

## Recommendations

No blocking recommendations. Retain the per-runtime manifest rows and rerun the
same clean-cohort evidence when 3.15 reaches the promotion point.

