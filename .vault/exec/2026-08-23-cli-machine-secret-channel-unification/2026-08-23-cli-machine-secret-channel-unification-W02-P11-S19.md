---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:db51dca7cdcbfc66332a7c9fc311311ca4107415760914fa07a7a0823a18f42b'
step_id: 'S19'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and restore config passphrase change as the sole three-field rotation verb with canonical leaf transport, public metadata, tests, and an explicit self-authenticating root-gate exemption

## Scope

- `passphrase command specification handler metadata and tests`

## Description

- Restore `config passphrase change` through the immutable command-spec graph as the sole public rotation leaf.
- Restore the command-local strict `PassphraseChangeSecrets` model, handler, and non-secret result schema without reviving the retired registration layer.
- Declare one canonical stdin/file-descriptor option pair and the exact `current_passphrase`, `new_passphrase`, and `new_passphrase_confirmation` payload.
- Add the typed `ProfileAuthenticationPosture` graph authority and project the leaf's `self-authenticating` posture into public registration metadata.
- Prove command shape, handler/spec parity, payload/model parity, metadata, help rendering, and application rotation behavior with focused gates.

## Outcome

The passphrase rotation capability is publicly mounted again at `config passphrase change`. Its leaf owns exactly one canonical paired machine-secret transport and one strict three-field model; the application remains the confirmation, policy, proof, transaction, and mutation authority. The graph now publishes `self-authenticating`, giving the later root profile-authentication steps a typed exemption rather than a parallel command-name inventory.

Focused Ruff, scoped `ty`, command-spec, metadata, help, lifecycle, and application rotation checks passed. Import-linter and the repository-wide type harness still report their pre-existing broad architecture/type debt; neither report identifies an S19-owned edge or scoped type diagnostic.

## Notes

The previous command-spec normalization commit removed the already-canonical handler and output schema while leaving the application rotation authority intact. Recovery therefore restored the current surviving implementation through the command-spec kernel instead of resurrecting obsolete decorators, registration calls, environment routes, or compatibility names.

Root `--profile-secrets-*` declarations and dispatch-time unused-source refusal deliberately remain for `W02.P11.S20` and `W02.P11.S21`; S19 establishes the exact typed exemption those steps consume.

Post-landing SOL review found the initial group and leaf policies incorrect, the handler consuming secrets before active-target resolution, stale graph/lifecycle assertions, and insufficient handler-level proof. The remediation classifies the group as state-free and the leaf as encrypted destructive, resolves the exact UUID target before reading, updates the graph truth, and adds real keychain-unavailable subprocess rotation coverage.

That subprocess contract currently exits at the root keychain refusal before the leaf. This is the recorded S21 dependency: root dispatch must consume the parsed `self-authenticating` posture after target normalization and write-route validation. S19 remains open until S21 makes the real two-rotation round trip green.
