---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e24a17c1c6254afa632ffd2f6898891f436ecc3fe1eb17ba149296db4c698c3a'
step_id: 'S04'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---
# Reconcile accepted wizard and profile-bundle composition clauses with the dedicated TUI entrypoint

## Scope

- `.vault/adr`

## Description

- Locate the wizard, profile-bundle, and dedicated-TUI composition decisions through semantic RAG, then confirm live consumers and declarations with full-file reads and targeted `rg`.
- Preserve `cadrumo.application.flows`, the bundle publication/import authorities, and ephemeral passphrase custody as their single canonical homes.
- Amend the accepted wizard substrate so CLI line mode and the dedicated Textual entrypoint are sibling projections over the same flow engine, with no cross-entrypoint import or selector.
- Amend the accepted profile-bundle decision so CLI line mode and the dedicated TUI consume the same application authorities without duplicating flow, export/import, or secret semantics.
- Remove the wizard ADR's final three fallback, safety-net, and degradation statements so every composition clause describes independent sibling entrypoints with no selector.
- Link both amended decisions to the accepted topology authority through the sanctioned VaultSpec editor.

## Outcome

The two older accepted decisions now conform to `2026-08-11-tui-architecture-adr` without changing their application-owned semantics. The obsolete CLI-to-Textual selection clause is removed: CLI retains flags, scripted execution, typed refusal, and line-mode projection; full-screen Textual execution starts only through `cadrumo.entrypoints.tui.launcher`. No new ADR, compatibility bridge, alternate flow engine, bundle writer, importer, or passphrase channel was created.

## Notes

RAG identified the accepted `tui-architecture` ADR as the sole topology and launch authority, while `application.flows`, `export_profile_bundle` / `deserialize_profile_bundle`, and bounded secret custody remain the canonical semantic owners. Live code still contains the legacy selector and reverse imports; this step reconciles the authorizing decisions only, leaving implementation removal to the already-scheduled cutover rows.

Independent review found three residual wizard-ADR phrases that still described CLI line mode as a fallback, safety net, or degradation path for the full-screen TUI. They now state that the dedicated TUI, CLI line mode, and non-interactive driver are sibling projections over the same application flow authority; neither projection selects or imports another.

Focused verification commands and results:

- `uvx vaultspec-core vault check adr-status` - `ok adr-status: clean`.
- `uvx vaultspec-core vault check links` - `ok links: clean`.
- `uvx vaultspec-core vault check schema` - final exit 0 with 29 unrelated plan-research warnings; no finding on either amended ADR or this Step Record.
- `uvx vaultspec-core vault check body-sections` - final exit 0 with 1,211 unrelated legacy document warnings; no finding on either amended ADR or this Step Record.
- `uvx vaultspec-core vault check all` - exit 0 with 1,304 warnings: orphans 2, features 6, exec-mapping 53, body-sections 1,211, schema 29, and modified-stamp 3; every hard dimension is clean.
