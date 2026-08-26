---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:56d951547e4c2fe75e1ee2a6b1a41e282f392e3b12f24e38a65509a2e625e650'
step_id: 'S49'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Examine the creating, mutating and selector verb groups against the live graph and record the six that are principled, with the criterion that makes each checkable

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `python -c "...COMMAND_GRAPH leaf-token and family census..."` -> `no new conflation found`

## Notes

No code changed. This records six verb groups examined and cleared, each with the
criterion a later reader can re-check, so the campaign does not re-litigate them.

**`create` (4) versus `add` (7): container versus member.** `create` brings a new
subject into being that other rows then attach to -- a profile, a work unit, an
inventory, an M145 record. `add` appends a member to a collection that already
exists -- a transaction, an evidence row, an inventory movement, an invoice, a
rule, a recipient, a descendiente. The pair `inventory create` /
`inventory movement add` shows the distinction inside one family.

**`update` (3) versus `set` (5): record versus setting.** `update` mutates a
stored record addressed by id (evidence, invoice, transaction). `set` assigns a
configuration value (ratios, certificate secret, credential source, folder,
capabilities). No leaf crosses the line.

**`configure` (2) versus `set`.** Both `config auth configure` and
`config auth apoderado configure` write several related fields as one operation;
`set` writes one value. A multi-field write named `set` would understate what it
touches.

**`register` (2): enrolling an external identity.** `config auth certificate
register` and `config google register` both enrol a credential the operator
already holds. The CLI contract names the first as its worked example of a
CREATING verb, and the second matches it.

**`latest` (5) is a selector, not a synonym for `view`.** Every one of the five
families carrying it -- borrador 100, deudas, expedientes, notifications, verify
-- also carries `list` AND `view`. `view` addresses one capture by id, `list`
enumerates, `latest` picks the most recent. Uniform across all five, and it
names which record rather than what the verb does.

**`app modelo iva-wallet` has three write verbs and needs all three.** `seed`
declares a carry-forward balance to bootstrap local history; `correct` repairs a
wrong seed under an audit guard; `override` records a deliberate taxpayer
deviation releasing the M303 prior-compensación carry, and demands a reason, an
evidence locator and `--confirm`. Different operations, different guards.
Separately, `app live iva-wallet` and `app modelo iva-wallet` share the noun but
not the job: the first pulls from AEAT, the second is local wallet state.

The hunt is not exhaustive. Groups still untested are recorded in the loop
prompt rather than implied to be clear.
