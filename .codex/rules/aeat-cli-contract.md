---
name: aeat-cli-contract
trigger: always_on
---

# AEAT CLI contract: verbs, notices, single-subject mutations

## `pull` fetches from AEAT, `--file` takes the one local file

The verb that fetches data from AEAT MUST be named `pull`, and the
single-local-file input option MUST be named `--file`. A fetch-from-AEAT command
MUST NOT be named `capture`, `refresh`, `fetch`, `download`, `sync` or `get`; a
single-file input MUST NOT be `--source`, `--path`, `--from-file`, or a bespoke
`--from-*` family. A command reconciling from either transport MUST be a subgroup
of `pull` and `file --file`, never one verb multiplexed by `--from-*` flags.

The reconcile surface had grown four divergent `--from-*` flags plus a sugar
verb while sibling surfaces used `capture`, `refresh` and `--source`, so no
operator could transfer knowledge across verbs.

**A verb rename MUST be swept by hand through the surfaces the gates do NOT
scan:** the runtime write-policy allowlist (`storage_write_policy.py`), the
error-registry `default_suggestion` fields, the cross-period `next_action`
builders, the curated operator help surface (`operator_surface/_help.py`), and
the envelope `command=` identifiers. Updating only the verb registrations leaves
dead operator instructions and drops the verb out of the profile-bound write
guard, which then fails open.

The censal reader is pinned to the read-only consulta view and fails closed on a
filing-tool or procedure-launcher landing; that guard binds regardless of the
verb's name.

## Notices are the only diagnostic channel

Operator-facing non-blocking diagnostics — warnings, advisories, next-step hints
— MUST be emitted through the typed `Notice` channel on the shared CLI envelope
spine (`cadrumo.core.json_contract.Notice`, via `_emit_envelope(...,
notices=[...])` / `emit_json_success(..., notices=[...])`).

A command MUST NOT re-introduce a bespoke advisory, `next` or `suggestion` field
inside its `result` payload. The shared spine (`schema_version`, `command`,
`status`, `notices`) is uniform across the success envelope and the stderr error
document; `status` derives from notice severity and stays in lock-step with the
`ExitCode` table.

The success and error envelopes were once disjoint with no shared `status`, the
success `warnings` channel was structurally dead, and advisories were smuggled as
bespoke `result` fields — so the contract was un-introspectable and bypassed the
envelope redaction funnel.

**Allowed, not a violation:** primary structured result data a command exists to
produce — verify `findings`, calendar `warnings`, a `next_due` date, a
per-finding `next_action`. These are output, not incidental diagnostics.

## Single-subject verbs: positional id, uniform result, idempotent

**The subject id is positional.** A verb addressing one ledger transaction
accepts the id as a positional `Argument` resolved through the single shared
transaction-id resolver — never a `--id` option, never a duplicated resolver
helper. The subject is an argument; flags configure the operation.

**Single-transaction mutations return the uniform quintet**
`{bucket_id, transaction_id, bucket_event_ids, review_status, transaction}`
through the shared ledger mutation result shape. Structural verbs that act on a
set or destroy the subject (`split`, `merge`, `remove`, `reset`) are different
operations and declare their own typed schemas.

**Creating mutations are idempotent-guarded.** Every verb that CREATES one
addressable record: a retry carrying the same caller-supplied idempotency key, or
the same deterministic clock-free derived id, returns the EXISTING record as a
no-op (no second lifecycle event, no `created_at`/`modified_at` re-stamp, no
re-run of side effects), surfaced through the uniform result shape plus an info
`Notice`. A same-key call whose content DIFFERS refuses with an instructive
localised conflict naming the divergent fields. A deliberately additive verb is
`non_idempotent_append` and MUST document that choice.

**Identity MUST be clock-free.** The timestamp is a non-identity last-seen body
field, never folded into the derived id.

This CLI's operator is an autonomous agent that retries calls, so a
non-retry-safe creating mutation silently double-writes — a duplicate ledger
transaction inflates every downstream modelo aggregation. The subtler failure is
a **no-op match that omits a persisted field**, silently dropping the new value.
**The match compares EVERY persisted field.**

## The operator harness cites only the live surface

Every agent-harness document under `src/cadrumo/_data/agent/` that names a CLI
verb or a JSON-envelope field MUST cite only verbs resolving against the live
operator-surface manifest and fields existing on the live envelope models, and
MUST be co-committed with the CLI surface it couples to. A citation to a renamed
verb hands the agent a dead instruction it cannot recover from.

## How

- **Good:** `aeat app live justificante pull`, `pull-all`, `pull-sources`;
  `aeat app ledger import --file STATEMENT.csv`; a dual-transport reconcile as
  `reconcile pull` + `reconcile file --file PATH`. `aeat config profile censo` is
  the worked example: `censo file --file` and `censo pull`, both reconciling
  through the one `apply_cotejo` authority behind the same `--apply` door.
- **Good:** an advisory projected with `advisory_notice(code, message,
  context={...})` and passed via `notices=`, its text line rebuilt from the same
  notice so JSON and text cannot drift.
- **Good:** derived verification and filing record ids fold the OUTCOME
  (revision, status or findings, actor) and drop the timestamp.
- **Bad:** a new `capture`/`refresh`/`fetch` verb for an AEAT read, a `--source`
  file input, or multiplexing one verb with a `--from-*` family.
- **Bad:** adding `authorization_advisory`, `source_advisories`, or any
  `*_advisory` / bare `next` / `suggestion` as a top-level field on a registered
  `OutputSchema`.
- **Bad:** `ledger view --id tx_123` for a one-subject verb; a mutation returning
  only `transaction_id`; an id that folds the clock; or a guarded no-op whose
  match omits a field.
- **Bad:** citing a harness verb that does not exist, or renaming a CLI verb
  without sweeping the harness documents.

Gates in this repository: `test_documented_command_conformance.py` and
`test_json_schema_conformance.py`. The latter was rebuilt against the command-spec
`ResultSchemaSpec` kernel after the `SCHEMA_REGISTRY` it originally walked was
retired; it walks every spec declaring a result-schema target and refuses a
bespoke `next` / `suggestion` / `*_advisory` field beside the envelope's one
diagnostic channel. `test_rule_surface_conformance.py` is deliberately NOT named
here any more: it shipped inside the cadrumo-harness client and left with it when
that client was rehomed out of this repository, so naming it here pointed every
reader at a file this tree does not contain. Source:
ADRs `2026-06-10-cli-pull-file-standard-adr`,
`2026-06-10-cli-envelope-notice-standardisation-adr`,
`2026-06-10-ledger-interface-contract-adr`,
`2026-06-30-ledger-add-idempotency-adr`, `2026-06-30-agent-harness-adr`.
