---
tags:
  - '#adr'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - "[[2026-06-15-service-capabilities-research]]"
---



# `service-capabilities` adr: `Profile-linked service capabilities: opt-in/opt-out for Google export, LLM vision, and cloud evidence upload` | (**status:** `accepted`)

## Problem Statement

The app integrates external services — Google export, on-host LLM vision, and
cloud-CLI providers that may receive sensitive financial evidence — but has no
notion of which services a profile opts into (research F1). Every gate keys on a
process-global `Settings`/env flag (research F2), so a gestor with a personal
profile (cloud upload allowed) and a client profile (cloud barred) cannot express
the two postures: `aeat_evidence_gestor_mode` / `aeat_evidence_cloud_upload_permitted`
are one value for the whole install. There is no operator-facing surface to review
or set "what is this profile allowed to use." The right home — per the operator —
is the user profile.

## Considerations

- The profile already owns a strict, schema-driven, effective-dated fact catalogue
  persisted through a single-writer encrypted repository, with a wizard/edit CLI
  and snapshot machinery. Adding capabilities as a new schema section reuses all of
  it (validation, persistence, wizard, edit, snapshot) for free.
- Capabilities are operator *intent*, distinct from (a) the global safety posture
  (gestor mode, the secure-storage invariant) and (b) dependency availability
  (is Ollama running?). A clean model keeps the three axes separate and ANDs them
  at the gate.
- The cloud-upload posture is regulated (`sensitive-financial-data-secure-storage-only`,
  `2026-06-13-llm-evidence-classification-adr`). A profile capability must never be
  able to *widen* the global safety floor — only narrow it. Gestor mode stays an
  absolute bar regardless of any profile opt-in.
- `aeat-schema-central-config` wants closed value sets in the registry/schema, not
  Python literals; the capability set is a closed enum.

## Constraints

- The capability section rides the encrypted secure-record persistence path
  (capability flags are low-sensitivity but inherit the record's storage). No new
  parallel store (`composition-service-no-parallel-write-path`).
- Gates currently take `Settings`; introducing profile capabilities means a
  resolution layer, not a signature break everywhere. The resolution must have a
  safe default when no profile/fact is present (back-compat with the global flag).
- Parent features (profile schema/wizard/edit, the evidence consent gate, the
  vision path) are all shipped and stable; this layers additively on them.

## Implementation

**Decision: model service capabilities as a first-class, schema-driven profile
section, and gate every external service on `resolve_capability(profile, settings,
capability)` — the AND of operator opt-in, the global safety floor, and (at the
CLI) dependency availability. Capabilities narrow, never widen, the global posture.**

1. **Capability taxonomy (core).** A closed `ServiceCapability` `StrEnum` in `core/`
   per `aeat-schema-central-config`: `cloud_evidence_upload`, `llm_vision`,
   `google_export` (extensible: `aeat_live_capture` later). Each member documents
   the service it gates and its default posture.

2. **Profile schema section (registry).** A `capabilities` `[[sections]]` in
   `user_profile/schema.toml` with one `boolean` field per capability, default
   matching the conservative global default (cloud upload off; vision/google on
   where the global default is permissive). Persisted as `UserProfileFact` rows in
   the encrypted `UserProfileRecord` — no code change to the persistence path.

3. **Resolution layer (application).** `resolve_capability(capability, *, profile,
   settings) -> CapabilityDecision` reads the profile's capability fact, falls back
   to the global `Settings` default when the fact is absent (back-compat), and
   returns a typed decision carrying the reason (opted-out by profile / barred by
   global posture / permitted). For `cloud_evidence_upload` the resolver ANDs the
   existing three-condition gate: gestor-mode bar **first** (absolute), then the
   profile opt-in (replacing the global `aeat_evidence_cloud_upload_permitted` as
   the operator-intent layer, with the global flag as the no-profile fallback),
   then the per-invocation ack. The resolver lives beside the gate, not in domain.

4. **Gate rewiring.** `cloud_evidence_read_permitted` gains an optional
   `capabilities`/profile argument and consults the resolver; the on-host vision
   path checks `llm_vision`; the Google export entry points check `google_export`.
   Each gate, when a capability is opted out, raises the existing typed refusal /
   emits a typed `Notice` (per `cli-notices-are-the-only-diagnostic-channel`) naming
   the capability and the `config profile capabilities set` command to enable it —
   never a silent no-op (`no-silent-under-declaration`).

5. **CLI surface.** `aeat config profile capabilities show` (the resolved state of
   every capability for the active profile, with its source: profile-fact vs
   global-default vs barred) and `... capabilities set <capability> <on|off>`
   (routes through the existing `EditProfileSectionCommand` single writer). The
   wizard create/edit flow gains a `capabilities` section so opt-in/out is offered
   at profile creation.

6. **Surfacing.** `config profile capabilities show` and `config profile status`
   report each capability's resolved posture; the dependency `doctor` (ADR B) adds
   the availability axis so the operator sees opted-in-but-unavailable vs
   opted-out vs ready.

## Rationale

The profile is the operator's identity and the natural home for "what this identity
is allowed to do," exactly as the operator framed it. Reusing the schema-fact
machinery avoids a parallel capability store and inherits validation, encryption,
wizard, and edit for free (research F1, the reference map's preferred home). Keeping
capabilities as a *narrowing* intent layer over the global safety floor preserves
the regulated cloud-upload invariant — a profile can turn cloud upload **off**, but
turning it "on" still requires the global posture to permit and gestor mode to be
absent, so the safety floor is never raised by operator preference. Routing the
opt-out through a typed refusal/Notice (not a silent skip) keeps the operator
informed (`no-silent-under-declaration`).

## Consequences

- A gestor can run a personal profile that uses cloud CLIs and a client profile
  that bars them, from one install — the headline operator need.
- The three axes (intent / safety / availability) are cleanly separable and
  ANDed at the gate, so reasoning about "why didn't this run" is a single resolved
  decision with a typed reason.
- Migration: existing profiles have no capability facts, so the resolver falls back
  to the global `Settings` defaults — zero behaviour change until an operator sets a
  capability. No data migration (consistent with `no-legacy-compatibility`: the
  fallback is forward-functional default resolution, not legacy-shape tolerance).
- A capability cannot widen the safety floor; an operator who expects "I turned
  cloud upload on" to override gestor mode is correctly refused with a typed reason.
- Pitfall to avoid: scattering capability checks. Every gate must route through the
  one resolver so the posture is computed in exactly one place.

## Codification candidates

- **Rule slug:** `service-capabilities-narrow-never-widen`.
  **Rule:** A per-profile service capability MUST be resolved through the single
  capability resolver and may only NARROW the global safety posture (it can opt a
  profile OUT of a service the install permits; it can never opt a profile INTO a
  service the global safety floor — gestor mode, the secure-storage invariant —
  forbids). Deferred until the surface ships and a review confirms the resolver is
  the sole gate path.

## Codification candidates


