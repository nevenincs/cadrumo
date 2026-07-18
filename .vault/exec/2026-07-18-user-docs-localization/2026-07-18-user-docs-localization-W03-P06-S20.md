---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S20'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence and ## Scope

- `dev/docs/tests`
- `docs/locales` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence

## Scope

- `dev/docs/tests`
- `docs/locales`

## Description

- Run the full `docs-check` lane (docs pytest lane under the docs marker, plus doc8 and interrogate) at HEAD against the real translated content.
- Run the per-language nitpicky warnings-as-errors user-scope build matrix for the first time against real translations (the earlier green was English fallback).
- Run the localization gate module and collect-only on the docs test tree.
- Build the Spanish site end to end as a human-eyeball artifact.

## Outcome

Final matrix GREEN: the full `docs-check` lane (which includes the new catalogue drift gate, the per-language nitpicky `-W` es/ca/hu build matrix, completeness, parity, the full autodoc nitpicky build, doc8, and interrogate) passes 154 passed, 0 failed. Each language completeness gate confirms zero untranslated and zero fuzzy; the Spanish end-to-end build renders the eyeball artifact at the canonical HTML output root (`lang="es"`).

The green state was reached through a triaged evidence chain. The first matrix run returned 148 passed / 3 failed with three distinct causes, each resolved:
- Infra (this campaign): the noncanonical-docs-build-root gate flagged two localization test helpers that pinned their storage root under the build tree, plus a build-driver help string embedding a literal build path the gate's regex mis-read. Fixed by moving test storage to an OS temp dir and rewording the help text.
- Translation (Hungarian): the file-at-aeat page accented the invariant AEAT stems inside term roles, breaking two glossary cross-references; the coordinator restored the bare stems.
- Em-dash ratchet: two em dashes in the English import-export-and-evidence page (from an unrelated docs commit) reworded to parentheses and the three catalogues mirrored, single-msgid delta.

Reconciling the em-dash re-extraction surfaced a latent structural gap: a peer commit had regenerated the environment-overrides reference with new MCP/verdict-cache settings without re-syncing the catalogues, and the completeness gate (reading catalogues against themselves) could not see it. This campaign closed the gap: a new catalogue-vs-source drift gate asserts every page's freshly-extracted source msgid set equals each committed catalogue's, and an honest re-sync landed the drift as a deliberate completeness-debt window until the three translators topped up the five new descriptions per language.

## Notes

One transient peer regression required a re-run: the first final `docs-check` returned 9 failures, all CLI-reference / autodoc-build tests broken by a registry import-time refusal via `_workbook_parity.py` (the localization gates themselves passed). It was fixed at HEAD by peer commit `219ed57a6e`; the re-run against fixed HEAD is the 154-passed green record. The drift gate runs a real gettext extraction, so it carries the integration marker (in a dedicated module, since the completeness module is unit-marked and the two markers cannot share a module) and joins the docs lane by the docs marker.
