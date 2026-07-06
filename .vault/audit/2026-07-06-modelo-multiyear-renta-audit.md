---
tags:
  - '#audit'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
  - "[[2026-06-02-modelo-multiyear-renta-W01-P03-S09]]"
  - "[[2026-06-02-modelo-multiyear-renta-W01-P03-S10]]"
---

# `modelo-multiyear-renta` audit: `Modelo 145 fleet drift review`

## Scope

Reviewed the W01.P03 authorization fleet drift fix after Modelo 145 became a loadable
registry-backed local payer communication. The review checked the central `Modelo` enum,
the authorization fleet denominator ratchet, overview obligation out-of-scope
classification, and the S09/S10 plan/exec evidence.

## Findings

### w06-w07-edge-review | medium | M720 advisory work does not close previous-filing binding rows

The W06/W07 edge review found that the new M720/M721 foreign-asset helper is advisory-layer code over caller-supplied prior and current observations. It does not exercise a registry `previous_filing` binding path for M720, so W07.P29.S81 through W07.P29.S83 must remain open until that binding/resolver path exists. The M720 test wording was tightened to state this limitation explicitly.

### w06-w07-edge-review | medium | M714 art.31 evidence is relation-backed calculation wiring, not independent oracle replay

The W06/W07 edge review found that the M714 art.31 tests prove real registry relation resolution and formula wiring across two renta years, but do not replay an independent AEAT worked example. The M714 closure evidence should therefore be described as relation-backed calculation evidence for the bounded 2021-2025 window, with art.31 exclusion slices still manual where M100 lacks filing-grade breakdowns.

### modelo-145-fleet-drift | low | no blocking findings

The independent reviewer found no blocking issues. Adding `Modelo.M145 = "145"` repairs
the real source of drift because `CANONICAL_MODELO_FLEET` is derived from `Modelo` minus
`NON_REGISTRY_MODELOS`, not from an access-gate-local allowlist. Classifying Modelo 145 in
`OUT_OF_SCOPE_OBLIGATIONS` only affects the overview obligation calendar; it does not hide
145 from the authorization fleet.

Residual risks are acceptable and intentional: the `73` denominator remains a hard ratchet
that must be intentionally updated when the registry-backed fleet changes, and Modelo 145
is covered by the fleet-wide default-deny loop rather than a named M145-only assertion. The
live-registry coverage test and core enum/registry parity gate make both residuals
non-silent.

## Recommendations

Keep future fleet changes routed through the central `Modelo` enum and the registry parity
tests. Do not patch `CANONICAL_MODELO_FLEET` locally in `core/access_gate`; that would
reintroduce the drift this fix removed.
