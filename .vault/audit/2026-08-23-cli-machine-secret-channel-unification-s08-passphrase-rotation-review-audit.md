---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3f9b67581ebdf5aa0245e068a7f974e31314a1f08d5369fe2eeafb6723e06560'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` audit: `S08 passphrase rotation review`

## Scope

Reviewed the S08 rotation implementation landed in `f647b4dd93` and its lifecycle record in
`52cff343cf` at current HEAD against the accepted machine-secret ADR, approved plan, research
record, and S08 execution record. The review covered canonical declarations, channel selection,
bounded reading, strict payload registration, conflict-before-read behavior, descriptor closure,
proof and mutation ordering, confirmation and password-policy enforcement, output secrecy, and
obsolete branch deletion. Semantic discovery was followed by whole-file reading, exact-symbol
census, scoped-diff inspection, and focused unit/integration execution.

## Findings

### confirmation-doc-claim | low | The module says the CLI compares confirmation when it only forwards it

The module-level contract in `src/cadrumo/entrypoints/cli/_config/_passphrase.py:15` says the
confirmation is compared “here AND again” in the application authority. `_collect_passphrases`
does not compare the two prospective values; it correctly forwards both to
`rotate_profile_passphrase`, whose application boundary performs the comparison before policy,
proof, or mutation. Runtime behavior remains safe, but the source narrative overstates the CLI
surface's local enforcement and can misdirect later maintenance or review.

No HIGH or CRITICAL finding was identified. The command retains both canonical declarations,
registers the exact three-field `MachineSecretPayload`, selects conflicts before any source read,
delegates descriptor reads to the one-shot closing reader, resolves the active profile only after
secret collection, and mutates only through the application rotation authority. That authority
checks confirmation and the canonical prospective-password policy before custody proof and writes,
then proves the current credential before mutation. Focused execution passed without secret output.

## Recommendations

- Correct the module narrative to say the CLI collects and forwards confirmation while the
  application authority performs the mandatory comparison, or add an intentional CLI comparison
  if independent surface-level early refusal is desired.
- Keep real inherited-descriptor rotation and cross-process leak coverage assigned to S13-S14;
  the shared reader tests prove descriptor lifecycle mechanics, while S08's existing integration
  path proves stdin rotation and wrong-current non-mutation.
