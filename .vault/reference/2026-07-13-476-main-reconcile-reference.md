---
tags:
  - '#reference'
  - '#476-main-reconcile'
date: '2026-07-13'
modified: '2026-07-13'
related: []
---

# `476-main-reconcile` reference: `merge conflict inventory and reconciliation map for the 476 rename merge`

Read-only preparation for merging `chore/eliminate-shims` (the 476 rename
campaign, 243 commits ahead) into `main` (99 commits ahead) in the
`chore/476-main-reconcile` worktree. Computed with an in-memory
`git merge-tree --write-tree main chore/eliminate-shims` at main `e2603e7807`
against 476 `0ada78ffb5` on 2026-07-13; no worktree was touched. The 476
worktree still carried ~817 uncommitted files at analysis time, so this
inventory MUST be recomputed against the campaign's final commit before the
real merge.

## Authority at the merge

The 476 branch carries the ACCEPTED rename decisions and they govern:
`2026-07-12-cadrumo-product-rename-adr` (CADRUMO product identity;
referent-based product/authority boundary; the import root becomes
`src/cadrumo`) and `2026-07-12-cadrumo-cli-executable-adr` (the human CLI
executable REMAINS `aeat`; no aliases, no shims). Main's
`2026-07-13-product-rename-adr` overlaps them and differs on the executable
question (it staged an executable rename as a follow-up, which the 476 ADR
rejects): at the merge, mark main's ADR SUPERSEDED by the two 476 ADRs via the
`vault adr supersede` verb, keeping its Stage A record (distributions,
repository, marketing) as historical grounding.

## Conflict inventory (73 paths: 59 content, 10 modify/delete, 4 location)

Classes and intended resolution direction:

- Rename-vs-rename in packaging and release surfaces (`pyproject.toml` region,
  `.github/workflows/publish.yml`, `README.md`, `RELEASING.md`,
  `THIRD_PARTY_NOTICES.md`, `dev/packaging/smoke_*`, `dev/release/*`,
  `docs/_release_*`): both sides renamed the distributions to `cadrumo` /
  `cadrumo-data-*`. Resolve on 476's structure (it also renames the import
  root and test filenames, e.g. `test_cadrumo_data_distribution.py`), then
  graft main-only work absent from 476: the `ofx` extra (GPL-3.0 `ofxtools`
  gating), the `license-files = ["LICENSE", "NOTICE"]` declarations and the
  companion LICENSE/NOTICE files, the `test_license_attribution_chain` gate,
  the corpus-sources 0.2.0 pins, and the runtime copyleft / corpus-reuse
  disclosure sections.
- Docs prose conflicts (`docs/how-to`, `docs/explanation`,
  `docs/architecture`, `docs/disclaimer.md`, `docs/conf.py`): 476 carries the
  docs rework the operator referenced; prefer 476 and re-apply main-only legal
  additions (privacy pointer, non-affiliation callouts) where absent.
- Modify/delete: main deleted kickoff briefs 476 still edits (delete wins);
  476 deleted `docs/_static/aeat-mark-*.svg` brand marks main touched (476's
  deletion wins — the rebrand removes the aeat marks).
- `.vault/index` conflicts: regenerate with `vaultspec-core vault feature
  index` after the merge instead of hand-resolving.

Raw inventory (recompute before the real merge):

- `CONFLICT (content): Merge conflict in .github/workflows/publish.yml`
- `CONFLICT (content): Merge conflict in .vault/exec/2026-05-27-m210-irnr-phase-2-engine/2026-05-27-m210-irnr-phase-2-engine-W01-P02-S06.md`
- `CONFLICT (content): Merge conflict in .vault/index/iva-compensation-chain.index.md`
- `CONFLICT (content): Merge conflict in .vault/index/live-censo-calendar-reconciliation.index.md`
- `CONFLICT (content): Merge conflict in .vault/index/live-pull-verification-sweep.index.md`
- `CONFLICT (content): Merge conflict in .vault/index/m210-irnr-phase-2-engine.index.md`
- `CONFLICT (content): Merge conflict in .vault/index/mcp-protocol-hardening.index.md`
- `CONFLICT (content): Merge conflict in .vault/plan/2026-05-19-iva-compensation-chain-plan.md`
- `CONFLICT (content): Merge conflict in .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md`
- `CONFLICT (content): Merge conflict in README.md`
- `CONFLICT (content): Merge conflict in RELEASING.md`
- `CONFLICT (content): Merge conflict in THIRD_PARTY_NOTICES.md`
- `CONFLICT (content): Merge conflict in dev/docs/serve.py`
- `CONFLICT (content): Merge conflict in dev/packaging/smoke_core.py`
- `CONFLICT (content): Merge conflict in dev/packaging/smoke_split_install.py`
- `CONFLICT (content): Merge conflict in dev/packaging/tests/test_cadrumo_data_distribution.py`
- `CONFLICT (content): Merge conflict in dev/release/__init__.py`
- `CONFLICT (content): Merge conflict in dev/release/tests/test_readiness.py`
- `CONFLICT (modify/delete): docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md deleted in main and modified in chore/eliminate-shims.  Version chore/eliminate-shims of docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md left in tree.`
- `CONFLICT (modify/delete): docs/USERDOCS-KICKOFF-BRIEF.md deleted in main and modified in chore/eliminate-shims.  Version chore/eliminate-shims of docs/USERDOCS-KICKOFF-BRIEF.md left in tree.`
- `CONFLICT (content): Merge conflict in docs/_release_checklist.yaml`
- `CONFLICT (content): Merge conflict in docs/_release_notes_template.md`
- `CONFLICT (modify/delete): docs/_static/aeat-mark-dark.svg deleted in chore/eliminate-shims and modified in main.  Version main of docs/_static/aeat-mark-dark.svg left in tree.`
- `CONFLICT (modify/delete): docs/_static/aeat-mark-light.svg deleted in chore/eliminate-shims and modified in main.  Version main of docs/_static/aeat-mark-light.svg left in tree.`
- `CONFLICT (content): Merge conflict in docs/architecture/index.md`
- `CONFLICT (content): Merge conflict in docs/conf.py`
- `CONFLICT (content): Merge conflict in docs/disclaimer.md`
- `CONFLICT (content): Merge conflict in docs/explanation/building-on-earlier-filings.md`
- `CONFLICT (content): Merge conflict in docs/explanation/editing-and-verifying.md`
- `CONFLICT (content): Merge conflict in docs/explanation/from-records-to-figures.md`
- `CONFLICT (content): Merge conflict in docs/explanation/index.md`
- `CONFLICT (content): Merge conflict in docs/explanation/recording-a-filing-and-the-boundary.md`
- `CONFLICT (content): Merge conflict in docs/explanation/reviewing-and-exporting.md`
- `CONFLICT (modify/delete): docs/how-to/classify-with-llm-evidence.md deleted in main and modified in chore/eliminate-shims.  Version chore/eliminate-shims of docs/how-to/classify-with-llm-evidence.md left in tree.`
- `CONFLICT (content): Merge conflict in docs/how-to/classify-with-llm.md`
- `CONFLICT (content): Merge conflict in docs/how-to/file-at-aeat.md`
- `CONFLICT (content): Merge conflict in docs/how-to/import-bank-statements.md`
- `CONFLICT (content): Merge conflict in docs/how-to/index.md`
- `CONFLICT (modify/delete): docs/how-to/justificante-receipts.md deleted in main and modified in chore/eliminate-shims.  Version chore/eliminate-shims of docs/how-to/justificante-receipts.md left in tree.`
- `CONFLICT (content): Merge conflict in docs/how-to/quickstart.md`
- `CONFLICT (modify/delete): docs/how-to/read-live-aeat-data.md deleted in main and modified in chore/eliminate-shims.  Version chore/eliminate-shims of docs/how-to/read-live-aeat-data.md left in tree.`
- `CONFLICT (modify/delete): docs/how-to/setup-llm-classification.md deleted in main and modified in chore/eliminate-shims.  Version chore/eliminate-shims of docs/how-to/setup-llm-classification.md left in tree.`
- `CONFLICT (content): Merge conflict in docs/how-to/troubleshooting.md`
- `CONFLICT (content): Merge conflict in docs/index.md`
- `CONFLICT (content): Merge conflict in docs/tutorials/index.md`
- `CONFLICT (content): Merge conflict in docs/updates.md`
- `CONFLICT (content): Merge conflict in docs/verification/cowork-install-proof.md`
- `CONFLICT (content): Merge conflict in docs/verification/neve-marketplace-install-proof.md`
- `CONFLICT (content): Merge conflict in docs/verification/support-matrix.md`
- `CONFLICT (content): Merge conflict in docs/workstation-setup.md`
- `CONFLICT (content): Merge conflict in justfile`
- `CONFLICT (modify/delete): packaging/aeat_data_manuals/README.md deleted in chore/eliminate-shims and modified in main.  Version main of packaging/aeat_data_manuals/README.md left in tree.`
- `CONFLICT (modify/delete): packaging/aeat_data_official/README.md deleted in chore/eliminate-shims and modified in main.  Version main of packaging/aeat_data_official/README.md left in tree.`
- `CONFLICT (file location): packaging/aeat_data_manuals/LICENSE added in main inside a directory that was renamed in chore/eliminate-shims, suggesting it should perhaps be moved to packaging/cadrumo_data_manuals/LICENSE.`
- `CONFLICT (file location): packaging/aeat_data_manuals/NOTICE added in main inside a directory that was renamed in chore/eliminate-shims, suggesting it should perhaps be moved to packaging/cadrumo_data_manuals/NOTICE.`
- `CONFLICT (content): Merge conflict in packaging/cadrumo_data_manuals/hatch_build.py`
- `CONFLICT (content): Merge conflict in packaging/cadrumo_data_manuals/pyproject.toml`
- `CONFLICT (file location): packaging/aeat_data_official/LICENSE added in main inside a directory that was renamed in chore/eliminate-shims, suggesting it should perhaps be moved to packaging/cadrumo_data_official/LICENSE.`
- `CONFLICT (file location): packaging/aeat_data_official/NOTICE added in main inside a directory that was renamed in chore/eliminate-shims, suggesting it should perhaps be moved to packaging/cadrumo_data_official/NOTICE.`
- `CONFLICT (content): Merge conflict in packaging/cadrumo_data_official/hatch_build.py`
- `CONFLICT (content): Merge conflict in packaging/cadrumo_data_official/pyproject.toml`
- `CONFLICT (content): Merge conflict in packaging/mcpb/manifest.json`
- `CONFLICT (content): Merge conflict in packaging/mcpb/tests/test_build.py`
- `CONFLICT (content): Merge conflict in pyproject.toml`
- `CONFLICT (content): Merge conflict in src/cadrumo/agent/_workspace.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/agent/tests/test_plugin_workspace.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/core/compatibility_lifecycle.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/core/resources/tests/test_corpus_companion_seam.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/domain/calculations/registry/_corpus_catalogue.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/entrypoints/mcp/_server.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/entrypoints/mcp/tests/test_server_refusal.py`
- `CONFLICT (content): Merge conflict in src/cadrumo/tests/test_wheel_bundles_corpus_and_registry.py`
- `CONFLICT (content): Merge conflict in uv.lock`

## Post-merge follow-ups (the deferred PyPI-surface miss hunt)

1. Re-run the distribution-name sweep greps against the MERGED tree
   (`aeat-cli`, `aeat_cli-`, `aeat-data-`, `pypi.org/project/aeat`,
   `github.com/nevenincs/aeat`, `uvx aeat==`) — this is the authoritative
   pass the operator deferred until after the merge.
2. Register PyPI pending Trusted Publishers for `cadrumo`,
   `cadrumo-data-manuals`, `cadrumo-data-official` (owner `nevenincs`,
   repository `cadrumo`, workflow `publish.yml`, environment `pypi`) —
   operator web-UI action; then publish the root `cadrumo` wheel and
   deprecate the old `aeat-cli` / `aeat-data-*` projects with tombstone
   notices.
3. Update the `nevenincs/neve-marketplace` listing to the plugin identity the
   476 ADRs decide, and re-verify the MCPB bundle against the merged tree.
4. Re-run the licence sweep and the packaging gates against the merged tree
   (the import-root rename moves `src/aeat` to `src/cadrumo`, which the
   publish workflow's wheel-content guard and the corpus locator reference).
