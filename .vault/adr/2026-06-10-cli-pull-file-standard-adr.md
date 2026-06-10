---
tags:
  - '#adr'
  - '#cli-pull-file-standard'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-pull-file-standard-research]]'
  - '[[2026-06-10-live-justificante-reconcile-adr]]'
---



# `cli-pull-file-standard` adr: `CLI pull verb and file flag standardization` | (**status:** `accepted`)

## Problem Statement

The CLI vocabulary for two recurring concepts has drifted. "Fetch live data from
AEAT" is spelled `capture` on most live verbs, `pull` on the IVA wallet,
`capture-history` / `capture-remote-state` / `capture-sources` on others, and
`refresh` on censo. "Single-file input" is spelled `--from-justificante`,
`--from-declaration`, `--from-capture`, and `--source` depending on the command,
while `--file` already exists as the de-facto standard
(`config auth configure --file`). The reconcile surface concentrated the
divergence — four source flags — and is the trigger for fixing it everywhere.
This ADR establishes one verb (`pull`) and one option (`--file`) as the
project-wide standard and records the full-surface rollout. It is a deliberate
operator-directed standardization of an unreleased pre-beta CLI.

## Considerations

- **`pull` is the AEAT-fetch verb, project-wide.** Every live-read verb that
  contacts AEAT becomes `pull` (or `pull-<suffix>` for the multi-target
  variants). The existing `iva-wallet pull` is the precedent.
- **`--file` is the single-file-input option, project-wide.** Every option that
  takes one file path becomes `--file`. Directory/output flags and enum "source"
  options are out of scope (they are not single-file inputs).
- **Reconcile becomes a command group** rather than a flag-bag:
  `reconcile pull <wu>` (fetch + reconcile), `reconcile file <wu> --file PATH`
  (local), `reconcile history` (unchanged). This is the cleanest expression of
  the two standards on the surface that triggered the work.
- **No-legacy.** The redundant `reconcile-from-justificante` sugar verb and the
  four `--from-*` flags are removed outright (unreleased pre-beta; no aliases).

## Constraints

- **This ADR supersedes the CLI-placement decision of
  `2026-06-10-live-justificante-reconcile-adr`.** That ADR placed the live capture
  as a distinct `aeat app live justificante capture` verb and rejected a
  `--from-sede` flag on reconcile, reasoning the live capture and local reconcile
  must stay distinct. The *separation* principle is preserved; only the *naming*
  is superseded: the capture verb is renamed `pull`, and the reconcile sources are
  re-expressed as the `pull` / `file` subgroup. The justificante feature's
  application layer (the capture service, the orchestrator, `reconcile_capture`,
  the evidence stamp) is unchanged — this is a CLI-surface rename, not a logic
  change.
- **Locale discipline.** Every renamed verb/flag moves its `*_help` key family
  across all four catalogues via the `aeat.locales` CLI (`aeat-locales-cli`); the
  parity and translation-honesty gates must stay green.
- **Conformance gates.** The documented-command conformance test and the CLI
  grammar/subgroup tests must be updated and pass; the generated CLI reference is
  regenerated.
- **Shared-worktree breadth.** The rename touches many modules, locales, tests,
  and docs concurrently with other agents; the rollout lands surface-by-surface in
  atomic explicit-path commits, tracked by the plan.

## Implementation

The rollout proceeds surface by surface, each an atomic commit with its gates:

1. The reconcile group (`_modelo_reconcile_cli.py`): convert the single
   `reconcile` verb into a Typer group with `pull`, `file`, and `history`
   subcommands; `pull` calls the live capture orchestrator then
   `reconcile_capture`; `file` calls `modelo_reconcile` with the `--file` path;
   remove `--from-*` and the `reconcile-from-justificante` sugar.
2. The live `pull` renames (`_app_live_justificante_cli.py`,
   `_app_live_expedientes_cli.py`, `_app_live_notifications_cli.py`,
   `_app_live.py`): `capture` -> `pull`, `capture-all` -> `pull-all`,
   `capture-sources` -> `pull-sources`, `capture-history` -> `pull-history`,
   `capture-remote-state` -> `pull-remote-state`.
3. Censo `refresh` -> `pull` (`_config/_profile_censo.py`).
4. `ledger import --source` -> `--file` (`_ledger_import_cli.py`).
5. Locales: move each `*_help` key family to the new verb/flag names across
   `en/es/ca/hu`.
6. Tests: update every invocation; keep the documented-command conformance and
   CLI-grammar gates green.
7. Docs: update the six how-to guides and regenerate the CLI reference.
8. Codify the `aeat-cli-pull-and-file-standard` rule.

## Rationale

A single verb and a single file option make the operator surface predictable: an
operator who learns `pull` once knows how to fetch from AEAT anywhere, and `--file`
always means "the file." The reconcile group removes a four-flag source-bag in
favour of two named subcommands that map one-to-one onto the two standards. Doing
the whole surface at once (rather than per-feature) is what makes the convention
real; a half-renamed CLI is worse than either consistent state.

## Consequences

- **Gains.** Predictable, learnable CLI; one place each to document "fetch" and
  "file input"; the reconcile surface stops accreting source flags.
- **Difficulties.** Broad, outward-facing rename with heavy locale and test churn;
  must land coherently or the CLI is briefly inconsistent. Mitigated by the
  surface-by-surface plan and the conformance gates.
- **Pathways opened.** The codified rule makes every future live verb a `pull` and
  every future file input a `--file` by default; new contributors inherit it.
- **Pitfalls.** Missing a locale key move breaks parity; missing a test
  invocation reds CI; a missed doc reference drifts the reference. The plan
  enumerates all three downstream surfaces per rename to prevent omissions.

## Codification candidates

- **Rule slug:** `aeat-cli-pull-and-file-standard`.
  **Rule:** A CLI verb that fetches live data from AEAT MUST be named `pull`
  (or `pull-<suffix>` for multi-target variants), and a CLI option that takes a
  single file input MUST be named `--file`; do not introduce `capture` / `fetch`
  / `refresh` fetch verbs or `--from-*` / `--source` / `--path` single-file
  options.


