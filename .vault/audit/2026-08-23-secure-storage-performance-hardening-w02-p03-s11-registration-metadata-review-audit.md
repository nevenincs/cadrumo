---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:446355fc210a46b6bfe2c2645fba4b56f18fecdf58aab129cc03c4ef700951ce'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W02.P03.S11 registration metadata review`

## Scope

Reviewed the W02.P03.S11 registration-metadata implementation against the
accepted command-scoped-loading decision and the preceding S09/S10 contracts.
The review covered the generated command and complete live-node projection,
source identities, deterministic Spanish/English generation, options and
arguments, help, hidden/deprecated flags, callback policy parity, the four
explicitly unimplemented identities, metadata-only operator discovery,
MCP/HITL reconciliation, tamper gates, and installed-package inclusion. The
review inspected only the Step-owned implementation and tests; unrelated
shared-worktree changes were excluded.

## Findings

### operator-surface-gap-reconciliation | high | Explicitly unimplemented schemas break live operator-surface parity

`test_live_operator_surface_reconciles_raw_click_paths_callbacks_and_mcp_policy_by_identity`
fails because `command_schema_refs()` publishes all 300 generated schema
identities while the materialized Click surface contains 296 implemented
identities. The exact mismatch is the four entries in
`DECLARED_UNIMPLEMENTED_SURFACES`: `config.profile.export`,
`config.profile.import`, `config.profile.rename`, and
`config.profile.subject_access_request`. The production operator inventory
filters these identities, but its authoritative live reconciliation test and
MCP/HITL compatibility contract still treat every schema reference as
callable. S11 therefore does not yet preserve the existing exact-set consumer
contract or provide one coherent meaning for the public schema-reference
projection.

Resolution: closed in the reviewed tree. `command_schema_refs()` now projects
only rows with a live CLI path, while the complete registration projection and
generation parity retain all 300 result-schema identities and exact-gate the
four stated gaps. The focused live operator-surface/MCP reconciliation and the
broader S11 integration lane pass with 296 callable identities.

### unresolved-prefix-evidence | medium | Metadata lookup drops the successfully resolved command prefix

`test_unresolved_leaf_retains_key_and_click_path_evidence` fails for
`app.not-a-real-command`: the former live resolver reported `resolved_cli_path`
as `("app",)`, while the metadata path reports an empty tuple. This weakens the
typed `SchemaResolutionError` used to diagnose an unknown or stale MCP command
identity. The complete generated node projection already contains sufficient
path information to derive the longest recognized prefix without importing a
handler subtree, so losing this evidence is not required by metadata-only
discovery.

Resolution: closed in the reviewed tree. Unknown identities now derive the
longest recognized prefix from the complete generated live-node projection and
name the first unresolved token. The existing `app.not-a-real-command` evidence
test passes without materializing a handler subtree.

## Recommendations

Resolve `operator-surface-gap-reconciliation` by making the callable schema
projection and its consumers agree explicitly on the 296 implemented versus
four declared-gap identities, then rerun the real operator-surface and MCP/HITL
reconciliation lanes. Do not silently advertise the four absent verbs or
delete their stated-gap evidence merely to satisfy the equality.

Resolve `unresolved-prefix-evidence` by deriving the longest known CLI prefix
from the generated complete-node projection and retaining it in
`VerbLeafResolutionFailure`; prove the unknown nested-key case remains
metadata-only.

Both recommendations are implemented and verified. Final review finds no open
S11 findings. The scoped Ruff and `ty` gates pass; 36 focused integration tests
and 14 command-schema unit tests pass. A real wheel build contains exactly one
`command_registration_metadata.v1.json` resource (1,932,220 bytes), confirming
the generated runtime projection is packaged.
