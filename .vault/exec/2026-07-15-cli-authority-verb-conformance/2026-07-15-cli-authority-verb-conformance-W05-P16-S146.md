---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S146'
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
     The S146 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Replace stale help records with accepted profile, recovery, certificate, reset, ledger, and audit descriptions and ## Scope

- `src/cadrumo/application/operator_surface/_help.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace stale help records with accepted profile, recovery, certificate, reset, ledger, and audit descriptions

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Read the curated help records and confirm the cited commands use the accepted grammar.
- Confirm the nested reset lifecycle is cited in its split form.

## Outcome

The help records cite the accepted grammar across the profile, authentication, recovery, certificate, reset, ledger, and audit surfaces. The reset lifecycle appears in its nested split form rather than as a flat verb, and the custody and profile entries cite live commands throughout.

This surface is one of the three the hand-sweep hazard names, and it is under CI enforcement: the suggestion-conformance gate resolves every command cited in the curated help documents against the live Click tree, so a stale citation here fails rather than shipping as a dead operator instruction.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
