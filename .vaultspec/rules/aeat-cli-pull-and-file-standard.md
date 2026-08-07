# The CLI uses `pull` to fetch and `--file` for file input

The verb that fetches data from AEAT MUST be named `pull`, and the
single-local-file input option MUST be named `--file`. A fetch-from-AEAT command
MUST NOT be named `capture`, `refresh`, `fetch`, `download`, `sync` or `get`; a
single-file input MUST NOT be `--source`, `--path`, `--from-file`, or a bespoke
`--from-*` family. A command reconciling from either transport MUST be a subgroup
of `pull` (from AEAT) and `file --file` (local artefact), never one verb
multiplexed by `--from-*` flags.

The reconcile surface had grown four divergent `--from-*` flags plus a sugar
verb, while sibling surfaces used `capture`, `refresh` and `--source`, so no
operator could transfer knowledge across verbs.

**A verb rename MUST be swept by hand through the surfaces the gates do NOT
scan:** the runtime write-policy allowlist (`storage_write_policy.py`), the
error-registry `default_suggestion` fields, the cross-period `next_action`
builders, the curated operator help surface (`operator_surface/_help.py`), and
the envelope `command=` identifiers. Updating only the verb registrations leaves
dead operator instructions and drops the verb out of the profile-bound write
guard, which then fails open.

## How

- **Good:** `aeat app live justificante pull`, `pull-all`, `pull-sources`,
  `pull-history`; `aeat app ledger import --file STATEMENT.csv`; a dual-transport
  reconcile as `reconcile pull` + `reconcile file --file PATH` with `history`
  listing prior runs. `aeat config profile censo` is the worked example: `censo
  file --file` ingests a local artefact and `censo pull` reads the live censal
  consulta, both reconciling through the one `apply_cotejo` authority behind the
  same `--apply` door.
- **Bad:** a new `capture`/`refresh`/`fetch`/`download` verb for an AEAT read, a
  `--source` file input, or multiplexing one verb with a `--from-*` family.

The censal reader is pinned to the read-only consulta view and fails closed on a
filing-tool or procedure-launcher landing; that guard binds regardless of the
verb's name.

Source: ADR `2026-06-10-cli-pull-file-standard-adr`; censal transport
`2026-07-25-censal-profile-autofill-adr`. Enforced by
`test_documented_command_conformance.py`.
