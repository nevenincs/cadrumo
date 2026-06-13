---
tags:
  - '#adr'
  - '#modelo-iva-routing-carry'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - "[[2026-06-09-modelo-iva-routing-carry-research]]"
---



# `modelo-iva-routing-carry` adr: `M303 reverse-charge routing, #64 advisory refinement, and cross-period local carry` | (**status:** `accepted`)

## Problem Statement

Two items were deferred from the `cli-ledger-testimonials` campaign and are now explicitly
in scope. A fresh-context verification (recorded in that campaign's P05 audit addendum)
found: (2) Modelo 303 reverse-charge IVA (inversión del sujeto pasivo) generates a cuota
that no binding routes, because the ledger flow classifier never emits
`INVERSION_SUJETO_PASIVO`; and the newly-landed `#64` unconsumed-IVA advisory false-fires
on categories that are cuota-less by law. (3) Automatic cross-period `previous_filing`
carry is not wired into the local file -> calculate flow — `PreviousFilingSourceResolver`
has no production caller and local `file` never persists observations — so an operator
must manually re-enter prior-period values. This ADR records the design and the rulings
needed to close both, and the legal-grounding gate that bounds what may ship now.

## Considerations

The grounding (see the related research) tiers the M303 work by what is legally grounded
in the repo today. Reverse-charge routing under `art-84` is fully grounded (the article,
`rd-1624-1992:art-71`, and `orden-eha-3786-2008:art-1` are all present in the legal
catalogue and corpus). Eight LIVA articles needed for the remaining categories (`art-7`,
`art-13`, `art-15`, `art-17`, `art-20`, `art-22`, `art-25`, `art-26`) are absent from both
the catalogue and the corpus. For the carry, the existing live-capture persistence path
and the cross-period clean-state guard are the load-bearing parents; the design mirrors
them rather than introducing a parallel write path.

## Constraints

- REGISTRY-CALCULATION-LEGAL-GROUNDING: a binding may not cite a LIVA article that is not
  defined in the legal catalogue with a resolvable `corpus_ref` backed by real BOE text.
  The eight missing articles are therefore a hard gate on the Tier-2 routing (box-59/60
  substantive grounding, AIC official-box parity, import-deducible); reverse-charge Tier-1
  is unblocked because `art-84` is already grounded.
- SAFETY / NO-SILENT-UNDER-DECLARATION: the cross-period clean-state guard blocks filing a
  dependent period whose upstream evidence is non-official. Locally-filed observations are
  not official AEAT evidence, so the carry must not be allowed to satisfy that gate.
- ONE-WRITER / NO PARALLEL WRITE PATH: local-file observation persistence must be an
  additional projection of the single-writer filing transition, co-emitted with
  `MODELO_FILED`, not a second write path; the carry resolver must not compete with the
  iva-wallet compensación decision that already owns the M303 compensation binding.
- NO FABRICATION: no regulatory value, casilla routing, or legal_ref may be invented;
  Tier-2 waits on real corpus text.

## Implementation

**M303 reverse-charge (Tier 1).** Make the ledger flow classifier consult the
`IvaCategory` through the existing substrate `derive_flow_for_classification`, so
reverse-charge categories emit `INVERSION_SUJETO_PASIVO`. Add the net-zero
devengado/deducible M303 bindings for `DOMESTIC_REVERSE_CHARGE` (output box 13, deducible
box 37), grounded in `art-84`; the existing autorepercutido-intracomunitaria binding
becomes reachable through the same fix.

**Advisory refinement (Tier 1, ship-now).** Narrow `unsupported_ledger_iva_observations`
to a named, grounded closed set so the `#64` advisory fires only on cuota-bearing unrouted
categories (`DOMESTIC_REVERSE_CHARGE`, `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`,
`IMPORT_THIRD_COUNTRY`) and excludes the cuota-less ones (exempt/zero/not-subject,
exempt intra-community supply, triangulation, simplificado).

**Tier 2 (grounding-gated).** Add the eight missing LIVA articles to the legal catalogue +
corpus with real BOE text and `required_text` citations; only then ship the box-59
(`art-25`) / box-60 (`art-22`) substantive grounding, AIC official-box parity (`art-15`),
and any import-deducible routing (`art-17`).

**Cross-period local carry.** Persist the filed `CalculationRevision.observations` as a
`RegistryModeloObservation` keyed by `(modelo, filing_year, period)` via a new helper
called from the filing transition, co-emitted with `MODELO_FILED`, stamped with a
NON-official `source_kind`. Enroll `PreviousFilingSourceResolver` in the calculate mesh so
its values flow through the existing backend-binding channel; the manual casilla-lift
no-ops when the binding is already resolved and caller `--binding` overrides.

## Rationale

The tiering follows directly from the grounding: shipping reverse-charge routing under the
already-grounded `art-84` closes a real silent gap now, while the registry-grounding rule
forbids the other categories until their corpus lands — so the advisory refinement (which
adds no binding and cites no missing article) is the honest interim, keeping the operator
alert non-silent on the genuinely-dropped cuota and quiet on the legitimately cuota-less.
For the carry, mirroring the live-capture persistence + reusing the single resolver and the
existing precedence chain honours the one-writer and registry-authority disciplines; the
non-official `source_kind` is the single decision that keeps auto-carry from laundering an
unevidenced local chain past the filing gate.

## Consequences

- GAINS: reverse-charge IVA is declared (and surfaced when not), the advisory stops
  crying wolf on exempt operations, and local cross-period carry stops forcing manual
  re-entry — while filing still demands real evidence.
- DIFFICULTIES: Tier-2 requires sourcing and validating eight BOE articles before any of
  their bindings can ship; this is deliberate and gated, not skippable.
- PITFALLS avoided: adding the local `source_kind` to the official set (would silently let
  unevidenced chains file); the carry resolver double-counting the iva-wallet compensación
  binding; reverse-charge bindings citing ungrounded articles.
- PATHWAYS: the carry seam generalises to any future local cross-period dependency; the
  corpus additions unblock entrega-intracomunitaria / export / import modelling beyond M303.

## Codification candidates

- **Rule slug:** `ledger-iva-advisory-only-on-cuota-bearing-categories`.
  **Rule:** The unconsumed-declarable-IVA advisory must fire only on categories that are
  legally expected to produce a cuota; exempt, zero-rated, not-subject, exempt
  intra-community supply, triangulation, and other-regime categories are cuota-less by law
  and must be excluded from the advisory's flagged set.
- **Rule slug:** `local-filed-observations-are-non-official-evidence`.
  **Rule:** Observations persisted by the local `file` flow must carry a non-official
  `source_kind` and must never be added to the official-evidence set that satisfies the
  cross-period clean-state gate; auto-carry may feed calculate/draft but never substitute
  for external filing evidence.
