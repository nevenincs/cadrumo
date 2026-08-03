---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:3aec29978ec57a260559e83270250068572f88de18c566f55d2dbe6535fe316a'
step_id: 'S29'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S29 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Rewrite bucket_dek_path as a one-line caller of keystore_sidecar_path, gated by the existing master-key custody suite and ## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite bucket_dek_path as a one-line caller of keystore_sidecar_path, gated by the existing master-key custody suite

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `4425e24ecf`, confirmed at HEAD. `bucket_dek_path` in `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py:27-32` is a one-line caller of `keystore_sidecar_path`, gated by the existing master-key custody suite. Note: the filename constant is still imported from `.._namespace_registry` (line 29) — the retired re-export bridge `S113` targets; not a defect in this Step, since `S27`'s new `keystore_sidecar_path` call itself is clean, but worth knowing this call site is one of the ten still reaching the bridge.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
