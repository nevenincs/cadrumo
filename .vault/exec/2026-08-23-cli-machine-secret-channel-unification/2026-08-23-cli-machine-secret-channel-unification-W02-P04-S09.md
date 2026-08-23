---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:59d2a5309f6c8c5c462c608f4e9ed38d2bbfca1912752c9dbcdc46358f73e866'
step_id: 'S09'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-machine-secret-channel-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-23-cli-machine-secret-channel-unification-plan placeholders are machine-filled by
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
     The Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate restore to two conditional canonical payload variants and hard-cut the legacy password field in favor of passphrase and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_restore_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate restore to two conditional canonical payload variants and hard-cut the legacy password field in favor of passphrase

## Scope

- `src/cadrumo/entrypoints/cli/_config/_restore_cli.py`

## Description

- Ground restore behavior and governing decisions through semantic discovery,
  exact symbol search, and current-tree inspection.
- Register strict canonical `passphrase` and `recovery_secret` payload models.
- Select the machine channel once before capsule reads, proof, or publication.
- Route both restore doors through the canonical bounded payload reader and
  verified no-echo prompt fallback.
- Delete the restore-local readers, compatibility selector, duplicated strict
  model configuration, and retired `password` field.
- Update real restore fixtures and add focused hard-cut and variant-isolation
  tests.
- Audit the scoped change for secret safety, ordering, and contract fidelity.

## Outcome

Profile restore now consumes the same paired machine-secret capability as the
other migrated custody verbs. The passphrase door accepts exactly `passphrase`;
the artifact door accepts exactly `recovery_secret`; legacy `password` input is
rejected as an unexpected field. Conflict refusal precedes all reads and the
application restore authorities still perform proof before publication.

## Notes

Focused lint, unit contract, metadata, and real password/recovery restore tests
passed. The campaign-wide real inherited-descriptor subprocess matrix remains
in S13 and S14 by plan design. Unrelated shared-worktree changes were preserved.
