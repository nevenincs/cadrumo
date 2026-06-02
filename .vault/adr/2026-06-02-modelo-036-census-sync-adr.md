---
tags:
  - '#adr'
  - '#modelo-036-census-sync'
date: '2026-06-02'
related:
  - "[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]"
  - "[[2026-05-16-modelo-036-census-sync-plan]]"
  - "[[2026-05-16-modelo-036-census-sync-research]]"
---

# `modelo-036-census-sync` adr: `Modelo 036 census sync rollout under Spanish censo naming` | (**status:** `accepted`)

## Problem Statement

The 2026-05-16 plan enumerates the Modelo 036 ("Mis Datos Censales")
G313 sync surface in English: every plan identifier uses "census" /
`_census.py` / `CensusSnapshot` / `CensusSnapshotService`. The
shipping codebase consistently uses the Spanish stem `censo` —
`_censo.py`, `CensoSnapshot`, `CensoSnapshotService`,
`BucketEventType.CENSO_REFRESHED`, `config profile censo refresh`,
locale keys `cli.config.profile.censo.*`. This ADR records the
Spanish-naming decision and confirms that the plan's English-named
Steps are satisfied by their Spanish-named implementations.

## Considerations

- The project's wider naming convention favours Spanish stems for
  domain concepts that map 1:1 to AEAT surfaces (`iva` not `vat`,
  `renta` not `personal income tax`, `casilla` not `box`, `modelo`
  not `form`). "censo" follows that pattern.
- The G313 page is titled "Mis Datos Censales" — the authoritative
  AEAT vocabulary is the Spanish noun. Naming after the operator-
  visible AEAT surface keeps developer-vs-operator vocabulary
  aligned.
- The plan predates the Spanish-naming codification. Re-titling
  the plan Steps would churn the step-identifier surface for no
  behavioural change; the plan Steps stay verbatim and this ADR
  records the naming-shape resolution.

## Constraints

- Operator-facing surfaces (locale keys, CLI verb spellings, audit
  trail field names) MUST use the Spanish stem `censo`.
- Internal symbols MUST use the Spanish stem — no English `Census*`
  shim classes, no `_census.py` re-export module.
- Pre-ADR plan documents keep their English Step text verbatim; the
  exec record explicitly names the Spanish symbol that satisfies
  each English-named Step.

## Implementation

The rollout shipped under `censo`:

- `aeat.application.live._censo` — `CensoSnapshot` model with
  content-addressed `snapshot_id`, `CensoSnapshotRepository` over
  `SecureObjectRepository`, `CensoSnapshotService` with `capture` /
  `latest_active` / `discard`, plus 14 passing real-behavior tests.
- `aeat.application.live._snapshot_base` — shared
  `SnapshotLifecycleState` enum (ACTIVE / SUPERSEDED / DISCARDED).
- `aeat.adapters.outbound.aeat.sede._censo` — `CensoFactSet` envelope
  + G313 HTML parser refusing on unknown fields.
- `aeat.adapters.outbound.aeat.sede._censo_live` — live G313 page
  read + projection to `CensoFactSet`.
- `aeat.application.user_profile._censo_errors` — `CensoSyncError`
  base + typed subclasses, registered in the central
  application-error registry.
- `aeat.domain.buckets._event.BucketEventType` — `CENSO_REFRESHED`,
  `CENSO_APPLIED`, `CENSO_DEPENDENT_STAMPED_STALE`.
- `aeat.entrypoints.cli._config._profile_censo` — four operator
  verbs (`refresh`, `show`, `compare`, `apply`) routed through
  `_emit_envelope` with typed `Censo*Result` payloads.
- `aeat.locales/{es,en,ca,hu}.yml` — `cli.config.profile.censo.*`
  translation keys across all four target languages.

## Rationale

The Spanish-stem decision is the same one applied to `iva`, `renta`,
`casilla`, `modelo`, and other AEAT-vocabulary concepts. Naming the
implementation in the language of the surface it integrates with
keeps the developer mental model aligned with the AEAT
documentation; an English alias layer would invite drift.

## Consequences

- Plan rows whose Step text reads "census*" close by audit-based
  documentation that the Spanish-named implementation satisfies
  the intent.
- New Modelo 036 work uses Spanish naming directly.
- The handful of stale-refusal and walker-coverage Steps in P05/P07
  remain open until the per-axis stale-refusal wiring is verified
  against the modelo action surface — separate engineering slice.

## Codification candidates

None this pass. The Spanish-naming convention is already documented
implicitly across the codebase's iva/renta/modelo precedents; a
fresh project rule would duplicate that lived convention.
