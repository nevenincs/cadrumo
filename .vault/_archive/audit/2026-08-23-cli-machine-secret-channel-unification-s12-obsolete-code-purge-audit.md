---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:89e873194b2631001041c15b1567e7e5e77006e50e52ba6f612add7b3774d09e'
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

### keychain-free-machine-operation-rereview | high | Resolved - explicit root authentication closes the degraded-host dead loop

The accepted amendment now exposes `--profile-secrets-stdin` and
`--profile-secrets-fd` as a graph-owned root precondition, attempts persisted
resume first, and calls canonical `login_profile` for the exact selected bucket
only after resume refuses. The requested handler then continues inside the same
process; no CLI path reads `cadrumo_secret_passphrase`, while the separately
governed application fallback remains available to non-CLI callers.

The re-review ran the real failing-keychain subprocess nodes for profile
show/validate/history and for two passphrase rotations with old-proof refusal;
both passed. A separate fresh-process probe authenticated a profile-bound
inventory write and then a read through the root stdin channel, observed the
non-persistence Notice, and found no passphrase in either stream. The original
HIGH is closed. Descriptor mechanics and the paired root declarations are
covered by the canonical contract tests; the campaign's full cross-platform
subprocess matrix remains assigned to S13/S22 rather than to this S12 purge.

### closed-inventory-regression | high | A post-S12 ledger command repurposes the secret reader outside the five-command authority

`_ledger_inventory_cli.py` now subclasses `MachineSecretPayload` for an
inventory closing-authority document and calls both
`select_machine_secret_channel` and `read_machine_secret_payload` behind
bespoke `--authority-stdin` / `--authority-fd` options. The command is absent
from the closed five-leaf `MachineSecretSpec` inventory and therefore bypasses
the inventory metadata and non-adopter gates. Its nested fields are also bare
`dict[str, object]` rather than the typed boundary model required for a
financial authority record. This change landed after the original S12 census
and falsifies the execution record's claim that no machine-secret reader exists
outside the five-command inventory. S12 cannot close until this structured
document input uses its own typed non-secret transport authority, or the
governing decision and inventory are explicitly reconciled before code.

This payload is not substitutable for a scalar-secret payload and must not join
the five-command inventory. The secret contract is an 8 KiB object of bounded
scalar credential fields whose values are `SecretStr`; the authority record is
a variable nested evidence protocol with constrained identifiers, enums,
dates, decimal values, evidence cardinality and uniqueness, and cross-object
activity/year invariants already owned by `InventoryClosingAuthorityRecord`.
The interim three-dictionary model is strictly weaker than that domain model,
and the secret reader is not a constraint-shape superset of the document.
Replace the wrapper and double serialization with direct validation into
`InventoryClosingAuthorityRecord`. The nearest existing document contract is
the typed evidence-file loader in `_m303_filing_evidence_input.py`; the same
module's acquisition-cost stdin reader is only a partial analogue because it
is unbounded and has no descriptor channel. If anonymous stdin/fd delivery is a
required capability for authority documents, first decide a distinct bounded
structured-document transport and command-spec metadata contract, sharing only
private byte-transport primitives with secret input. Otherwise use the existing
typed file-input shape. In either case, add a conformance gate that confines
the public secret payload, selector, reader, and prompt APIs to the accepted
five leaves plus the distinct root authentication gate.

### duplicate-session-resume | medium | Profile record reads retain a second session gate after parsed-root convergence

`_profile_readiness._read_profile_record` still calls
`bind_resumed_profile_session` whenever no live session serves its bucket.
Every real executable consumer now passes through the parsed root session gate,
so this historical named-profile workaround is a redundant second resume
authority with different refusal projection. Remove the helper-local resume and
make it require the exact session already established by the root gate; migrate
direct tests to establish that precondition explicitly.

The earlier contradictory regression and stale-prose findings also remain
open. Running the ambient test directly now fails exactly as the hard cut
requires: the configured environment passphrase is ignored and the command
refuses with exit 2, while the test still asserts success. The stale root prose
continues to name `CADRUMO_SECRET_PASSPHRASE` as the condition for command-tree
access, and the session test continues to call it the sanctioned headless
channel.

### closed-inventory-regression-remediation | high | Resolved - structured authority evidence now uses its typed file contract

The inventory command no longer imports or subclasses any public scalar-secret
API. Its command spec exposes one required `--file` option, reads UTF-8 text,
and validates it directly as `InventoryClosingAuthorityRecord` before the
service call. The bespoke authority stdin/fd flags, intermediate dictionary
model, and related locale keys and tests were removed. An AST conformance gate
now fixes the exact allowed importer set for every public secret API to the five
authorized leaves and the distinct root authentication contract/gate.

### duplicate-session-resume-remediation | medium | Resolved - profile readiness requires the root-established exact session

`_profile_readiness._read_profile_record` no longer imports or invokes
`bind_resumed_profile_session`. It verifies that the active session serves the
resolved bucket and otherwise refuses. Session establishment and refusal
projection therefore have one CLI authority: the parsed root gate.

### ambient-regression-and-prose-remediation | medium | Resolved - CLI authentication is explicit while substrate configuration remains separate

The obsolete success test now proves that configured substrate material cannot
authenticate a CLI invocation without an explicit root channel. Relevant root
and session prose describes explicit authentication instead of an ambient CLI
secret channel. Application settings and substrate resolution remain available
for their separately governed non-CLI callers and are not rediscovered by the
CLI gate.

## Recommendations

- Exact searches prove zero consumers of deleted `resolve_secrets_channel`,
  `read_secrets_stdin`, and `read_secrets_fd`. Channel readers are private under
  `read_machine_secret_payload`; selector, reader, payload, staging, and prompt
  use is confined by the conformance gate to the five-command inventory and the
  distinct root authentication gate. Core `Settings` and application substrate
  resolution remain available outside CLI discovery as required.
- Keep structured evidence transports governed by their typed document models;
  do not reuse scalar-secret payload APIs for variable nested records.
- No CRITICAL, HIGH, or MEDIUM finding remains open.
- Final disposition: both HIGH findings are closed. The structured-document
  command is outside the scalar-secret transport by construction, the duplicate
  readiness resume is gone, the ambient regression and prose are corrected,
  and the exact consumer census plus focused integration, lint, type, import,
  locale, and Vault checks permit S12 to close.
