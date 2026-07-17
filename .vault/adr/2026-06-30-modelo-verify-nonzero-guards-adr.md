---
tags:
  - '#adr'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-research]]"
  - "[[2026-06-02-modelo-200-base-determination-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
---

# `modelo-verify-nonzero-guards` adr: `Close silent-under-declaration gaps on unguarded manual-base self-assessment modelos` | (**status:** `accepted`)

## Problem Statement

`no-silent-under-declaration` requires every modelo verify gate to surface at least an ADVISORY finding when a positive economic input resolves to a zero dependent base/cuota with no offsetting reduction declared — closing the defect class the M200 base-determination work (`2026-06-02-modelo-200-base-determination-adr`) first documented. That work closed the gap for M200 (two ADVISORY `implies_nonzero` guards) and M131 (one ADVISORY guard). A registry sweep for this research confirms the same `verification_predicates` Layer-2 protection is entirely absent from four further self-assessment modelos whose headline liability is computed from a manual or partially-manual base, and is incomplete on a fifth (M210, which guards only fiscal-representative designation, not base-imponible under-declaration):

- **M202** (IS pago fraccionado) — base chain rooted in a manual `resultado contable` casilla, no guard.
- **M123** (retenciones capital mobiliario) — base/retención chain entirely manual leaves, no guard.
- **M151** (IRPF impatriados) — manual base-liquidable, no guard.
- **M714** (Patrimonio) — the least-modelled of the five; sequential manual casillas with no formula linkage, no guard.
- **M210** (IRNR) — has one BLOCKING_RULE guard (representante fiscal) but no guard on the base-imponible chain itself.

The `aeat` CLI workflow these gates sit behind is the surface an autonomous LLM tax-advisor agent drives end to end (`2026-07-02-agent-harness-refoundation-adr`); an unguarded silent zero on these modelos is reachable by that agent with no human-legible signal.

## Considerations

- **The predicate DSL already supports this shape.** `implies_nonzero(["antecedent_id","consequent_id"])` is a shipped, validated operator (`KNOWN_VERIFICATION_PREDICATE_OPERATORS`, `src/cadrumo/domain/calculations/registry/_schema.py:1011-1043`); no schema change is required for M202, M123, M151, M714, or the M210 general/UE-branch guard.
- **No construct/binding coverage sweep applies.** `verification_predicates` is a revision-scoped array with no `ConstructDefinition` membership requirement (`_schema.py:643-665`); registry-build validation (`_validate_surfaces.py:196-249`) checks only legal_refs resolution, casilla id existence, and operator-name validity. Each addition is a clean, isolated registry-authoring change.
- **Legal grounding pre-exists for every recommended guard.** Five binding provisions (`ley-27-2014:art-40-3`/`art-40`, `rd-439-2007:art-90`, `ley-35-2006:art-93`, `ley-19-1991:art-30`, `trlirnr-rdleg-5-2004:art-24`) are already authored in the legal catalogue with `corpus_ref` pointing at bundled, reviewed BOE text (`review_status = "reviewed"`, dated 2026-05-05 through 2026-06-02) — no new legal-catalogue authoring is required, per `registry-calculation-legal-grounding` and `legal-grounding-verifies-bundled-authoritative-corpus`.
- **Two structurally different risk shapes exist.** M202, M151, and the M210 general-branch guards are "formula-defended" (the consequent is already formula-derived from the antecedent, so the guard is declarative/defensive, mirroring M131's `01→02`), where a registry regression — not an operator omission — is the realistic trigger. M714 is "operator-skippable" (sequential manual casillas, no formula linkage), the closer analogue to M200's pre-ADR `00500→00501` gap and the most analogous case for a future Phase-2 derivation effort.
- **M714 carries the highest unguarded-edge density but the lowest guard confidence.** The mínimo exento and límite-conjunto mechanics make two of its three candidate edges high-false-positive risk; only the `cuota-integra → total-cuota-integra` edge is safe to guard without further tax-expert review.
- **M210's highest-value edge is not expressible in the current DSL.** The inmobiliaria branch's silent-zero risk (the most common M210 filing scenario) is gated on a categorical casilla condition (`tipo_renta`), and no shipped operator supports a categorical-equality antecedent. Closing it requires a DSL extension, out of scope for a registry-authoring-only ADR.

## Constraints

- **M202 is the priority and is sequenced first.** Its higher filing volume (every SL/SA files M202 three times a year) and highest-risk framing make it the lead Step; M123, M151, M714, and the M210 addition follow.
- **ADVISORY only, no BLOCKING_RULE.** Every recommended guard carries `finding_kind = "ADVISORY"`. A BLOCKING guard on any of these edges would refuse legitimate zero-consequent filings this research could not fully rule out (losses, full corrections, EU/EEE expense offsets, no relevant activity in that lane) — the same reasoning M200's ADR applied.
- **Three M202 revisions need the guard, but only one was fully re-verified.** `2025-y-siguientes` was read end to end; `2019-2022` and `2023-2024` were confirmed structurally identical by file-naming/numbering only. The plan phase must re-confirm formula text verbatim for the two older revisions before authoring identical predicates across all three — or scope the first landing to `2025-y-siguientes` and follow up.
- **M714's two riskier edges and M210's inmobiliaria-branch edge are explicitly deferred**, not silently dropped — each is recorded with its blocking reason (false-positive risk for M714; missing DSL operator for M210).
- **No implementation in this feature.** This ADR records the decision; a `vaultspec-write` plan is the next, separate artifact.

## Implementation

Five Steps (M202 first), each a pure registry-authoring addition plus a two-tier test (registry-shape + gate-behaviour, per the no-tautological-calculation-tests discipline):

1. **M202** — author `implies_nonzero(["04", "13"])`, ADVISORY, predicate_id e.g. `modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo`, `legal_refs = ["ley-27-2014:art-40-3", "ley-27-2014:art-40"]`, landed as a new `verification_expectations/0002-verification_predicates.toml` fragment (the existing `0001-...-cuota-chain-verification.toml` workbook-parity file is untouched) across `2025-y-siguientes` at minimum, with `2019-2022`/`2023-2024` pending the formula-text re-confirmation above.
2. **M123** — author `implies_nonzero(["06", "09"])`, ADVISORY, `legal_refs = ["rd-439-2007:art-90", "ley-35-2006:art-101"]`, new `verification_expectations/0001-verification_predicates.toml` under `2024-y-siguientes` only (`2019-2023` has no calc chain to guard).
3. **M151** — author `implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"])`, ADVISORY, `legal_refs = ["ley-35-2006:art-93"]`, new `verification_expectations/0001-verification_predicates.toml` under `2015-y-siguientes`.
4. **M714** — author `implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"])`, ADVISORY, `legal_refs = ["ley-19-1991:art-30"]`, new `verification_expectations/0001-verification_predicates.toml` under `2021-y-siguientes`. The `base-imponible→base-liquidable` and `total-cuota-integra→cuota-a-ingresar` edges are explicitly NOT authored in this Step; recorded as follow-up requiring tax-expert review.
5. **M210** — append `implies_nonzero(["rendimientos_integros", "base_imponible"])`, ADVISORY, `legal_refs = ["trlirnr-rdleg-5-2004:art-24"]`, to the EXISTING `verification_expectations/0001-verification_predicates.toml` under `2025` (alongside the existing representante-fiscal predicate; no new file). The inmobiliaria-branch edge is NOT addressed — recorded as a precondition for a future DSL-extension feature.

## Rationale

Every recommended guard reuses the shipped `implies_nonzero` operator against casilla ids and legal grounding that already exist in the registry at HEAD — the cheapest, lowest-risk way to close the silent-under-declaration class on these five modelos, matching the M200/M131 precedent exactly. ADVISORY severity is chosen uniformly because none of the five chains were confirmed free of legitimate zero-consequent cases under this research's time bound; a BLOCKING guard demands a stronger "no legitimate zero" proof than was available for any of them (M131's `01→02` is the closest to that bar and even it stays ADVISORY). The two genuinely uncertain findings — M714's two riskier edges and M210's inmobiliaria branch — are deliberately scoped OUT rather than guessed at, consistent with the research mandate to flag rather than invent.

## Consequences

- **Gains.** Five new operator-facing advisories close real silent-zero exposure on M202 (highest filing volume), M123, M151, M714, and M210's general/UE branch, at near-zero implementation risk (pure TOML authoring against existing legal grounding, no schema or evaluator change). An autonomous agent driving `prepare → calculate → verify` on any of these modelos now receives an explicit signal instead of a silent `finding_count = 0` grant.
- **Difficulties.** M202's older two revisions need formula-text re-confirmation before the guard lands there; M714's two riskier edges and M210's highest-value edge remain open (tax-expert review for M714; a DSL extension for M210).
- **Pitfalls avoided.** A rushed BLOCKING guard on any of these edges would red legitimate zero-consequent filings (M714's mínimo-exento-driven zero base-liquidable is the clearest example) — this ADR stays ADVISORY everywhere and explicitly declines to guard the two M714 edges and the M210 inmobiliaria edge rather than authoring a falsely-confident predicate.
- **Neutral.** M210's representante-fiscal predicate is untouched; the new predicate is appended to the same file ("ADDED predicate, not a new file").

## Codification candidates

- None proposed beyond the existing `no-silent-under-declaration` rule, which this ADR's Implementation directly extends as worked examples five and six (M202/M123/M151/M714/M210) alongside M200 and M131.
