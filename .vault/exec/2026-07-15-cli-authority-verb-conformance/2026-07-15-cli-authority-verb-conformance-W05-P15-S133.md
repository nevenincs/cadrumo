---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S133'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S133 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Update the authoritative command manifest to the accepted paths and remove legacy keys and ## Scope

- `src/cadrumo/application/operator_surface/_manifest.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the authoritative command manifest to the accepted paths and remove legacy keys

## Scope

- `src/cadrumo/application/operator_surface/_manifest.py`

## Description

- Read the authoritative manifest module and establish how it sources its command keys.

## Outcome

The manifest holds no hardcoded command keys to migrate or remove. It projects the CLI's own registered result-schema registry, which the CLI adapter enumerates and injects, so the manifest cannot carry a legacy key that the registry does not carry.

This is a stronger end state than the Step anticipated: a hand-maintained key list can drift from the live surface, while a derived projection cannot. The retired keys are absent from the manifest because they are absent from the registry.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
