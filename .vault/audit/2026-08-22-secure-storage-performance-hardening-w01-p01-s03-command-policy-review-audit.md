---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:d910730fc5162f99629590bf7294e91b58283ea457944fa02895b5f900e3c963'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W01.P01.S03 command execution policy review`

## Scope

Reviewed the W01.P01.S03 callback-attached execution-policy seam against the
accepted command-scoped-loading decision, the live census and capability
taxonomy established by W01.P01.S01 and W01.P01.S02, and the repository's CLI,
storage-routing, secure-data, and quality rules.

The review inspected callback attachment under both Typer decorator orders,
eager and lazy Click materialisation, executable and non-executing groups,
absence and corrupt-metadata handling, handler identity, declaration
contradictions, import-light structure, and whether the tests obtain policy
from the materialised callback rather than restating a path-keyed oracle.
Focused integration evidence completed with 15 passing tests.

## Findings

### cross-axis-underdeclaration | high | Storage routing and filing handoff can contradict the declared capability and side-effect envelope

`CommandExecutionPolicy.__post_init__` validates that any non-`none`
`write_route` has a `local-state` effect, but it does not require a storage
authority. A policy with only `registry`, `local-state`, and
`write_route="profile-bound"` is therefore accepted even though the route means
the callback enters active-profile storage. This lets the later import and
capability gate receive an authority declaration that is known to be incomplete
at construction time. The inverse handoff gap is similar: `handoff=True` only
requires the implied `filing` capability, so a filing handoff declaring the
effect-free set `{none}` is accepted even though this risk axis denotes
production of a filing-grade artefact. These are safety-relevant
under-declarations in the metadata intended to replace the existing write-route
and risk catalogues, and neither contradictory branch has a focused negative
test.

### nested-policy-types | medium | The policy record does not enforce its nested classification or boolean judgment types

The dataclass accepts a duck object as `classification` when it exposes
`side_effects` and `expanded_capabilities`, and accepts integer or other truthy
values for `destructive`, `handoff`, and `live_write`. In contrast, the sibling
capability record and the policy decorator fail loudly on unknown or incorrectly
typed metadata. A dynamically assembled or cast declaration can consequently
enter the census without being a `CommandCapabilityClass` or without carrying
literal boolean judgments; malformed instances may then fail later in a gate or
serialize misleadingly. The focused suite proves an invalid top-level decorator
argument and an invalid attached attribute are rejected, but does not exercise
these nested type boundaries.

### cross-axis-underdeclaration-resolution | low | Re-review confirms the authority and effect contradictions now fail at construction

Resolved on re-review. Every non-`none` storage route now requires both the
`local-state` effect and the expanded `profile-custody` capability, while a
filing handoff requires both the expanded `filing` capability and the
`local-state` effect. Focused negative specimens independently exercise an
under-capable bootstrap route and an effect-free filing handoff. Existing
positive specimens continue to construct state-free and profile-custody write
policies and carry the latter through real lazy Click materialisation.

### nested-policy-types-resolution | low | Re-review confirms nested policy metadata is exact and fail-loud

Resolved on re-review. Construction now requires an actual
`CommandCapabilityClass` and exact `bool` instances for `destructive`,
`handoff`, and `live_write`. Focused specimens prove that a string
classification, integer destructive flag, string handoff flag, and null live
write flag are all rejected rather than entering the census. The validation
adds no heavy dependency beyond the already-owned lightweight capability
module.

## Recommendations

For `cross-axis-underdeclaration`, strengthen construction-time validation so a
profile-bound or bootstrap-root storage route requires the minimum owning
storage capability selected by the campaign's taxonomy, and so a filing handoff
cannot claim an effect-free invocation. Add negative cases that independently
prove each invalid cross-axis combination is rejected, plus positive cases for
the legitimate route and handoff shapes used by subsequent enrollment Steps.

For `nested-policy-types`, require an actual `CommandCapabilityClass` and exact
boolean values for all three risk judgments, then add focused tests using a
duck-typed classification and non-boolean judgment values. Keep this validation
inside the import-light policy module and preserve the current unchanged-callback
decorator behavior.

One HIGH finding remains open. No CRITICAL finding was identified. Callback
attachment order, eager/lazy materialisation, honest absence for unannotated or
non-executing nodes, handler identity, and the anti-tautology census specimen
were otherwise supported by direct runtime evidence.

Re-review outcome: the HIGH and MEDIUM findings above are resolved. The focused
integration suite completed with 21 passing tests. No HIGH or CRITICAL finding
remains, and no new safety, architectural-intent, identity, import-lightness, or
anti-tautology defect was identified.
