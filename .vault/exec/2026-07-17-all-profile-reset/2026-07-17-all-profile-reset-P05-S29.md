---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S29'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace all-profile-reset with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S29 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Regenerate the CLI reference and operator how-to pages for the reset family from the frozen live surface and ## Scope

- `docs/reference/commands-and-configuration.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate the CLI reference and operator how-to pages for the reset family from the frozen live surface

## Scope

- `docs/reference/commands-and-configuration.md`

## Description

- Regenerate the `docs/cli/**` CLI reference from the frozen live surface through the owning generator (`dev.docs.cli_reference.generate_cli_reference_in_subprocess`); the removed `sandbox use` verb no longer appears and the reset lifecycle renders from live help.
- Confirm no tracked reader doc, sequence contract, or the hand-authored `docs/reference/commands-and-configuration.md` lookup cites a removed reset/sandbox spelling; the `protect-data-access-reset.seq` contract and `protect-data-access.md` how-to already use the accepted `config reset start/status/resume` grammar.

## Outcome

The generated CLI reference tree (`docs/cli/`) is gitignored — it is a build artifact regenerated at docs-build time — so no tracked diff results. CLI-reference conformance and anchor-parity gates green (6 passed); documented-command conformance green (from S27 run). No committable tracked change; the reference is conformant with the removed spellings.

## Notes

- The generated held-out terminology evaluation dataset `src/cadrumo/_data/terminology/evaluation/coverage-report.json` still enumerates `cli-option:aeat config profile sandbox use:*` entries. It is outside this campaign's CLI/doc surface (a terminology-tooling artifact, not scanned by the CLI or grammar gates); flagged for the lead's terminology regeneration.
- No new user-facing how-to prose was authored: the reset family how-to already exists. Any additional reset-family narrative is deferred to the lead per the dispatch brief.
