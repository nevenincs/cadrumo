---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S142'
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
     The S142 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Replace removed command, option, help, risk, and error nodes with accepted Hungarian grammar and ## Scope

- `src/cadrumo/locales/hu.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace removed command, option, help, risk, and error nodes with accepted Hungarian grammar

## Scope

- `src/cadrumo/locales/hu.yml`

## Description

- Run the locale CLI drift check and confirm the Hungarian catalogue matches the codebase key set.
- Sweep the Hungarian catalogue for citations of the retired command grammar.
- Run the locale gates and the translation-honesty ratchet.

## Outcome

The Hungarian catalogue carries the accepted grammar. Its command, option, help, risk, and error nodes cite only live commands, and `hu.yml` reports `ok` under the CLI drift check.

The catalogue was verified through the locale CLI rather than by reading the file: `scaffold --check` reports `ok`, so no key drifted against the codebase, and the four-way parity and placeholder gates pass. A targeted sweep for the retired grammar finds no surviving citation of the lock, rekey, show-recovery, verify-recovery, sandbox-use, or flat scoped-reset doors.

The citations are also under CI enforcement rather than resting on that sweep: the suggestion-conformance gate walks every string leaf of every catalogue through the live command tree, so a dead command cited in translated text fails a gate. That gate previously caught three real locale-divergent dead citations, so it is proven to bite rather than merely pass.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
