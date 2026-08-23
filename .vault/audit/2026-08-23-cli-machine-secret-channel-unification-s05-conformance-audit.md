---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:00f466ceadaf6d3a7ceeb9e161b91134d8fb9df10a2659616eda09c23005a079'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` audit: `s05 conformance`

## Scope

Reviewed S05 commit `72e8ff8a2c` at current HEAD against the accepted machine-secret ADR,
approved plan, research record, and S05 execution record. The review covered the closed
five-command inventory, cycle-safe canonical-base registration, value-free payload metadata,
conditional restore variants, live help/Click/spec/schema parity, outsider detection, and the
declared S15 generated-artifact deferral. Semantic code and ADR discovery was followed by
whole-file inspection, exact-symbol census, scoped-diff inspection, and focused tests.

## Findings

### outsider-conformance-scope | medium | The no-outsider gate searches only the config aggregate

`test_no_command_outside_the_closed_inventory_adopts_either_channel` derives adopters only from
`CONFIG_COMMAND_SPECS`. The accepted contract is global to the CLI, and the repository has
multiple non-config command-spec aggregates and dynamically materialized live nodes. The current
exact source census finds no outside production adopter, so this is not a live unauthorized secret
surface; however, a future adopter outside the config aggregate would evade the durable gate while
the test continued to claim that no command outside the closed inventory adopted either channel.
The incomplete negative proof is at
`src/cadrumo/entrypoints/cli/tests/test_machine_secret_metadata.py:89`.

No HIGH or CRITICAL finding was identified. The strict-base registration import is cycle-safe,
the projected payload structures contain no values, restore selection depends only on public
`artifact` presence, and the execution record honestly leaves generated registration/CLI-tree
parity to S15. The temporary prefix assertion for channel declarations also reflects the staged
migration honestly rather than claiming all five commands are already complete.

## Recommendations

- Expand the outsider assertion to derive every live leaf or every authoritative command-spec
  aggregate, then compare all `secrets_stdin` and `secrets_fd` adopters with
  `MACHINE_SECRET_COMMANDS` by canonical command identity.
- Retain S15 as the owner of generated registration JSON and CLI-tree regeneration; at S15 closure,
  replace the staged prefix allowance with exact two-channel parity for every inventory member.
