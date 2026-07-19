---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S04'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-17-post-release-distribution-plan placeholders are machine-filled by
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
     The RESOLVED by accepted ADR 2026-07-18-mcpb-signing-publisher-adr, the MCPB ships unsigned by operator decision (no purchased certificate), integrity channel is the published SHA-256 plus in-bundle cohort digest pins already enforced by the bootstrap, no signing identity to bind and ## Scope

- `packaging/mcpb/build.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# RESOLVED by accepted ADR 2026-07-18-mcpb-signing-publisher-adr, the MCPB ships unsigned by operator decision (no purchased certificate), integrity channel is the published SHA-256 plus in-bundle cohort digest pins already enforced by the bootstrap, no signing identity to bind

## Scope

- `packaging/mcpb/build.py`

## Description

- Resolve the MCPB signing-identity requirement through the accepted `2026-07-18-mcpb-signing-publisher-adr`: the MCPB ships unsigned by operator decision (no purchased certificate).
- Record the integrity channel that replaces a signing identity: the published SHA-256 plus the in-bundle cohort digest pins the bootstrap already enforces.

## Outcome

The step's acceptance criterion (an MCPB signing identity binding to the immutable cohort) is met by the operator's accepted decision that there is no signing identity to bind; integrity rides the published SHA-256 and the bootstrap-enforced cohort digest pins in `packaging/mcpb/build.py`. Closed against an accepted resolving ADR, not against a CI run.

## Notes

Retroactive execution record reconstructed from the step row and the accepted ADR; the step was already checked. No new work; vault-only bookkeeping.
