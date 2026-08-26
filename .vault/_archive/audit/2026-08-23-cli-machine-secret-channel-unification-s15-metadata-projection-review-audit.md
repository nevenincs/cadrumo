---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b1a8d0b752768121b9f5dd47f9a9956cc9dd8b995da72167d9cff8772dc5f923'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-adr]]"
---

# `cli-machine-secret-channel-unification` audit: `S15 metadata projection review`

## Scope

Independent architecture and safety review of S15's direct command-graph metadata
projection after retirement of the generated command-registration JSON cache and its
generator. The review covered `_command_schema.py`, `_verb_input_schema.py`,
`command_api.py`, `dev/docs/cli_tree.py`, and their focused tests against the accepted
amended ADR, approved S15 plan row, research, predecessor S03-S05/S07/S20 execution
records, and the generated-reference and no-legacy rules.

Semantic source and decision discovery was followed by exact-symbol census and whole-file
inspection. The current graph was then projected in a fresh process to verify the exact
five leaf payload owners and field sets, restore's public `artifact` absent/present
conditions, graph-derived root posture, the self-authenticating rotation exemption, the
8 KiB and strict/collision declarations, value-free serialization, public import
boundary, handler laziness, outsider emptiness, and physical absence of the retired cache
and generator.

## Findings

No findings. In particular, this review found no HIGH or CRITICAL issue.

The live projection contains only `config.login`, `config.profile.create`,
`config.passphrase.change`, `config.profile.restore`, and
`config.auth.certificate.secret.set` as leaf machine-secret adopters. Their projected
fields exactly match the ADR, restore carries only the two public option-presence
conditions, and every other command projects an empty leaf-secret tuple. The root
contract contains only the public `profile_passphrase` string field and structural
transport constraints. Rotation remains the sole `self-authenticating` leaf.

No projected structure carries a secret value, default secret, example, hash,
invocation-derived length, or persisted credential fact. The supported `command_api`
boundary exposes immutable projection types and functions without materialising Typer or
loading behavior-handler targets. The CLI-tree artifact is regenerated from that same
live projection and remains gitignored rather than becoming a second authority. The
retired `command_registration_metadata.v1.json` and
`generate_command_registration_metadata.py` files are physically absent; remaining name
mentions are negative shipping and regression guards, not consumers or compatibility
paths.

Focused verification passed: 46 command-graph, machine-secret authority,
profile-authentication, and CLI-tree tests; scoped Ruff; and scoped diff whitespace
validation. The final review re-read current HEAD, status, and the owned diff after
concurrent worktree movement.

## Recommendations

No remediation is required for S15. Preserve the existing exact-set, import-laziness,
value-free serialization, and retired-authority absence gates when later documentation
or operator surfaces consume this projection.
