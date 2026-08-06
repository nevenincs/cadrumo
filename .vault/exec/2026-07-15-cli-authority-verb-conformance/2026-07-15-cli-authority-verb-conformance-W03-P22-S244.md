---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:9049eb3ad2de1fc051e952945aeb3bef834888c8f7f908b65b52ea7de1f89e34'
step_id: 'S244'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove duplicate namespace metadata from profile, calculation, aggregation, and filed-observation repositories and bind repository construction to registry definitions

## Scope

- `src/cadrumo/application/user_profile/`
- `src/cadrumo/application/calculations/`
- `src/cadrumo/application/aggregation/`
- `src/cadrumo/application/live/`

## Description

- Enumerate every module-level namespace, sensitivity and schema-version constant across the four cited trees and classify each as registry-sourced or a raw literal.
- Confirm the repositories in all four trees already bind construction to registered definitions.
- Find the one remaining raw-literal set, declared verbatim in two modules, and establish that no gate observes its drift.
- Single-site it in the module that owns the carry, binding each member to its registered definition.
- Add a gate proving the set's subtraction is load-bearing and effective, and prove that gate can fail.

## Outcome

Partly satisfied at HEAD. The repository-construction half was already done; one unguarded duplicate remained, implemented under commit `473a4f3625`.

Every repository in the four cited trees already binds its construction metadata to a registered definition. The profile value and snapshot repositories, the workflow state and run persistence, the Clave diagnostics writer, the justificante capture snapshot, and the repair-decision store all read the namespace, sensitivity, schema version, or required default object key straight off the definition. Forty-four such bindings exist across the four trees and not one raw namespace literal survives in a repository. That half of the step needed nothing.

What remained was a set of five namespace strings declared verbatim in two separate modules. These are the namespaces that ride dedicated typed bundle fields rather than the generic secure-object carry. One copy lived in the custody-carry module, where the set is subtracted from the registry-derived carry list so a typed store is not carried twice. The other lived in the bundle module, where the same five are counted as covered when the full-custody coverage manifest is assembled. Two copies, two different decisions, both restating strings the registry owns.

The reason this one mattered while its neighbour did not is the shape of the failure. The custody-carry module also holds a per-namespace natural-key resolver map with roughly forty namespace-keyed entries, and those are equally literal, but they are cross-checked: an existing gate walks the registry-derived carry list and asserts every carried namespace has either a resolver or a fixed default key, so a drifted resolver key surfaces as a gate failure, and the export path is fail-closed besides. The typed-category set is subtractive instead. A member that drifted from the registry would simply stop matching, silently re-admitting a typed store into the generic carry and double-carrying it, and nothing observed that. The resolver keys are guarded lookup keys; the typed-category set was an unguarded second authority. Only the latter was changed.

The set now lives once, in the custody-carry module, with each member naming its registered definition rather than its string, and the bundle module reads that one set. A gate was added because none existed for this exclusion. It pins both halves: every member must be a namespace the full profile would otherwise carry, so the subtraction is not a silent no-op, and no member may survive into the generic carry. The non-vacuity half is the important one, and it was checked against live data rather than assumed. The full profile offers forty-six carry candidates and the generic carry emits forty-one, a difference of exactly these five, so the subtraction is demonstrably load-bearing. A control confirmed the guard bites: substituting a non-existent namespace for a real member leaves it outside the candidate set and trips the first assertion.

Verified with six tests in the custody-completeness gate, up from five. Both lint passes and type checking are clean on the three touched files, and collect-only is clean at fourteen thousand three hundred and ninety tests.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list, so the constant inventory that drove this step came from a tree-wide grep for module-level metadata declarations rather than from search. That inventory is what separated the forty-four registry-sourced bindings from the one raw-literal set; a name-based search would not have found it, because the duplicated symbol was spelled identically in both modules and neither name resembles the registry's.

Two other literal families in these trees were examined and deliberately left. The bundle and custody modules both hold cryptographic domain-separation labels and additional-authenticated-data byte strings; those are versioned crypto context values, not secure-object namespaces, and collapsing them into the namespace registry would change key derivation. Separately, the aggregation service carries a service-owner attribution string and the outbound client a caller string; both are provenance labels rather than storage namespaces.

The suite run over the whole profile tree reported four failures in the login-session and logout modules. These are the known host limitation rather than a regression: the probes' own fixture refuses with an explicit message stating the host has no usable operating-system keychain to custody the session key, and it records that login itself succeeded and correctly degraded to a process-scoped session. Neither module is touched by this step. Type checking the same tree reports six diagnostics, all in two recovery-related probe modules that are likewise untouched here; the three authored files type-check clean in isolation.

The shared index again held another agent's staged work, this time vault documents. It was excluded by naming only authored paths on the commit.
