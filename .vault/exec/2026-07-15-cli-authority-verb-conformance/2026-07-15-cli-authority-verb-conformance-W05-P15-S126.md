---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S126'
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
     The S126 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Define secret-free schemas for passphrase change, recovery status, create, rotate, verify, and flat recover and ## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define secret-free schemas for passphrase change, recovery status, create, rotate, verify, and flat recover

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Confirm the six accepted custody result schemas are registered in the named payload module.
- Read each schema field set and confirm no field carries passphrase, key material, or recovery words.
- Probe the whole registry for sensitive field names and classify every match.

## Outcome

All six accepted schemas are registered and secret-free: `config.passphrase.change`, `config.recovery.status`, `config.recovery.create`, `config.recovery.rotate`, `config.recovery.verify`, and the flat `config.recover`. Each declares only non-secret fields: a recovery path, a secure-store directory, a non-secret recovery fingerprint, and booleans.

A registry-wide probe found eleven fields matching a naive sensitive-substring pattern; every one proved to be metadata describing a secret rather than a secret value, such as a boolean `has_secret`, a secret-store directory path, an AEAT period code, and LLM token counts. The distinction matters: a substring rule would have red-lined all eleven and invited weakening the check.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
