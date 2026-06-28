---
tags:
  - '#adr'
  - '#cli-ledger-testimonials'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-19-profile-lifecycle-disaster-adr]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-active-profile-storage-runtime-classification-closeout-audit]]'
  - '[[2026-06-03-cli-ledger-testimonials-plan]]'
  - '[[2026-06-04-cli-ledger-testimonials-research]]'
---



# `cli-ledger-testimonials` adr: `Active-profile name-or-UUID resolution at the application boundary` | (**status:** `accepted`)

## Problem Statement

An operator addresses their profile by the display label they chose at
`profile create` (e.g. `operator`, `tester`); the immutable UUIDv4 bucket id
is never surfaced to them. But the active-profile env override
`AEAT_ACTIVE_PROFILE` — the highest-precedence rung of the active-profile
precedence chain — feeds its raw value straight into the canonical
storage-route resolver, which treats it as the bucket directory name and builds
`buckets/<value>/db/aeat.db` directly. So a real operator who sets
`AEAT_ACTIVE_PROFILE=operator` (the only identifier they know) hits a hard
refusal — `Profile 'operator' has no registered bucket manifest at
buckets/operator` — on every profile-bound command, while the same export set to
the never-seen UUID works. This is a genuine operator-facing CLI dead-end, not a
test artifact: a fresh-process reproduction confirmed the env-var-by-name path
fails end-to-end. The persona-testimonial swarm missed it because it never
exercised the fresh-process env-var entry. Surfaced as honesty-review finding
`#53` / plan step `P02.S05`; the grounding check that proved it real is the
fresh-process `AEAT_ACTIVE_PROFILE=<label>` repro.

## Considerations

- The active-profile state model is the one fixed by the prior profile-lifecycle
  disaster decision (Ruling 2): three load-bearing sources — the
  `AEAT_ACTIVE_PROFILE` env override (highest precedence), the `active-profile`
  pointer file (written by `profile create`/`switch`/`import`/`rename`/`delete`),
  and manifest existence at `buckets/<id>/manifest.toml` whose body carries the
  display label. The env override and pointer are designed to carry the bucket
  `<id>`; the label lives in the manifest body.
- That same disaster decision mandates a SINGLE canonical resolver for the
  active-profile → storage-bucket coupling (the "one resolver" / central
  route-derivation boundary): the `core.config` route resolver
  (`classify_storage_route` / `settings_for_active_profile_bucket` /
  `_resolve_database_url`), which delegates to the pointer reader. The unified
  storage-runtime manager (`StorageRuntime`, in the persistence adapter layer) is
  a readiness/diagnostic wrapper that CONSUMES that config resolver — the
  dependency direction is runtime → config, never the reverse. So routing the fix
  "through the runtime" is infeasible: the runtime already routes through config,
  and config is the canonical bottom.
- The name → UUID resolution requires a manifest scan (read every
  `buckets/*/manifest.toml`, match the label). That scanner is the application-
  layer `resolve_profile_bucket` (added for the diagnostics path under the same
  finding). Display labels are unique among live profiles (the name-uniqueness
  guard), so a label resolves unambiguously.

## Constraints

- HEXAGONAL LAYERING: `core.config` (core) MUST NOT import the application-layer
  manifest scanner, and the persistence-adapter `StorageRuntime` MUST NOT import
  application either (adapters do not depend on application). So the name → UUID
  scanner can live in NEITHER the core route resolver NOR the adapter runtime —
  both sit below application. Putting a second scan into core would also duplicate
  the scanner, violating the one-resolver invariant.
- ONE-RESOLVER INVARIANT (disaster decision, Ruling 2): the storage-route
  derivation must have a single canonical implementation; no parallel route
  resolver may be introduced. The fix must therefore reuse the existing
  `settings_for_active_profile_bucket` route boundary and the single
  `resolve_profile_bucket` name resolver — not hand-roll either.
- BACKWARD COMPATIBILITY: a UUID-valued `AEAT_ACTIVE_PROFILE` or pointer must
  resolve byte-identically to today; the name path turns a current hard-fail into
  a resolution and changes nothing that already works.
- CONFIRMATIONS (verified for this decision): (1) `Settings` is loaded LAZILY —
  `load_settings()` constructs a fresh `Settings()` from the environment on each
  call (honouring an `override_settings` block first), not an eager module-level
  instance — so an application-layer normalization that runs before the storage
  route is resolved is effective. (2) The pointer file holds the UUID in every
  production path (`profile create`/`switch` write `bucket_id=<uuid>`); the
  display LABEL enters active-profile resolution only via the
  `AEAT_ACTIVE_PROFILE` env override. So the normalization target is the
  env-override → active-bucket resolution that feeds the route boundary.

## Implementation

Normalize the active-profile identifier from a display label to its UUID at the
APPLICATION boundary — the only layer that may host the manifest scanner — then
feed the EXISTING canonical core route boundary
(`settings_for_active_profile_bucket`) a UUID, exactly as it expects today. The
single name → UUID resolver is the already-committed application-layer
`resolve_profile_bucket` (UUID-direct fast path; manifest-scan-by-label fallback
only on a direct miss; a clear ambiguity error on more than one live label match,
never an arbitrary pick). It already serves the diagnostics `profile get/set`
path; this decision makes it also serve the active-profile resolution that the
work/ledger commands use, so there is ONE name resolver and ONE route resolver.
`core.config` stays UUID-only and byte-identical on the UUID path — it is not
touched, preserving the one-resolver invariant and core purity. The resolution
sites that resolve the active bucket for storage (the active-bucket-id resolution
feeding `settings_for_active_profile_bucket` and the profile-record load) consume
the normalized UUID. No new resolver, no config hand-roll, no core → application
or adapter → application edge.

## Rationale

The decision honours the disaster decision's two load-bearing properties rather
than working against them: the canonical route resolver in `core.config` stays
the single coupling-resolution interface, and `resolve_profile_bucket` stays the
single name resolver. The only architecturally-available home for the manifest
scan is the application layer (core and the adapter runtime both sit below it and
cannot import it), and because the lower layers consume an `<id>` and never
resolve a name themselves, normalizing the name to a UUID at the application
boundary introduces no second route resolver — it bridges the env-override INPUT
(a label, per Ruling 2 source 1) to the manifest IDENTITY (the UUID dir, per
Ruling 2 source 3). The "route through the unified runtime" instinct was correct
in spirit (do not hand-roll a competing resolver) but infeasible in mechanism
(the runtime consumes config; neither can host the application scanner); this
decision delivers the same single-resolver guarantee at the layer that can
legally hold the scan.

## Consequences

- GAINS: a real operator-facing dead-end is removed — `AEAT_ACTIVE_PROFILE=<label>`
  now opens the operator's profile, matching the identifier operators actually
  know. The UUID path is unchanged. One name resolver and one route resolver
  remain; no duplication.
- DIFFICULTIES: `core.config` is load-bearing (the disaster decision's resolver),
  so the change is deliberately kept OUT of it — all behaviour change is at the
  application boundary, and a wider regression slice (config/settings + profile
  resolution + a modelo-work sample) guards the UUID path.
- PITFALLS avoided: no second manifest scanner in core (would re-split the
  resolver the disaster decision unified); no arbitrary bucket pick on an
  ambiguous label (a wrong silent pick on a tax profile is a data-integrity
  hazard — the resolver raises a clear ambiguity error instead).
- PATHWAYS: the application-boundary normalization is the single seam through
  which any future label-addressed active-profile input (interactive/server modes)
  resolves, without re-opening the core resolver.

## Codification candidates

- **Rule slug:** `active-profile-name-normalized-at-application-boundary`.
  **Rule:** Resolve an operator-facing profile label to its UUID bucket id ONLY
  through the single application-layer profile resolver and feed the canonical
  `core.config` route boundary a UUID; never add a name→UUID (manifest-scanning)
  resolver into `core` or the persistence-adapter storage runtime, and never
  hand-roll a second storage-route resolver — the disaster-decision one-resolver
  invariant and hexagonal layering both forbid it.
