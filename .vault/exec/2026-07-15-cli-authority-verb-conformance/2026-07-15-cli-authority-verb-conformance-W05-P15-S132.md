---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S132'
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
     The S132 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Update write-policy tokens for the accepted destructive and read-only command paths and ## Scope

- `src/cadrumo/application/storage_write_policy.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update write-policy tokens for the accepted destructive and read-only command paths

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Read the profile-bound write catalogue in the named module and the matcher that consumes it.
- Confirm the accepted destructive paths are covered and determine how nested reset verbs match.
- Establish why the custody verbs are absent from the catalogue rather than assuming a gap.

## Outcome

The catalogue is correct as it stands, and its shape initially reads like a fail-open gap that it is not.

The matcher is prefix-based by design, so the single `config reset` entry covers the nested reset start, status, and resume verbs; a per-verb enumeration is unnecessary rather than missing. The custody verbs `config passphrase change`, `config recover`, and `config recovery` are absent from this catalogue because they are deliberately bootstrap-exempt, carrying the documented rationale that custody verbs own their own session, recovery, and rewrap flow. Adding them here would have been the actual defect.

The catalogue is independently gated: every guarded write path is asserted to name a live command, and that gate carries its own proof that a stale catalogue entry is rejected.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
