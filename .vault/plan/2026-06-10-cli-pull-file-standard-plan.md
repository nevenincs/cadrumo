---
tags:
  - '#plan'
  - '#cli-pull-file-standard'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-cli-pull-file-standard-adr]]'
  - '[[2026-06-10-cli-pull-file-standard-research]]'
---


# `cli-pull-file-standard` `CLI pull and file standardization rollout` plan

### Phase `P01` - Reconcile group

Convert reconcile into a pull/file/history group expressing both standards, with locales, tests, and docs.

- [ ] `P01.S01` - Convert reconcile into a Typer group with pull, file, and history subcommands, removing the four --from-* flags and the reconcile-from-justificante sugar verb; `src/aeat/entrypoints/cli/_modelo_reconcile_cli.py`.
- [ ] `P01.S02` - Move the reconcile help and error locale keys to the new pull/file group across all four catalogues via the aeat.locales CLI; `src/aeat/locales/en.yml`.
- [ ] `P01.S03` - Update the reconcile CLI tests to drive reconcile pull and reconcile file --file; `src/aeat/entrypoints/cli/tests/test_modelo_reconcile_verb.py`.

### Phase `P02` - Live pull renames

Rename every live AEAT-fetch verb from capture/capture-* to pull/pull-*, with locales and CLI tests.

- [ ] `P02.S04` - Rename justificante capture to pull; `src/aeat/entrypoints/cli/_app_live_justificante_cli.py`.
- [ ] `P02.S05` - Rename expedientes capture to pull and capture-all to pull-all; `src/aeat/entrypoints/cli/_app_live_expedientes_cli.py`.
- [ ] `P02.S06` - Rename notifications capture to pull; `src/aeat/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `P02.S07` - Rename filed capture/capture-all/capture-sources and iva-wallet capture-history/capture-remote-state to the pull family; `src/aeat/entrypoints/cli/_app_live.py`.
- [ ] `P02.S08` - Move every live capture* help locale key family to the pull names across all four catalogues; `src/aeat/locales/en.yml`.
- [ ] `P02.S09` - Update the live CLI verb tests and the live read subgroups test for the pull names; `src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py`.

### Phase `P03` - Censo and ledger

Censo refresh to pull and ledger import --source to --file, with locales and tests.

- [ ] `P03.S10` - Rename censo refresh to pull, with its locale keys and tests; `src/aeat/entrypoints/cli/_config/_profile_censo.py`.
- [ ] `P03.S11` - Rename ledger import --source to --file, with its locale key and tests; `src/aeat/entrypoints/cli/_ledger_import_cli.py`.

### Phase `P04` - Docs, conformance, and codify

Update the how-to guides, regenerate the CLI reference, keep conformance green, and codify the standard.

- [ ] `P04.S12` - Update the six how-to guides that reference renamed verbs and flags; `docs/how-to/reconcile.md`.
- [ ] `P04.S13` - Regenerate the CLI reference and keep the documented-command conformance gate green; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [ ] `P04.S14` - Codify the aeat-cli-pull-and-file-standard project rule; `.vaultspec/rules/rules/aeat-cli-pull-and-file-standard.md`.

## Description

Rolls out the CLI pull/file standardization decided in the ADR across the full
blast radius enumerated in the research: `pull` becomes the only AEAT-fetch verb
and `--file` the only single-file-input option. P01 lands the trigger surface
(the reconcile group). P02 renames every live AEAT-fetch verb. P03 covers the
censo and ledger surfaces. P04 updates docs, holds the conformance gates green,
and codifies the standard as a project rule. Each Step carries its verb/flag
rename plus its downstream locale, test, and (where applicable) doc updates so no
surface drifts. Supersedes the CLI-naming decision of the
`live-justificante-reconcile` ADR; the application layer is unchanged.

## Steps







## Parallelization

Within each rename Step the code, locale, and test edits are one atomic unit
(they must land together or a gate reds). The four Phases are largely
independent surfaces and may proceed in parallel, except: P04.S13 (conformance +
reference) and P04.S12 (docs) must run after the rename Phases settle, and
P04.S14 (codify) lands last. The locale Steps (`S02`, `S08`) are sequenced after
their Phase's verb/flag renames so the key moves match the final names.

## Verification

The plan is complete when every Step is closed (`- [x]`). Mission success
criteria, each a verifiable gate:

1. No `capture` / `capture-*` / `refresh` AEAT-fetch verb and no `--from-*` /
   single-file `--source` option remains in the CLI tree (grep + the CLI grammar
   test).
2. `aeat app modelo reconcile` is a `pull` / `file` / `history` group; `file`
   takes `--file`.
3. Locale parity and translation-honesty stay green across all four catalogues.
4. The documented-command conformance gate and the CLI subgroup tests pass; the
   generated CLI reference matches.
5. The `aeat-cli-pull-and-file-standard` rule is codified and synced.
