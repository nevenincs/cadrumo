---
name: aeat-cli-pull-and-file-standard
---

# AEAT CLI uses `pull` to fetch and `--file` for file input

## Rule

Across every CLI interface, the verb that fetches data from AEAT MUST be named
`pull`, and the option that takes a single local file as input MUST be named
`--file`. A fetch-from-AEAT command MUST NOT be named `capture`, `refresh`,
`fetch`, `download`, `sync`, or `get`; a single-file input option MUST NOT be
named `--source`, `--path`, `--from-file`, or a bespoke `--from-*` family. When
a command both reconciles and accepts either a live pull or a local file, model
it as a subgroup whose members are `pull` (fetch from AEAT) and `file --file`
(local artefact), not as one verb multiplexed by `--from-*` flags.

## Why

The reconcile surface had grown four divergent `--from-sede` / `--from-capture`
/ `--from-justificante` / `--from-declaration` flags plus a sugar verb, and the
live family used `capture`, the censo family used `refresh`, and ledger import
used `--source` — every fetch and every file-input spelled differently per
command. An operator could not transfer knowledge from one verb to the next, and
`--help` taught a different vocabulary on every screen. The
`2026-06-10-cli-pull-file-standard-adr` collapsed the surface onto two words:
`pull` always means "go read this from AEAT", `--file` always means "here is the
one local file". A single learned verb and a single learned flag now generalise
across the whole CLI. The documented-command conformance gate
(`test_documented_command_conformance.py`) prevents the how-to docs from citing a
non-canonical or dead verb, and `test_json_schema_conformance.py` keeps every CLI
leaf's `command` envelope identifier bound to a registered schema — but neither
scans production `suggestion` / `next_action` / curated-help strings, so a verb
rename MUST be swept by hand through the runtime write-policy allowlist
(`storage_write_policy.py`), the error-registry `default_suggestion` fields, the
cross-period `next_action` builders, the curated operator help surface
(`operator_surface/_help.py`), and the envelope `command=` identifiers. A
rename that updates only the verb registrations leaves dead operator instructions
and — critically — drops the verb out of the profile-bound write guard
(fail-open). This is the CLI-surface companion to `aeat-architecture-boundaries`
(the CLI gate is the operator's first instructive surface) and to
`aeat-locales-cli` (the help text for these verbs is authored only through the
locale CLI).

## How

- **Good:** `aeat app live justificante pull`, `aeat app live expedientes pull`
  / `pull-all`, `aeat app live notifications pull`, `aeat app live filed pull` /
  `pull-all` / `pull-sources`, `aeat app live iva-wallet pull-history` /
  `pull-remote-state`, `aeat config profile censo pull` — every live AEAT read is
  a `pull`.
- **Good:** `aeat app ledger import --file STATEMENT.csv` and
  `aeat app modelo reconcile file --file JUSTIFICANTE.pdf` — the single local
  file is `--file` on both.
- **Good:** a reconcile that supports both transports is a subgroup:
  `reconcile pull` (fetch the justificante from the AEAT sede) and
  `reconcile file --file PATH` (reconcile against a local artefact); `history`
  lists prior runs. No `--from-*` flag selects the source.
- **Bad:** adding a new `capture`, `refresh`, `fetch`, or `download` verb for an
  AEAT read, or a new `--source` / `--from-capture` option for a file input —
  the conformance gate and this rule reject it; rename to `pull` / `--file`.
- **Bad:** multiplexing one verb across data sources with a `--from-sede` /
  `--from-justificante` flag family instead of distinct `pull` and `file`
  subcommands.

## Source

ADR `2026-06-10-cli-pull-file-standard-adr` (accepted), which supersedes the
CLI-naming of `2026-06-10-live-justificante-reconcile-adr`; research
`2026-06-10-cli-pull-file-standard-research` (full blast radius); plan
`2026-06-10-cli-pull-file-standard-plan`. Enforced by
`src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` and the
how-to guides under `docs/how-to/`. Promoted per the `vaultspec-codify`
discipline.
