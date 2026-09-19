---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:080f3e34e6874854ed2e7389068464a551814c14d399c660826080847414201b'
step_id: 'S16'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and update operator documentation and sequence sources through canonical generators to describe both leaf channels, the distinct root profile-authentication pair, cross-scope collision rules, caller-owned descriptors, Windows HANDLE bootstrap, repeated keychain-free Argon2 work, bounded-lifetime cleanup, and removed CLI environment fallback

## Scope

- `docs/how-to and docs/reference CLI secret-input documentation and sequences`

## Description

- Ground the operator surfaces in the amended machine-secret ADR, the direct immutable command graph, `command_api`, live help, and the preceding metadata projection record.
- Replace the obsolete CLI environment-passphrase instruction with the explicit leaf and root channel contract.
- Document the five leaf adopters, both restore payload variants, exact hard-cut field names, strict-object refusal, and verified-terminal prompt boundary.
- Document root exact-target applicability, self-authenticating and unused-source refusals, cross-scope collision rules, keychain-free process scope, repeated Argon2 work, and the non-persistence Notice.
- Document caller-owned descriptor lifetime, local one-shot closure, fd 0 and fd 1/2 treatment, POSIX `pass_fds`, and the Windows inherited-HANDLE bootstrap for root, leaf, or dual sources.
- State bounded input and best-effort mutable-buffer cleanup without claiming immutable Python string erasure.
- Project both root profile-secret flags and their localized safe intent from the immutable command graph into curated live root help without reading a selected source or importing command handlers.
- Regenerate the environment reference and the data-access sequence goldens through their canonical generators.
- Correct the adjacent logout sequence and guides to match live custody semantics: logout closes the session while preserving the selected exact profile.
- Verify the page-level sequences, direct graph and metadata projection, generated references, linkable documentation structure, and scoped diffs.

## Outcome

Operators now have one complete machine-operability guide for all scalar-secret CLI input. It distinguishes the root profile proof from each leaf-owned payload, gives every accepted field, identifies every safe dual-source combination, and explains platform-specific descriptor transfer without overstating transport ephemerality or memory erasure. The generated environment reference now preserves the programmatic setting while stating that the CLI never uses it as fallback.

The sequence source executes live help for the root profile-authentication pair and the complete five-command leaf inventory and commits its generated golden. The page-level data-access sequence gate passes, including the reconciled logout behavior.

## Notes

- The focused machine-secret graph, profile-authentication contract, and CLI-tree suites passed 38 tests. The CLI-tree test module separately passed 14 tests, the canonical CLI-reference drift check passed, and the page-level sequence check passed.
- The full documented-command conformance suite passed 347 tests and reported two unrelated existing failures: a retired `app agent` citation in the workstation sequence and an existing long inline delete command in the profile-setup guide.
- The environment-reference suite passed three tests and reported one unrelated existing failure covering four dead MCP example keys.
- The nitpicky docs suite passed 16 tests and stopped one test during unrelated Modelo 322 casilla-reference generation because a Spanish locale key is absent; no S16 page was parsed before that extension failure.
- The sequence runner emits a benign Python module-reimport warning while returning success.
- The locale scaffold command encountered unrelated pending Modelo catalogue drift and rewrote broad unrelated catalogue surfaces. Those generator-owned changes were removed; only the four reviewed root-help title leaves remain alongside the existing localized option descriptions.
- Independent SOL review found no HIGH or CRITICAL issue. It identified contradictory logout wording and the missing root options in curated help. Both were corrected: logout guidance now matches the generated runtime evidence, and root help derives each declaration and description directly from the graph. Four-locale parity and real descriptor non-consumption tests cover the projection.
