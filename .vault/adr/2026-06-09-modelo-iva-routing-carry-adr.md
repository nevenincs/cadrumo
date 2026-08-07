---
tags:
  - '#adr'
  - '#modelo-iva-routing-carry'
date: '2026-06-09'
modified: '2026-08-07'
body_hash: 'sha256:b5a4cb26930cea8d9754c0240931660985fab40aef95efa5a12d986f1d4b61ec'
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

## Status

Accepted and in force. The IVA routing + cross-period carry-enrollment + `app_filing`
non-official-evidence decisions in this ADR stand and align to the canonical direction
in the PHASE ADRs (not a central apex doc): source-kind under the phase-2.1
`binding-source-kind-taxonomy-unification` ADR; the carry mechanism under the
foundational `live-iva-compensation-wallet-adr` anchor + the future phase-2.3 ADR.

## 2026-08-07 amendment — Tier 2 AIC official-box parity is a re-route, not an addition

Tier 2 above defers "AIC official-box parity" without saying which official box
parity means. A tax review has settled it, and the answer changes what the shipped
Modelo 390 binding does rather than only adding a breakdown beneath it.

**Ruling: intra-community acquisitions do not belong on the inversión-del-sujeto-pasivo
line.** Modelo 390's `modelo-390-iva-autorepercutido-intracomunitaria-cuota` selects
`intra_community_acquisition_reverse_charge` and
`intra_community_service_acquisition_reverse_charge`; its export field sits in record
`modelo-390-page-02` at offset 1492, which the bundled 2024 and 2025 designs both
identify as box 28, "IVA deveng. invers. sujeto pasivo - Cuota". The two dedicated
seven-rate AIC ladders published immediately before it, fourteen bienes boxes and
fourteen servicios boxes, stay blank. The money total is right and the line is wrong.

Three confirmations, ascending in strength.

- **Legal structure.** LIVA art. 13.1 makes adquisiciones intracomunitarias de bienes a
  hecho imponible in its own right, while art. 84 governs entregas de bienes and
  prestaciones de servicios, its Uno.2 being the inversión rule. The bundled
  `ley-37-1992-art-84.html` carries the BOE block structure past its own end and shows
  the following block opening Capítulo II, adquisiciones intracomunitarias de bienes, at
  art. 85. LIVA places the AIC taxable-person rule in a different chapter from the
  inversión rule.
- **AEAT's own taxonomy, inside this modelo.** The Régimen Simplificado page of Modelo
  390 carries box 76, IVA devengado en adquisiciones intracomunitarias, and box 77, IVA
  devengado por inversión del sujeto pasivo, as two separate boxes. AEAT states the
  distinction rather than leaving it to be inferred from how many boxes exist.
- **The app already does it correctly on Modelo 303, which is decisive because it is an
  internal contradiction rather than a competing reading of the law.**
  `modelo-303-dr303-11-projection` targets official box 11 from
  `iva.autorepercutido.intracomunitaria.devengado`, while a separate
  `modelo-303-dr303-13-projection` targets box 13 from
  `iva.autorepercutido.interior.devengado`. For the identical two ledger categories,
  Modelo 303 files on the AIC line and reserves the inversión line for domestic
  inversión, while Modelo 390 files both on the inversión line. Modelo 390 reconciles its
  annual devengada against the summed quarters, so the two surfaces disagree about where
  the same money belongs. Both readings cannot be right in one codebase.

**This amendment corrects the Considerations inventory above.** That list names eight
LIVA articles absent from the catalogue and corpus, and art. 85 is not among them. Art.
85 establishes the taxable person for adquisiciones intracomunitarias and is therefore
the binding provision any re-routed AIC binding must cite. It is absent from both the
bundled corpus and the legal catalogue, so the gate that Tier 2 already imposes now
covers nine articles, not eight. The re-route must not ship before art. 85 lands with
real BOE text and a `required_text` cross-check, per the grounding constraint above.

**Two residues recorded here are cross-modelo, not Modelo 390 problems.** Both were
first measured on Modelo 390 and both are equally true of Modelo 303, so an
implementation scoped to the half that was measured would leave the other half live.
First, the AIC base imponible reaches no official box on either return: Modelo 390's box
27 is neither declared nor exported, and Modelo 303's box 10 has no projection formula.
Second, the AIC binding's `rate_kinds` omits `zero` on both, so a 0%-rate
intra-community acquisition reaches nothing even on the line it currently occupies. The
`zero` widening is independently fixable but must carry its own mutation proof, because
widening a selector alone can silently change what an existing box declares.

**The implementing shape already exists in this registry.** Modelo 303 reaches its
official boxes through projection formulas targeting the official box id, not through
casilla `number` declarations; the three projections named above are the pattern to
copy rather than re-derive. Keep the existing rate-blind total casilla as a sibling
layer so rate-unrecorded AIC rows still reach a casilla, since narrowing to per-rate
boxes without a blind sibling has been measured to collapse a total.

**One measurement constraint for the implementer.** A byte offset does not identify a
box. Offset 1492 matches box 28 on page 2 and box 215 on page 3 of the same design, so
the identification holds only when keyed by record as well as offset. This extends the
existing caution that offset-to-box is undefined across a revision's span: it is equally
undefined across pages within one design, and an offset-only claim produces no
impossible output to catch it by inspection.

This amendment rules on code and is not self-executing. The corpus work and the
re-route are tracked as separate open rows, the re-route blocked by the corpus work, so
that the record being correct is not mistaken for the tree being correct.
