---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S134'
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
     The S134 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Update nested command-path token handling and examples for passphrase, recovery, auth, and reset groups and ## Scope

- `src/cadrumo/entrypoints/cli/_errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update nested command-path token handling and examples for passphrase, recovery, auth, and reset groups

## Scope

- `src/cadrumo/entrypoints/cli/_errors.py`

## Description

- Read the command-identifier mapper in the named module.
- Probe it with the passphrase, recovery, auth, and reset group paths and compare each result against the live registry keys.

## Outcome

The mapper handles nested command paths generically rather than by enumerating groups: it drops the root program token, joins the remaining tokens with dots, and maps hyphens to underscores per token, which is the exact inverse of the CLI token convention.

A probe confirms every named group resolves to its real registered key, including `aeat config passphrase change` to `config.passphrase.change`, `aeat config recovery verify` to `config.recovery.verify`, `aeat config auth reset` to `config.auth.reset`, and `aeat config reset start` to `config.reset.start`. Because the handling is generic, the four named groups are correct by construction and a future nested group needs no further change here.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
