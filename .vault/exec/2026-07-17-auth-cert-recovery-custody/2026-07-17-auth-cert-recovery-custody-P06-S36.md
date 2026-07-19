---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S36'
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
     The S36 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Migrate the auth, certificate, and recovery help and risk metadata to the accepted grammar and ## Scope

- `src/cadrumo/application/operator_surface/_help.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the auth, certificate, and recovery help and risk metadata to the accepted grammar

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Migrate the recovery family's risk metadata: retire `config.show_recovery` / `config.verify_recovery` rows; add `config.recovery.status` / `verify` (reads), `config.recovery.create`, and `config.recovery.rotate` (destructive - it invalidates the prior recovery code, so the MCP surface elicits confirmation).
- Update the operator-surface contract: CONFIG required children swap the retired spellings for `recovery`; one CUSTODY family mounts `status`/`create`/`rotate`/`verify`.

## Outcome

Help and risk metadata for the auth, certificate, and recovery families all cite only the accepted grammar; the curated operator help surface carried no custody entries to migrate.

## Notes

Auth and certificate rows were migrated by the earlier family cutovers; this Step's remaining delta was the recovery family.
