---
tags:
  - '#adr'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-25-cli-authority-verb-conformance-campaign-close-honesty-review-audit]]"
---

# `cli-authority-verb-conformance` adr: `Profile-bound command criterion` | (**status:** `accepted`)

## Problem Statement

The profile-bound write guard is a hand-maintained catalogue of command-path
prefixes. Nothing states the CRITERION by which a path belongs in it, so
membership has been decided verb by verb and the catalogue drifts silently in
two directions.

Both directions have now been observed. A verb rename left six entries naming
paths the CLI no longer exposes, so every invoice mutation fell out of the
guard and was answered as a non-profile-bound verb, unrefusable under any
storage route. And nine mutating leaves under the `app` root sat outside BOTH
the guard and the bootstrap exemption, reachable by neither safety mechanism.
Neither was visible to any gate.

## Considerations

The guard and the bootstrap exemption are complements, not alternatives. A
verb skips the active-session gate because it must run BEFORE a profile is
unlocked (profile creation, passphrase change, recovery); a verb is guarded
because it mutates state that only an unlocked profile owns. A verb in neither
is not a third category - it is an omission.

The `app` root already carries the answer. Its own help states that app
commands operate on the active profile bucket, and its two-root split from
`config` is an accepted architectural boundary. So a mutating leaf under `app`
that no mechanism covers contradicts the root's own definition.

## Considered options

Option A, keep the catalogue hand-maintained and sweep it periodically.
Rejected: two sweeps have already missed both drift directions, and the
failure is silent by construction.

Option B, derive membership mechanically from the manifest family mutability.
Rejected on measurement: family mutability is declared per FAMILY, and a
mutating family contains read leaves (`list`, `view`), so it over-selects.

Option C, state the criterion as a rule and enforce the rule with a gate over
the live command tree. Adopted.

## Constraints

The criterion cannot be applied mechanically to every verb token. The same
token means different things in different families: `app modelo work verify`
mutates revision state while `app registry verify` reads bundled data, and
`app modelo export` writes a file rather than bucket state. A first cut of the
enforcing gate ignored this and flagged eleven registry-read and file-writing
leaves as unguarded mutations. Any enforcement must therefore be scoped to
verbs whose semantics are not in doubt, and must leave the ambiguous tail
visible rather than sweeping it into either half.

## Implementation

THE CRITERION. A live leaf under the `app` root that mutates active-bucket
state MUST be reachable by exactly one of two mechanisms: it is listed in
`PROFILE_BOUND_WRITE_VERB_PATHS`, or it is listed in
`BOOTSTRAP_EXEMPT_VERB_PATHS` because it must legitimately run before a
profile is unlocked. It MUST NOT be in neither. A leaf that only reads is in
neither by design.

ENFORCEMENT. `test_every_unambiguously_mutating_app_leaf_is_guarded_or_bootstrap_exempt`
materialises the live tree through the shipped lazy path, selects leaves whose
final token is unambiguously mutating, and asserts none is outside both
mechanisms. It carries two floors - a minimum app-leaf count and a minimum
selected-mutation count - so a materialisation collapse cannot green it. A
companion asserts every token in the set still names a live verb, so a rename
cannot silently narrow the guarantee.

RECONCILIATION. Nine leaves were outside both mechanisms and are now guarded:
ledger evidence confirm, ledger restore, the three invoice-catalogue mutations,
live justificante pull, modelo iva-wallet seed, modelo m145 create, and modelo
work resume.

## Rationale

Stating the rule rather than curating the list moves the failure from silent to
loud. The catalogue can still be wrong, but it can no longer be wrong WITHOUT
a gate saying so, which is the property the two observed drifts both lacked.

Scoping enforcement to unambiguous tokens is a deliberate trade. It buys a
total guarantee over most mutating verbs instead of a partial guarantee over
all of them, and it avoids encoding a semantic guess about verbs whose meaning
genuinely varies by family.

## Consequences

The nine newly-guarded verbs now refuse on an unattached storage route rather
than proceeding. That is the intended behaviour change and the reason this is
recorded as a decision rather than applied as a fix.

An ambiguous tail remains and is named rather than hidden: leaves ending in
`verify`, `export`, `extract`, `reconcile`, `preview` and `wizard` are outside
the enforced set and need a per-verb reading before any of them is guarded or
declared read-only. Several are near-certainly correct as they stand -
registry verification reads bundled data, several exports write files rather
than bucket state - so a mechanical sweep of that tail would be wrong.

The criterion is stated for the `app` root only. The `config` root mixes
custody, bootstrap and profile-scoped verbs, and its unguarded set was not
adjudicated here.
