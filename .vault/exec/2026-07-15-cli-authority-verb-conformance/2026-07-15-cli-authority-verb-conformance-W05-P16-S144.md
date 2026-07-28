---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S144'
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
     The S144 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Require four-locale parity and reject orphaned locale nodes for removed grammar and ## Scope

- `src/cadrumo/locales/tests/test_audit.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Require four-locale parity and reject orphaned locale nodes for removed grammar

## Scope

- `src/cadrumo/locales/tests/test_audit.py`

## Description

- Read the named audit gate and enumerate the parity and drift assertions it makes.
- Confirm the gate detects an extra locale node with no codebase reference.
- Run the locale gate suite.

## Outcome

The named surface enforces four-way parity and rejects orphaned nodes. It asserts symmetric key drift without privileging a reference locale, so a key present in one catalogue and absent from another fails from either direction; it reports missing, renamed, and extra placeholders, including root and nested specification kwargs; it rejects boolean and null leaves; and it refuses a blank value on set.

Orphan rejection is live: the audit carries an extra-key verdict, and the committed catalogues pass the production audit, so an orphan left behind by removed grammar is a failure rather than a silent pass. The gate also proves the real audit CLI rejects placeholder drift, so the check and the operator-facing verb cannot disagree. The locale suite runs sixty tests green.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
