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

Re-reviewed reopened W02.P03a.S11 after the S54 hard cut. The corrected scope is production CommandSpec-derived result-schema and operator-help discovery, exact input contracts, localized help, lazy target ownership, and fresh-process import behavior. Historical latency measurements were retained as observations only; generated-resource and materialized-tree claims were rejected. Concurrent registry work was excluded.

## Findings

### operator-surface-gap-reconciliation | high | Historical generated-resource finding superseded by S54

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

Historical resolution: this described the pre-S54 generated projection and is no longer a current-state claim. S54 retired the generated inventory and the four-gap model. Current schema references derive the exact production CommandSpec identity set.

### unresolved-prefix-evidence | medium | Historical generated-node finding superseded by S54

`test_unresolved_leaf_retains_key_and_click_path_evidence` fails for
`app.not-a-real-command`: the former live resolver reported `resolved_cli_path`
as `("app",)`, while the metadata path reports an empty tuple. This weakens the
typed `SchemaResolutionError` used to diagnose an unknown or stale MCP command
identity. The complete generated node projection already contains sufficient
path information to derive the longest recognized prefix without importing a
handler subtree, so losing this evidence is not required by metadata-only
discovery.

Historical resolution: this described the deleted generated live-node projection and is not current evidence. Current unknown identities fail against the CommandSpec identity and path projection without a generated prefix oracle.

### generated-resource-evidence | critical | Prior completion mechanism is nonconforming and superseded

The former audit treated an ignored generated JSON resource, its development generator, and wheel inclusion as successful architecture. The accepted child ADR rejects that dependency inversion. S54 physically deleted the resource, reader, generator, ignore entry, parity tests, and adjacent mirrors. The historical latency numbers remain observations but provide no completion proof.

Resolution: closed. Current schema and operator-help discovery projects the tracked production CommandSpec graph directly. No serialized intermediary, generation step, fallback, or second authority exists.

### behavior-import-during-help | high | Toggle choices imported a behavior target during discovery

Fresh-process proof found schema discovery importing `_capabilities_cli` because choices for `config.profile.capabilities.set` were inferred from the handler-owned `Toggle` enum.

Resolution: closed. The immutable ValueContract owns the `on` and `off` choices, and the runtime compiler constructs its Click choice directly from that tuple. The behavior accepts the validated string and no private handler enum remains. All current result-schema and input-help identities project with zero newly imported behavior target modules.

### dormant-materialized-aliases | medium | Compatibility aliases preserved rejected terminology and fallback surface

Two unused private aliases retained the old materialized-schema names even though they delegated to the graph.

Resolution: closed by physical deletion. Exact source scans find no generated resource reader, schema registry, materialized compatibility alias, or development generator.

## Recommendations

Preserve the latency observations only with their historical qualification. Maintain dynamic exact graph-set, runtime-choice parity, and newly imported behavior-target tests; never restore a generated artifact, registry, mirror, alias, or materialized-tree oracle.
