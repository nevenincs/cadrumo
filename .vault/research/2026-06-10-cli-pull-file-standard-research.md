---
tags:
  - '#research'
  - '#cli-pull-file-standard'
date: '2026-06-10'
related:
  - '[[2026-06-10-live-justificante-reconcile-adr]]'
---



# `cli-pull-file-standard` research: `CLI pull and file flag standardization blast radius`

Operator directive: the CLI must standardize two vocabulary axes. `pull` becomes
the single verb meaning "fetch live data from AEAT" across the whole interface,
and `--file` becomes the single option for a single-file input across every
command. The trigger was the modelo reconcile surface, which had accumulated four
divergent source flags (`--from-justificante`, `--from-declaration`,
`--from-capture`, and a proposed `--from-sede`). This document inventories the
full blast radius — every command, flag, locale family, test, and doc — so the
rollout is complete and auditable. Discovery used the vaultspec-rag
`search_codebase` fast path for the concept ("fetch live data from AEAT verb")
plus `rg` for the exact verb and flag literals.

## Findings

### A. AEAT-fetch verbs to rename to `pull`

Every live-read verb that fetches from AEAT, plus the censo refresh. The
`iva-wallet pull` verb already conforms and is the precedent.

- `aeat app live justificante capture` -> `pull` (`_app_live_justificante_cli.py`)
- `aeat app live expedientes capture` -> `pull` (`_app_live_expedientes_cli.py`)
- `aeat app live expedientes capture-all` -> `pull-all` (`_app_live_expedientes_cli.py`)
- `aeat app live notifications capture` -> `pull` (`_app_live_notifications_cli.py`)
- `aeat app live filed capture` -> `pull` (`_app_live.py`)
- `aeat app live filed capture-all` -> `pull-all` (`_app_live.py`)
- `aeat app live filed capture-sources` -> `pull-sources` (`_app_live.py`)
- `aeat app live iva-wallet capture-history` -> `pull-history` (`_app_live.py`)
- `aeat app live iva-wallet capture-remote-state` -> `pull-remote-state` (`_app_live.py`)
- `aeat config profile censo refresh` -> `pull` (`_config/_profile_censo.py`)

### B. Single-file inputs to rename to `--file`

`--file` already exists as the precedent (`config auth configure --file` for a
certificate path). Renaming targets are single-file path options only — directory
and output flags (`--output`, `--output-root`, `--registry-root`,
`--source-root`) and enum sources (`ledger doclink --source` is a kind:
gmail/google_drive/url) are explicitly out of scope.

- `aeat app modelo reconcile --from-justificante PATH` -> reconcile group (below)
- `aeat app modelo reconcile --from-declaration PATH` -> reconcile group (below)
- `aeat app modelo reconcile --from-capture SNAPSHOT_ID` -> reconcile group (below)
- `aeat ledger import --source PATH` -> `--file` (`_ledger_import_cli.py`)

### C. The reconcile command becomes a group (supersedes the prior CLI decision)

The `2026-06-10-live-justificante-reconcile-adr` decided the reconcile sources as
flags on a single verb and rejected a live `--from-sede` flag. That CLI-placement
decision is superseded here: `reconcile` becomes a command group:

- `aeat app modelo reconcile pull <work-unit>` — fetch the justificante from AEAT
  (the `pull` standard) and reconcile in one flow. Replaces `--from-capture` /
  the rejected `--from-sede`.
- `aeat app modelo reconcile file <work-unit> --file PATH` — reconcile a local
  file (the `--file` standard). Replaces `--from-justificante` /
  `--from-declaration` and the `reconcile-from-justificante` sugar verb.
- `aeat app modelo reconcile history` — unchanged.

The redundant `reconcile-from-justificante` sugar verb is removed (no-legacy,
pre-beta; the `file` subcommand subsumes it).

### D. Downstream surfaces in the blast radius

- **Locales:** each renamed verb and flag carries a `*_help` key family across all
  four catalogues (`en/es/ca/hu`); each rename is a key move + four translations,
  driven through the `aeat.locales` CLI per `aeat-locales-cli`.
- **Tests:** every CLI test invoking a renamed verb or flag — notably
  `test_live_*_verbs.py`, `test_modelo_reconcile_verb.py`,
  `test_live_read_subgroups.py`, `test_profile_censo_verbs.py`,
  `test_ledger_*`, and the documented-command conformance gate.
- **Docs:** six how-to guides reference the renamed surfaces —
  `modelo-390.md`, `import-bank-statements.md`, `file-at-aeat.md`,
  `check-aeat-notifications.md`, `reconcile.md`, `censo-update.md` — plus the
  generated API/CLI reference.

### E. Durable standard to codify

The rollout should land a project rule (`aeat-cli-pull-and-file-standard`):
`pull` is the only verb for an AEAT live fetch, and `--file` is the only option
for a single-file input. Future commands inherit the convention; the
documented-command conformance gate and a CLI-grammar test guard against
regression.
