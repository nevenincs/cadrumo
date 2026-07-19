---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S23'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Replace recovery display and rotation spellings with recovery status, create, and rotate and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace recovery display and rotation spellings with recovery status, create, and rotate

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

- Replace `config show-recovery` and its `--rotate` spelling with the `config recovery` subgroup exposing `status`, `create`, and `rotate`.
- Route the CLI through the landed storage lifecycle authority via new application operations `create_recovery_code` / `rotate_recovery_code` in `src/cadrumo/application/user_profile/_custody.py` (create refuses an existing enrollment; rotate requires one; the prior envelope survives an unverified candidate).
- Extend `inspect_recovery_status` with the non-secret recovery fingerprint; `status` never exposes the words.
- Register `config.recovery.status` / `config.recovery.create` / `config.recovery.rotate` payload schemas carrying path, fingerprint, and rotated only.

## Outcome

The recovery display/rotation spellings are gone; the lifecycle subgroup is mounted with typed, secret-free envelopes and enrollment routed through the atomic verified-install storage facade.

## Notes

The old `mint_recovery_code` (which returned the mnemonic on a result record) and `CustodyRecoveryEnrollment` were deleted outright per no-legacy-compatibility; no consumer remained.
