---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Rebuild the release cohort so the v0.2.1 train re-runs installed-behavior evidence against the new caches and warm serving and ## Scope

- `dev/packaging/release_cohort.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rebuild the release cohort so the v0.2.1 train re-runs installed-behavior evidence against the new caches and warm serving

## Scope

- `dev/packaging/release_cohort.py`

## Description

- Rebuild the release cohort from the fully-fixed HEAD so the v0.2.1 train
  re-runs installed-behavior evidence against the new caches and warm serving.

## Outcome

- New immutable cohort id
  `a027ea57c148727869bb92354b7961b84c24177c3a0afdadf8e7321b8a84c4c3`,
  version 0.2.1, source commit `df344ddbd782b2f36abef1f65c79e1b350ad5d8d`,
  all twelve members digest-bound. This cohort carries every campaign change:
  the event-loop fix, validation-verdict cache with wheel-stamped verdict,
  shipped corpus text, hardened compiled-registry cache, warm in-process MCP
  serving with wedge fallback, the self-healing MCPB bootstrap, the
  destructive-reset risk declarations, and the digest-fragment install
  enforcement.

## Notes

- This cohort supersedes `616f48fc…` (commit `044e48450e`); the
  distribution-installation-readiness evidence matrix rows (S34 onward) should
  bind to this or a later cohort, not the superseded one.