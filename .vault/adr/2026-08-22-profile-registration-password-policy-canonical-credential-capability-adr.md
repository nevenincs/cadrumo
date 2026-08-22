---
tags:
  - '#adr'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:ff27f48857f4e060ae56a9eb9ec2b6c177859f5020c30164ebbb99453811b79d'
related:
  - "[[2026-08-22-profile-registration-password-policy-holistic-credential-capability-research]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-registration-password-policy` adr: `canonical credential capability` | (**status:** `accepted`)

## Problem Statement

Profile password establishment has incompatible application and encrypted-custody
contracts. Candidates declared valid by registration and password change can fail later
inside custody, escape as adapter exceptions, and render mixed-language internal-error
output. Authentication paths can expose the same persistence diagnostic, and recovery
mnemonics are accidentally constrained by profile-password validation. The affected
capabilities and option space are grounded in
`2026-08-22-profile-registration-password-policy-holistic-credential-capability-research`
and `2026-08-22-profile-registration-password-policy-tui-custody-validation-mismatch-reference`.

This decision establishes one canonical profile-password contract, typed application
mappings for establishing, changing, and authenticating credentials, and an independent
recovery-secret codec. It refines without replacing the exact password limits and
custody guarantees accepted by `2026-08-13-profile-password-custody-rollup-adr`.

## Considerations

- Creation and password change must reject invalid candidates before KDF, staging,
  journaling, record re-heading, or publication.
- Existing-password proof must not reveal whether an attempt is malformed or incorrect.
- Application owns localized capability outcomes; custody owns cryptographic enforcement.
- Core is the only safe shared dependency of application and persistence adapters.
- Strength remains advisory and never becomes a composition gate.
- Recovery mnemonics are independent credentials, not profile passwords.
- Existing valid envelopes and byte-exact unlock behavior must remain unchanged.
- Obsolete profile-password policy paths must be deleted, not aliased or retained as
  compatibility code.

## Considered options

- **Canonical profile-password contract in core — accepted.** Application and custody
  consume one pure typed rule while preserving dependency direction and defense in depth.
- **Application-owned contract exposed through a port — rejected.** It makes a pure rule
  depend on runtime wiring or leaves custody with duplicated limits.
- **Custody-owned contract imported upward — rejected.** It reverses the architecture and
  preserves persistence-owned presentation behavior.
- **Change the generic eight-character constant and add local checks — rejected.** It
  retains conflated concepts, duplicate constraints, and no typed refusal taxonomy.
- **Catch custody errors independently at each UI — rejected.** It treats adapter symptoms,
  cannot guarantee parity, and risks hiding integrity or supervision failures.

## Constraints

- Profile passwords contain 15 through 256 Unicode scalar values and at most 1,024
  strict UTF-8 bytes. Surrogates are refused. No normalization, trimming, folding,
  replacement, case conversion, or composition enforcement applies.
- Core validation is pure and retains, logs, persists, hashes, or returns no password.
  Results contain only a typed reason and safe derived numeric facts.
- Authentication responses expose neither prospective-policy reasons nor candidate
  measurements. Malformed and incorrect attempts are publicly indistinguishable.
- Custody repeats canonical validation before cryptographic work and may not format
  operator copy.
- Recovery generation, transport, proof, and unwrap use a dedicated recovery-secret
  contract and never call the profile-password validator.
- Envelope format, KDF grid, AAD, sentinel proof, transaction ordering, password
  generation, session revocation, and no-legacy rules remain unchanged.
- Compromised-password blocklist design and normalization reconsideration are deferred.
- Recovery-based password reset is a separate archive/lineage decision and is deferred.
- Every implementation Step and every dispatched worker begins with `vaultspec-rag`
  grounding against code and governing ADRs, followed by exact-symbol confirmation.

## Implementation

A public core profile-password contract owns the named scalar and byte bounds, a finite
typed refusal-reason enumeration, and a pure assessment. Accepted assessment keeps the
existing advisory strength band as independent information. The generic eight-character
symbol no longer governs any profile capability, and obsolete profile aliases, duplicate
constants, and compatibility paths are removed with their consumers.

Registration and password change assess before any custody or transaction work, mapping
invalid results into their own typed application error families with stable translation
keys and non-secret context. Application facades expose only the profile-specific
assessment needed by inbound feedback. Custody calls the same core contract as
defense-in-depth and converts failures to internal custody errors without operator prose.

Login, password restore, current-password authorization, recovery-artifact export and
removal, and other existing-password proofs map shape and proof failures into one
authentication-refused application outcome. Integrity, transaction, corruption,
resource-supervision, and unavailable-storage faults remain distinct.

A dedicated recovery-secret codec owns strict mnemonic encoding and decoding for both
parent and supervised worker. It changes no mnemonic, recovery envelope, artifact bytes,
or proof semantics.

TUI and scripted CLI render only localized application messages. Expected typed errors
never receive generic INTERNAL guidance, and public envelopes never combine locale layers
or expose raw password diagnostics.

Acceptance requires scalar boundaries 14/15/256/257; independent byte boundaries
1,024/1,025; surrogate refusal; composed/decomposed exact preservation; no mutation on
registration or rotation refusal; parity across direct application, live TUI feedback,
TUI submission, and scripted CLI; non-oracular login and restore; unchanged operational
error classification; recovery codec roundtrips; existing-envelope unlock; rotation DEK
epoch and recovery preservation; complete locale coverage; obsolete-symbol absence; and
one-language presenter output.

## Rationale

A profile-specific core contract is the only option that provides one numerical and
semantic authority, preserves the accepted dependency direction, and lets custody defend
its cryptographic boundary without owning presentation. Typed prospective refusals give
establishment surfaces actionable feedback; deliberate collapse at proof surfaces avoids
an oracle. A separate recovery codec restores the domain independence required by the
custody rollup. Deleting obsolete paths prevents the canonicalization from adding another
layer of policy bloat.

## Consequences

Profile creation and password change gain deterministic parity with custody before any
mutation. All inbound surfaces can localize capability outcomes without inspecting
adapter exceptions, while authentication stops leaking storage-owned English details.
Custody retains exact-byte identity, current persisted formats, defense-in-depth, and
accepted transaction and recovery guarantees.

The generic credential helper can no longer claim that an eight-character floor governs
profiles. Non-profile consumers must keep explicitly named contracts. More application
error variants and locale entries are required for prospective-password guidance, while
authentication intentionally exposes less detail. Recovery transport gains a dedicated
codec and tests.

This decision does not claim compromised-password screening, Unicode normalization
compliance, or lost-password reset. Those remain visible follow-up decisions and cannot
enter this repair incidentally.
