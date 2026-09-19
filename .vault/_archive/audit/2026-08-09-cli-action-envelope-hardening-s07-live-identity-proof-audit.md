---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:755588f9e15631c98c285a11a42ea41d64ec4f6962845046b21740d6be889aee'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S07 live operator identity proof review`

## Scope

Formal review of W01.P02.S07 changes to the operator-surface models, contract,
and contract tests, including their joins to the S05 input-schema projection
and S06 reconciliation engine. The review checked inventory provenance,
callback and root exclusions, aliases, profile policy versus MCP exposure,
result/input schema identity, mounted-family exactness, and the new
`PROVISIONING` family semantics. Validation used the focused real tests, the
independent Click-leaf/schema conformance gate, Ruff, basedpyright, and a direct
set-difference probe.

## Findings

### s07-live-identity-proof | high | The live-leaf inventory is derived from the schema registry rather than the live CLI

`test_live_operator_surface_reconciles_callbacks_aliases_and_mcp_policy_by_identity`
starts with `command_schema_refs()`, passes those registered commands into
`build_verb_input_schemas()`, and then constructs `LiveLeafInventoryRow`
instances from that result. A real Click leaf missing from the schema registry
is therefore absent from both the alleged live inventory and every downstream
comparison. The final equality between reconciled keys and input-schema keys is
an equality between projections of the same denominator. The independent
Click-tree probe currently reports no unmatched live leaves or orphan registry
keys, and the existing independent conformance gate passes, but S07's new proof
does not own or consume that independent evidence and cannot detect this class
of future drift by itself.

Resolution: closed on re-review. The integration proof now recursively walks
the materialised Click tree before consulting schema registration, normalises
each raw terminal path, declares every callback path by category, and requires
an exact identity join with registered result and input schemas.

### s07-live-identity-proof | high | MCP exposure expectation and observation share the same policy source

Each `ProfilePolicyInventoryRow.should_expose_via_mcp` is assigned by
`is_exposable_command(key)`, while the expected descriptor key set is also
computed with `is_exposable_command` and descriptor construction follows that
same MCP policy. The storage policy only supplies the descriptive
`classification`. Consequently, a mistaken exposure rule can change the
expected policy and observed MCP inventory together without producing a
reconciliation contradiction. The test proves internal agreement with the MCP
filter, not an independent canonical profile-policy-to-exposure contract.

Resolution: closed on re-review. Expected MCP identities now come from raw
terminal identities plus declared schema-emitting callbacks minus canonical
root landing exclusions. The expectation does not call the MCP exposure
filter; descriptor identities are observed independently.

### s07-live-identity-proof | high | Provisioning semantics are added without direct executable contract proof

The contract adds the `PROVISIONING` domain and the `config provision` family,
including its operator question, service owner, mutability, and command tuple.
The reviewed tests do not directly assert those semantic values or compare the
declared command tuple with live Click declaration order. Generic mounted-family
tests establish shape and reachability, and the required-child test compares
contract-owned structures. The direct probe found the schema projection in
sorted key order (`pull`, `report`, `verify`), while the live CLI declaration is
`report`, `pull`, `verify`; no reviewed test establishes which order is
canonical or proves the declared tuple against it.

Resolution: closed on re-review. The integration proof directly asserts the
provisioning domain, root, child, service owner, mutability, operator intent,
declared command tuple, and equality with live Click child order
`report`, `pull`, `verify`.

### s07-live-identity-proof | medium | The cross-layer reconciliation test is classified as a unit test

The new test inherits the module-level `unit` marker while importing and
materialising CLI, MCP descriptor, schema-surface, storage-policy, and
application-contract behavior. The repository marker contract defines such
deterministic in-process architectural crossings as integration tests. Keeping
this proof in the unit lane misstates its boundary and makes the narrow unit
suite pay for whole-surface materialisation.

Resolution: closed on re-review. The module no longer applies a unit marker to
every item: the cross-layer proof is marked integration, and application-only
tests are explicitly marked unit. The repository marker-integrity gate passes.

Validation evidence: the three focused contract tests passed; the independent
Click-leaf/schema conformance gate passed; the direct independent set probe
reported empty `live - registry` and `registry - live` sets; Ruff passed on all
three reviewed files; basedpyright reported zero errors, warnings, or notes.

Re-review evidence: the independent traversal found 303 terminal Click paths
and 10 callback dispatch paths. The callbacks partition exactly into eight
own-schema callbacks, one result-reuse callback, and one help-only callback.
The 303 terminals plus eight own-schema callbacks produce 311 unique primary
schema identities; the registered identity set is also 311 and both symmetric
differences are empty. The previously observed 306 is the 303 terminal paths
plus the three root landing callback identities (`root.status`, `root.app`, and
`root.config`), not a terminal-leaf total. It omits five other own-schema
callbacks and is therefore useful only as an explanation of that prior probe,
never as a count gate. The callback-reuse path adds a raw emitting path but no
new identity, and the help-only callback adds neither an envelope identity nor
an MCP tool.

The complete focused contract module passed 24 tests. The independent
Click/result-schema conformance gate passed. The exact marker-integrity test
passed. Ruff passed on the four reviewed files, and basedpyright reported zero
errors, warnings, or notes. An initial marker command used a nonexistent root
test path and ran zero tests; it is not counted as evidence and was replaced by
the exact repository test path and selector above.

## Recommendations

1. Feed S07 reconciliation with an independently walked, fully materialised
   Click-leaf inventory, adding callback identities through the canonical
   callback authority, and assert symmetric differences against result and
   input schema inventories.
2. Derive profile/MCP expectations from an application-owned canonical policy
   independent of descriptor filtering, then compare that expectation with
   observed descriptors.
3. Add direct executable assertions for the `PROVISIONING` domain, operator
   question, service owner, mutability, required child, and exact command
   membership/order against the chosen live authority.
4. Move the cross-layer identity proof to the integration lane while retaining
   narrow application-only model and contract assertions in the unit lane.

All four recommendations are implemented and verified; this audit has no open
S07 findings.
