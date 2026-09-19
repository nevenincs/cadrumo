---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:67557c4d273074e4fa055130093f3fc30dc4e46b591945dfbf8277c5a325600c'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-W02-P11-S19]]"
---

# `cli-machine-secret-channel-unification` audit: `s19 passphrase rotation review`

## Scope

Independent SOL review of the S19 restoration against the amended machine-secret ADR, the keychain-free research, the command-spec single-authority boundary, and real subprocess behavior. The audit covers command policy, self-authentication posture, secret-read ordering, graph truth, stale lifecycle prose, and end-to-end rotation on a deliberately unavailable keychain.

## Findings

### s19-root-posture-consumption | high | self-authenticating posture is not yet consumed by root dispatch

The immutable graph and public metadata correctly mark `config.passphrase.change` as `self-authenticating`, but the current root session gate still refuses a keychain-unavailable process before the leaf runs. The new forced-failure subprocess regression exits with the typed keychain refusal instead of rotating. S21 owns the parsed-posture early return after active-profile normalization and write-route validation; S19 remains open until that behavior lands and the regression is green.

### s19-policy-classification | high | fixed help group and destructive encrypted rotation policy

The first restoration assigned `BOOTSTRAP_WRITE` to both nodes. The help-only group now carries `STATE_FREE`; the mutation leaf carries `ENCRYPTED_DESTRUCTIVE`. The independent `self-authenticating` posture remains unchanged and is asserted separately, preventing session-gate semantics from being inferred from write policy.

### s19-secret-read-order | medium | fixed exact target resolution before secret consumption

The handler previously parsed the machine payload before resolving an active profile. It now resolves and UUID-validates the exact active target before calling the bounded reader, while proof, password policy, transaction entry, and envelope mutation remain application-owned. A subprocess regression supplies malformed JSON with no active profile and observes the target refusal rather than a parser diagnostic.

### s19-command-graph-truth | medium | fixed stale counts and retired-verb assertion

The command graph contains 363 nodes after restoring the passphrase group and leaf, but exact-shape tests still expected 361 and a consumer still asserted the rotation schema was absent. Counts, subprocess import-light proof, and the consumer assertion now describe the live canonical graph.

### s19-runtime-proof | medium | real keychain-free rotation contract added and blocked on S21

The first restoration proved declarations and application behavior separately but did not execute the CLI handler. A real fresh-process regression now forces `keyring.backends.fail.Keyring`, supplies the three-field payload through stdin, requires successful rotation without secret output, refuses the retired current passphrase, and rotates again under the new one. Its first success assertion deliberately remains red until S21 consumes `self-authenticating` before the root resume gate.

### s19-lifecycle-prose | low | fixed stale claim that passphrase help intentionally fails

Lifecycle documentation still described the passphrase capability as absent and its help assertion as intentionally failing. The prose now identifies `config passphrase change` as the sole rotation door and retains negative assertions only for genuinely retired spellings.

## Recommendations

- Complete S21 by deriving the root-gate self-authentication exemption from the resolved command specification, never from the older bootstrap-exemption inventory.
- Re-run the forced failing-keychain rotation regression after S21 and close S19 only when its full two-rotation round trip passes.
- Preserve the corrected state-free/destructive policies, target-before-read order, exact graph assertions, and absence of environment or compatibility secret routes.

## S18 lifecycle resolution

### s19-root-posture-consumption | high | resolved by S21 and reverified on the current tree

The text above records the pre-S21 review state. The current root session gate consumes the resolved command specification's `self-authenticating` posture after exact-target normalization and write-route validation and before persisted-session or keychain work. On 2026-08-23, `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py::test_config_passphrase_change_self_authenticates_without_a_keychain` passed in 53.28 seconds. That fresh-process regression forces `keyring.backends.fail.Keyring`, completes one rotation, refuses the retired passphrase, and completes a second rotation with the new proof. The S21 dependency is therefore satisfied and this HIGH finding is closed.

### s19-runtime-proof | medium | resolved by the same real two-rotation subprocess proof

The formerly red regression is now green against the production entrypoint without a patched handler, session gate, or keychain. S13 and S14 remain the broader real-process transport authorities; this S19 regression is the focused destructive-lifecycle authority. The historical blocked wording remains above to preserve review chronology, but it no longer narrows or reopens S19 completion.

No CRITICAL or HIGH S19 finding remains open after this current-tree verification.
