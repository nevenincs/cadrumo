---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:bc51e703b1a71dc21189c3654a6c05be2819189ebf35c45a3ab16ec7eb590028'
related:
  - "[[2026-08-05-ci-lane-deconflation-P05-S185]]"
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

# `ci-lane-deconflation` audit: `P05 S185 execution self review`

## Scope

Self-review of the P05.S185 execution record against source provenance `adbdcc8875b9323b3ddc88a1984deea287380c6f`, its five-path manifest, source-size and no-threshold boundary, supplied focused receipts, global size-audit limitation, and excluded non-green scanner result.

## Findings

No CRITICAL or HIGH finding was identified in the S185 attestation.

### s185-size-audit-boundary | low | Global size audit is not green

The global size audit exits 1 for other subjects. It reports no `formula_runtime` offender, which is the only conclusion retained; the record does not claim a global pass.

### s185-scanner-boundary | low | Combined scanner result is excluded

The combined 25/4 scanner result is non-green and unattributed. It is expressly excluded from the S185 acceptance evidence rather than being assigned to this refactor.

### s185-focused-receipts | low | Focused evidence is executor-reported

The record preserves the three supplied focused outcomes and durations without inventing commands whose literal invocations were not supplied.

## Recommendations

- Re-run and independently attribute the non-green global size and combined scanner outcomes when the shared tree is stable; do not use them as S185 acceptance evidence.
