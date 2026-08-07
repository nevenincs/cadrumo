# Generated reference is CLI-owned: regenerate, never hand-edit the managed zones

## Rule

The bundled CLI references' generator-managed regions — delimited by the
`vaultspec:generated:begin` and `vaultspec:generated:end` markers in the shipped
`reference/cli.md` and in `docs/CLI.md` — are updated only by running
`vaultspec-core spec reference generate`, never by hand-editing inside the
markers. The `--check` mode gates pre-commit and CI and fails until both
references match fresh output.

Hand-written prose **outside** the markers — the entry-point table, the
global-options narrative, the sync-vocabulary section, the environment-variable
table — is hand-maintained normally; the generator reads but never rewrites it.

## Why

The bundled reference is hand-authored prose wrapped around generator-owned
zones, and the hand-authored content drifted from the live Typer surface every
time a flag or enumeration changed. The two surfaces also drifted against each
other in ordering. The generator plus `--check` makes drift mechanically
correctable and makes CI fail deterministically until the managed regions equal
fresh output.

## How

- **Good:** a new flag lands on a verb; run
  `vaultspec-core spec reference generate`, review the regenerated managed
  region, and commit it. Both references regenerate from one Typer walk and
  cannot diverge.
- **Bad:** hand-editing a signature or option table inside the markers. The edit
  is overwritten on the next generate, and `--check` fails CI in the meantime.

## Source

Audit `2026-06-10-cli-reference-automation-audit` (findings GENREVIEW-002,
GENREVIEW-003); sibling decision ADR `2026-06-10-cli-reference-automation-adr`.
