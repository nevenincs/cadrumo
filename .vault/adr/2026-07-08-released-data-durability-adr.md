---
tags:
  - '#adr'
  - '#released-data-durability'
date: '2026-07-08'
modified: '2026-07-10'
related:
  - "[[2026-07-08-released-data-durability-research]]"
---

# `released-data-durability` adr: `version gates become ceilings with an upgrade dispatch` | (**status:** `accepted`)

## Problem Statement

The application persists taxpayer data — profiles, filed-return records and
evidence, the ledger, calculation revisions, justificantes, attachments — in an
encrypted store that Spanish tax law effectively requires to stay readable for
years (four-year LGT prescription as the routine floor, longer for some
obligations). The 2026-07-08 durability audit (see the related research) found
that while the key hierarchy and ciphertext handling are durable, every persisted
format's version gate is strict equality: secure-object rows, the profile bundle,
and the sealed bucket archive all refuse any record whose stored version differs
from the current constant, in either direction. The bundle schema has already
moved v1→v2→v3 with prior versions dropped, and a test asserts a v1 archive is
refused now that v2 is current. Under the no-legacy posture this is correct for
pre-beta churn, but the first post-release version bump would silently strand
years-old filings, and no accepted decision governed the transition. The operator
directive is: keep every format at its current version — secure-object namespaces
at 1, archive at 2, bundle at 3 — and future-proof the mechanism now.

## Considerations

- The no-legacy rule already blesses exactly this shape: "a `max_supported_version`
  ceiling that refuses a FUTURE shape is forward-compatibility [kept]". The
  implementation must be brought up to what the rule already claims.
- No stored data exists at any version other than the current one, so no upgrade
  function needs to be written today — only the dispatch structure and the gate
  that forces one to exist before a bump ships.
- Secure-object AEAD binds the row's own `schema_version` into the associated
  data, so an old row must be decrypted under its written version and upgraded as
  plaintext afterwards; read-side upgrade must not rewrite the row.
- The audit swarm and quality-gate rules forbid mocks and monkeypatching; the
  upgrade chain must be testable by passing a real mapping, not by patching a
  module global.
- A future-version refusal and a missing-upgrade-path refusal are different
  operator situations (downgrade attempt vs. broken upgrade shipping) and must be
  distinguishable in the error surface.

## Considered options

- **Do nothing until release** — rejected: the flip has no owner or trigger, and
  the bundle/archive history shows version bumps happen casually; the mechanism
  must precede the next bump, not follow it.
- **Write migrations now for the dropped bundle/archive versions (v1/v2 bundle,
  v1 archive)** — rejected: pre-beta data from those versions cannot exist by the
  no-legacy premise; resurrecting readers for data that never shipped is dead
  code. The durability floor starts at the current version.
- **Ceiling semantics plus an explicit per-hop upgrade dispatch, empty today,
  enforced by a completeness gate (chosen)** — behaviour-preserving at every
  current version, zero migration code, and a version bump without a registered
  upgrade path becomes a loud CI failure instead of silent stranding.

## Constraints

- Read paths must keep failing closed: a version above the ceiling, or below the
  durability floor, or with an incomplete upgrade chain, refuses loudly with the
  stored and expected versions named. No silent coercion.
- The durability floor for each format starts equal to its current version and
  may only move forward through a superseding accepted ADR (it is the "we may
  drop readers older than this" line — post-release it can effectively never
  move for filed taxpayer data).
- Upgrade functions transform one hop (version N to N+1) of the decrypted
  plaintext payload; chains compose hops. Ciphertext, AAD, and revision lineage
  metadata are never rewritten by a read.
- The no-legacy rule stands: this ADR adds no read-tolerance of shapes nothing
  wrote; it adds the mechanism the rule already describes as kept.

## Implementation

One new storage-substrate module owns schema lineage: per-format current-version
and durability-floor constants, a typed upgrade-registry mapping
`(namespace, from_version)` to a one-hop payload upgrader, a chain evaluator that
reports missing hops, and an application function that upgrades a payload from
its stored version to the current version or raises naming the first missing
hop. The secure-object row codec replaces its strict-equality check with: refuse
`schema_version` above the caller's ceiling (future), decrypt under the row's own
version, then chain-upgrade the plaintext to current, stamping the returned
record at the version its payload now conforms to. The registered-namespace row
check applies the same ceiling semantics. The profile bundle derives its
supported-version set from floor..current and routes deserialization through a
single validate function that chain-upgrades the raw JSON payload before strict
model validation; the encrypted-bundle transport envelope and the sealed-archive
import gate split their refusals into future-version versus below-floor, through
a pure version-policy function shared with tests. A new lineage gate test
asserts, for every registered secure-object namespace and for the bundle format,
that every version from the durability floor to current has a complete upgrade
chain — vacuously green today, red the moment a version bump lands without its
upgrader. New refusal messages ride the locale catalogues via the locale CLI.

The archive tier is deliberately weaker than the other two: it carries the
floor/ceiling range gate and the future-versus-below-floor refusal split, but
NO upgrade dispatch — archive version differences are container-structural
(member layout, header shape), so the mechanism a widened range would need is
a version-aware reader, not a payload transform. Until such a reader exists,
the archive lineage gate pins the durability floor EQUAL to the current
version: raising the archive version forces an explicit same-change decision —
raise the floor with it (dropping older archives, the pre-release posture) or
land the version-aware reader plus a real old-archive restorability test and
widen the pin then. A floor held below current without that machinery would
pass the range gate green while restore misreads the old layout; the pin makes
that state unrepresentable. (Amended 2026-07-09 after an independent honesty
review found the original text over-claimed an upgrade dispatch "for the
archive format".)

## Rationale

The research verdict was PARTIAL: cryptographic durability is real (Argon2id
params persisted per bucket, DEK wrap, BIP-39 recovery, atomic rotation), format
durability is absent (strict-equality gates at every boundary, versions already
bumped with old readers dropped, no governing decision). Closing the gap now is
the cheapest it will ever be: every format sits at a single version, so the
change is pure mechanism — no data transformation exists to get wrong. The
completeness gate converts the durability guarantee from author discipline into
a structural invariant, the same enforcement shape the project uses for
casilla provenance and export parity.

## Consequences

- A future schema bump now has a forced cost: register the one-hop upgrader (and
  its test) or the lineage gate stays red. That cost is the point.
- Old rows read through an upgrade chain are upgraded in memory on every read
  until a write re-persists them at current; read-repair is deliberately out of
  scope here and can be a follow-up decision if read-path upgrade cost ever
  matters.
- The strict pydantic models still refuse old payload shapes that predate a
  version bump the author forgot to stamp; the gate catches the stamped case,
  and the roundtrip discipline's populated-fixture rule remains the guard for
  unstamped drift. A committed cross-version fixture corpus ("yesterday's bytes
  loaded by HEAD") is the natural follow-up hardening and is not decided here.
- The no-legacy rule needs a one-paragraph Status amendment at its vaultspec
  source recording that ceiling-plus-dispatch is the implemented meaning of its
  forward-compatibility carve-out; that edit follows the rule-editing discipline
  and is not part of this ADR's code change.
