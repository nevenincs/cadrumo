---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S125'
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
     The S125 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Remove schema registrations for lock, rekey, legacy recovery, and sandbox-use commands and ## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove schema registrations for lock, rekey, legacy recovery, and sandbox-use commands

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Materialise the command-result registry through the live command tree and enumerate the retired keys.
- Confirm no registration remains for the lock, unlock, rekey, legacy show-recovery and verify-recovery, or sandbox-use commands.
- Confirm the named payload module declares no result class for any retired door.

## Outcome

The named surface carries no registration for any retired command. A live-registry probe reports `config.lock`, `config.unlock`, `config.rekey`, `config.show-recovery`, `config.verify-recovery`, and `config.profile.sandbox.use` all absent from the 295-entry registry.

The removals are additionally locked going forward: the retired-key absence gate landed under S137 fails if any of these keys is registered again, and that gate was mutation-verified to fire when a retired key is resurrected. The surviving references to the retired doors are the guard tests that assert their absence, which is the correct end state rather than a residue.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
