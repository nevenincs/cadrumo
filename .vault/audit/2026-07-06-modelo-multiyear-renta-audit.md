---
tags:
  - '#audit'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-08-26'
body_hash: 'sha256:7fa28fecbd13cb927a0e6c6505a8c751ad751f83bd931dbc7d06ad3142805b30'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# `modelo-multiyear-renta` audit: `Modelo 145 fleet drift and post-S89 closeout review`

## Scope

Reviewed the W01.P03 authorization fleet drift fix after Modelo 145 became a loadable
registry-backed local payer communication. The review checked the central `Modelo` enum,
the authorization fleet denominator ratchet, overview obligation out-of-scope
classification, and the S09/S10 plan/exec evidence.

After S89 closed, the same audit file also records the 2026-07-06 post-S89
campaign-close review: the pass rechecked the stale HIGH/MEDIUM findings from the
campaign-close honesty audit, the W06/W07 edge-review notes below, and the final
M721 source-output supersession.

## Findings

### w06-w07-edge-review | closed | M720 previous-filing binding path now exists

The W06/W07 edge review originally found that the M720/M721 foreign-asset helper was
advisory-layer code over caller-supplied prior and current observations and did not
exercise a registry `previous_filing` binding path for M720. That finding is now closed:
commit `8f5442bc0d` added the three strict M720 `previous_filing` copy bindings for
cuentas, valores, and inmuebles, closed W07.P29.S81 through W07.P29.S83 with exec
records, and verified the resolver path with the M720 prior-year baseline tests.

### w06-w07-edge-review | classified | M714 art.31 evidence is relation-backed calculation wiring

The W06/W07 edge review found that the M714 art.31 tests prove real registry relation
resolution and formula wiring across two renta years, but do not replay an independent
AEAT worked example. This remains the correct evidence classification, not a blocker:
the baseline-fidelity test now avoids claiming a Phase-A art.30 calculation oracle, and
the dedicated registry tests own the art.30 escala formula coverage.

### post-s89-closeout | no new high/medium findings

The post-S89 review rechecked the remaining campaign-close honesty findings against
the live tree:

- M353 no longer carries expected-to-fail / held-pending framing.
- The M721 exterior orphan test file is absent; only the `_extranjero_` fidelity
  module remains.
- M309 and M369 both enroll through calculation mode with `record_calculation_year`.
- The A4 income ADR now reflects the delivered M100 `1391 -> 1388` art.48 carry.
- M202's 18% leg reads the live registry parameter and separately checks the
  statutory value.
- M714 wording now separates manual baseline-fidelity inputs from art.30 escala
  registry tests.
- S89 explicitly supersedes, rather than implements, the obsolete M721 scalar
  `source_output` previous-filing binding promise.

No new HIGH or MEDIUM blockers were found.

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

Do not reopen M720 S81-S83 unless a new regression removes the committed
`previous_filing` binding path. Do not reopen the M721 `source_output` promise without a
new row-set previous-filing ADR and schema/resolver plan.
