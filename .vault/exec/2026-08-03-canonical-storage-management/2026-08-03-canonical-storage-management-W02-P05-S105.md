---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0edf4810fee335a64eedafd9149d0d0eba332fa5da4985cd8e08eab02b21d919'
step_id: 'S105'
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
     The S105 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Correct the five settings-field defaults that disagree with their taxonomy member's declared subpath, cadrumo_registry_parity_store_dir defaulting to var slash audit slash registry slash parity against a declared audit slash registry slash parity, and cadrumo_financial_txs_dir, cadrumo_invoices_dir, cadrumo_attachments_dir, cadrumo_usage_ratios_path each carrying a var-prefixed default against an unprefixed declaration, dead at runtime since the derived-output validator overrides them from the taxonomy but a live second declaration of an already-drifted name that no gate compares and ## Scope

- `src/cadrumo/core/config.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct the five settings-field defaults that disagree with their taxonomy member's declared subpath, cadrumo_registry_parity_store_dir defaulting to var slash audit slash registry slash parity against a declared audit slash registry slash parity, and cadrumo_financial_txs_dir, cadrumo_invoices_dir, cadrumo_attachments_dir, cadrumo_usage_ratios_path each carrying a var-prefixed default against an unprefixed declaration, dead at runtime since the derived-output validator overrides them from the taxonomy but a live second declaration of an already-drifted name that no gate compares

## Scope

- `src/cadrumo/core/config.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `ab90ba77c1`, confirmed at HEAD. The Step text names `src/cadrumo/core/config.py`; the fields actually live in `src/cadrumo/core/_config_integration_fields.py` (file-citation swapped with S50, see that record). All five defaults dropped the stale `var/` prefix: `cadrumo_registry_parity_store_dir` -> `Path("audit")/"registry"/"parity"`, `cadrumo_financial_txs_dir` -> `Path("financial")/"transactions"`, `cadrumo_invoices_dir` -> `Path("financial")/"invoices"`, `cadrumo_attachments_dir` -> `Path("financial")/"attachments"`, `cadrumo_usage_ratios_path` -> `Path("financial")/"usage-ratios.json"` — each now agreeing with its `StorageCategory`'s declared subpath. Confirmed dead-at-runtime-but-now-consistent per the commit message: `Settings._resolve_output_dirs_under_storage_root` already overrode every unset field from the taxonomy before this fix; the correction removes a live second declaration of an already-drifted name, not a data relocation.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
