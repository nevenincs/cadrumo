---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8f0e0865718a8336920ff67e79720686a5fd0b19fcdab0085283d83c1daee80b'
related:
  - "[[2026-08-22-source-casilla-integration-W05-P16-S98]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
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

# `source-casilla-integration` audit: `S98 M360 terminal refusal review`

## Scope

Independent review of commit `1a76517bcc` and its current-head S98 proof surface: M360 `REFUND_OPERATION` refusal at calculation ingress, the separate M360 `manual_input` route, the census closure projection, and repeated-record export boundary.

## Findings

No actionable findings. The negative proof is limited to `REFUND_OPERATION`: it remains deferred, advisory-visible, absent from resolver ownership and connected fixtures, and cannot claim a projection-row export. It separately verifies the actual `manual_input` binding route remains present. The closure projection is refused with the M360 census work item and exact reopening condition, so the deferral is reviewable rather than silently terminal. No runtime route, registry declaration, or parallel source authority was added.

## Recommendations

Keep the direct source-mesh proof and refusal coverage aligned with the S97 reopening predicate. The exact full-authority coverage test did not complete within this environment's 30-second focused-runner cap during review; retain its current assertion and re-run it in a longer isolated CI lane before any change to the M360 disposition.
