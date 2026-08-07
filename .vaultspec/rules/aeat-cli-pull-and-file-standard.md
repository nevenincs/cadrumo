# AEAT CLI uses `pull` to fetch and `--file` for file input

## Rule

Across every CLI interface, the verb that fetches data from AEAT MUST be named
`pull`, and the single-local-file input option MUST be named `--file`. A
fetch-from-AEAT command MUST NOT be named `capture`, `refresh`, `fetch`,
`download`, `sync`, or `get`; a single-file input option MUST NOT be named
`--source`, `--path`, `--from-file`, or a bespoke `--from-*` family. A command
that reconciles from either transport MUST be a subgroup of `pull` (fetch from
AEAT) and `file --file` (local artefact), never one verb multiplexed by
`--from-*` flags.

A verb rename MUST be swept by hand through the surfaces the gates do NOT scan:
the runtime write-policy allowlist (`storage_write_policy.py`), the
error-registry `default_suggestion` fields, the cross-period `next_action`
builders, the curated operator help surface (`operator_surface/_help.py`), and
the envelope `command=` identifiers. Updating only the verb registrations leaves
dead operator instructions and drops the verb out of the profile-bound write
guard, which then fails open.

## Why

The reconcile surface had grown four divergent `--from-*` flags plus a sugar
verb while sibling surfaces used `capture`, `refresh`, and `--source` — no
operator could transfer knowledge across verbs. ADR
`2026-06-10-cli-pull-file-standard-adr` collapsed the surface onto `pull` ("read
this from AEAT") and `--file` ("the one local file"). The conformance gates bind
docs and envelope identifiers but do not scan production `suggestion`,
`next_action`, or curated-help strings, hence the mandatory hand-sweep.

## How

- **Good:** `aeat app live justificante pull`, `pull-all`, `pull-sources`,
  `pull-history`; `aeat app ledger import --file STATEMENT.csv`; a dual-transport
  reconcile as a subgroup `reconcile pull` + `reconcile file --file PATH` with
  `history` listing prior runs. `aeat config profile censo` is the worked
  example of that shape: `censo file --file` ingests a local artefact and
  `censo pull` reads the live AEAT censal consulta, both reconciling through the
  one `apply_cotejo` authority behind the same `--apply` door.
- **Bad:** a new `capture`/`refresh`/`fetch`/`download` verb for an AEAT read, a
  `--source`/`--from-capture` file input, or multiplexing one verb with a
  `--from-sede`/`--from-justificante` flag family.

**Safety constraint on the censal reader**, carried forward from the design that
preceded it: it is pinned to the read-only consulta view and fails closed on a
filing-tool or procedure-launcher landing. That write-adjacency guard binds
regardless of the verb's name.

## Source

ADR `2026-06-10-cli-pull-file-standard-adr` (superseding the CLI-naming of
`2026-06-10-live-justificante-reconcile-adr`); censal transport per
`2026-07-25-censal-profile-autofill-adr`. Enforced by
`src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` and
`docs/how-to/`.
