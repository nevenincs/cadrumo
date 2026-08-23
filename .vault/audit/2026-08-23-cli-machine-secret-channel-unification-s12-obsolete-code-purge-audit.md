---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:56432ddfa272af4ea63a5c4f388460a9f2e38aae1fa2e251bf6a95df31786c83'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-W02-P05-S12]]"
---

# `cli-machine-secret-channel-unification` audit: `S12 obsolete-code purge`

## Scope

Formal review of S12 commit `8a508fbe42`, grounded in the feature research,
accepted ADR, implementation plan, S12 execution record, and prior S10 audit.
The review covered the exact consumer census for deleted readers and selector,
the root session gate, the closed adopter inventory, preserved non-CLI settings,
secret-free refusals, and regression evidence. Semantic discovery was followed
by exact symbol searches and current-source inspection.

## Findings

### keychain-free-machine-operation | high | Removing the session-gate secret path makes later CLI invocations inoperable when a session cannot be persisted

`_resume_profile_session_or_refuse` now raises immediately for
`KEYRING_UNAVAILABLE` and no longer authenticates the current invocation from an
explicitly supplied factor. Login on such a host is deliberately process-scoped,
so its process exits before a subsequent profile-bound command can use the live
session. This creates a closed loop: `config login` succeeds but cannot persist,
while the next machine invocation cannot resume and is refused before its verb.
That violates the campaign's holistic machine-operability outcome. The surviving
branch is in `src/cadrumo/entrypoints/cli/__init__.py` at current line 644; the
process-only guarantee is documented in `_login_session.py` at current lines
1031-1036 and 1521 onward. The fix need not restore ambient environment discovery:
the architecture needs an explicit same-invocation authentication mechanism or
an equally machine-operable persisted-session mechanism.

### contradictory-regression-contract | medium | S12 leaves an integration test asserting the behavior the commit intentionally deletes

`TestHeadlessSecretChannel.test_configured_passphrase_unlocks_without_a_persisted_session`
in `test_profile_session_root_resume.py` at current lines 473-485 still requires
an ambient configured passphrase to unlock a later profile-bound invocation.
S12 neither migrated nor retired that contract. A default focused invocation can
misleadingly report green because this integration-marked test is deselected by
the default unit expression. Running the integration node at current HEAD reaches
an unrelated in-progress command-registration failure before the gate, so it
cannot isolate S12 dynamically, but its assertion and the deleted branch are
statically irreconcilable.

### stale-session-gate-prose | low | Production and test prose still advertises the retired ambient CLI secret channel

The root entrypoint still says command-tree access depends on
`CADRUMO_SECRET_PASSPHRASE` at current lines 227 and 840, while
`test_profile_session_root_resume.py` calls it the sanctioned headless channel
at current lines 123-129, 196, and 473-479. These statements contradict the
explicit-channel boundary. The prior S10 LOW finding in `test_config.py` was
addressed: its carrier description now describes explicit machine input or a
verified prompt, and the assertions require both channel flags without naming
the environment variable.

## Recommendations

- Resolve the keychain-free cross-process gap before accepting S12 by providing
  explicit same-invocation authentication or machine-usable persisted-session
  custody without reviving ambient CLI secret discovery.
- Add integration/subprocess proof for a host where login reports
  `session_persisted=false`, showing how the next profile-bound machine command
  executes, and run it under the correct marker.
- Reconcile or replace `TestHeadlessSecretChannel`, then remove stale
  environment-channel prose from the CLI root and session tests.
- Exact searches prove zero consumers of deleted `resolve_secrets_channel`,
  `read_secrets_stdin`, and `read_secrets_fd`. Channel readers are private under
  `read_machine_secret_payload`; selector, reader, and prompt use is confined to
  the five-command inventory and focused tests. Core `Settings` and application
  substrate resolution remain available outside CLI discovery as required.
- No CRITICAL finding was identified. One HIGH finding remains open.
