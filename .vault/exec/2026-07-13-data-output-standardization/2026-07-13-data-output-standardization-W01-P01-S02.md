---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S02'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Derive the integration-fields output dirs (financial, parity store, registry cache) from the state root and delete fields verified vestigial and ## Scope

- `src/cadrumo/core/_config_integration_fields.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Derive the integration-fields output dirs (financial, parity store, registry cache) from the state root and delete fields verified vestigial

## Scope

- `src/cadrumo/core/_config_integration_fields.py`

## Description

- Add the four live financial file-envelope catalogues (`cadrumo_financial_txs_dir`, `cadrumo_invoices_dir`, `cadrumo_attachments_dir`, `cadrumo_usage_ratios_path`) and the registry parity-tape archive (`cadrumo_registry_parity_store_dir`) to the state-root derivation table so their defaults root under `cadrumo_local_storage_root` (financial under `financial/`, parity nested under the derived `audit/` dir).
- Delete `cadrumo_purchase_invoice_evidence_dir` and `cadrumo_ledgers_dir` from `_config_integration_fields.py`; both were verified consumer-less in the S04 liveness audit (their data persists in the encrypted secure-object store).
- Sweep the two deleted fields from the `_normalize_repo_relative_paths` validator tuple in `config.py` and from `env/.env.example`.
- Remove the two secure-storage tests' assertions that the deleted plaintext directories are never written, and drop the now-unused `cadrumo_ledgers_dir` isolation override (and its unused import) from the inventory-verbs CLI test.
- Regenerate `docs/reference/environment-overrides.md` so it drops the two deleted-field rows and matches `dev.docs.env_reference` output byte-for-byte.
- Leave `cadrumo_registry_disk_cache_dir` at its `None` default (its production OS-temp fallback relocation to the cache root is a later-phase concern owned by the loader).

## Outcome

The integration-fields output directories now derive from the one state root, closing the last `PROJECT_ROOT/var/...` effective defaults in the settings surface, and two dead settings fields are gone. Gates: collection is clean repo-wide (12819 collected, unchanged); the inventory, ledger-evidence, and inventory-verbs suites are 30 passed; the settings/env-parity suite and my derivation test (now covering the financial dirs) pass; the `dev.docs.env_reference` freshness and env-example parity gates are 4 passed; ruff clean on touched files.

## Notes

`docs/reference/environment-overrides.md` is a generator-owned page that carried live uncommitted regeneration WIP from a peer at the time of this Step. Before touching it, I generated fresh `render_environment_reference()` output to a scratch file and diffed it against the peer working-tree copy: the only difference was exactly the two deleted-field rows, proving the peer copy was pure deterministic generator output with nothing hand-authored to strand. I therefore removed only those two rows (a targeted edit that preserves the peer's already-generated description refresh), confirmed the page then byte-matches fresh generator output, and committed it. The peer's parallel regeneration becomes a no-op; no work was stranded.
