---
tags:
  - '#reference'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
related:
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-07-06-cross-period-prorrata-plan]]'
  - '[[2026-06-19-silent-zero-base-aggregation-adr]]'
  - '[[2026-06-19-silent-zero-base-aggregation-plan]]'
---

# `cross-period-prorrata` reference: `cross-period-prorrata handover: W01 landed foundation, design decisions, plan roadmap, grounding surprises for the W02+ builder`

Handover for the agent building `cross-period-prorrata` W02 onward. A first team
landed the W01 register foundation and then stood down entirely to avoid a
concurrent-edit collision; this document is the durable handover of what is
already on disk, the design decisions to honour, the plan roadmap, and the
grounding surprises so the continuing builder does not re-derive or conflate.
Consult it before touching the register, the seed, or the aggregation path.

## What is already landed (W01 — build on this, do not rebuild)

Commits `fe92675dcf` (W01.P01 domain) and `e53c630a70` (W01.P02 persistence);
plan `2026-07-06-cross-period-prorrata-plan` at 9/40. What exists:

- Core closed enums, re-exported from `aeat.core`: `ProrrataRegisterRegime`
  (general | especial | ninguna) and `ProrrataProvisionalProvenance`
  (carried_prior_definitiva | aeat_autorizada | inicio_actividad). In
  `src/aeat/core/_prorrata_register.py`.
- Domain register in `src/aeat/domain/prorrata_register/`: `ProrrataRegisterEntry`
  (one per (ejercicio, sector); regime, provisional %+provenance, and the
  settlement/definitive slots present from birth; coupled-field invariants),
  the `ProrrataRegister` aggregate (unique (ejercicio, sector) key), and the
  PURE art-105 precedence-ladder resolver `resolve_provisional_percentage`.
- Encrypted persistence mirroring `src/aeat/adapters/persistence/profile/bienes_inversion.py`:
  `PROFILE_PRORRATA_REGISTER_NAMESPACE` (FINANCIAL, bucket-local, encrypted),
  `ProrrataRegisterRepository`, and a `ProrrataRegisterService` facade. Covered
  by a strict save/load/equality roundtrip plus an anti-tautology corrupt-payload
  proof (real key provider + real SQLite), both of which bite.

## Design decisions to honour (breaking these re-opens closed questions)

- `ProrrataRegisterRegime` is DELIBERATELY DISTINCT from the substrate enum
  `ProrrataRegime` in `src/aeat/domain/iva/_prorrata.py`. Do NOT reuse or extend
  the substrate enum: `validate_prorrata_reference` parses `ProrrataRegime(parts[3])`,
  so adding a `ninguna`/`none` member there would loosen a test-covered reference
  grammar the ADR forbids reopening ("substrate consumed, not re-opened"). The
  register's own regime carries the `ninguna` member for the genuine no-prorrata
  case.
- The precedence ladder is the SINGLE home for provenance resolution: authorised
  (105.Dos) / inicio (105.Tres) over carried (105.Uno) over None. There is NEVER
  a fabricated default percentage — absence resolves to a VISIBLE unresolved
  state, which is what feeds the W05 fail-closed-to-visible resolution. Do not
  reintroduce a silent 100% default anywhere.
- Per-taxpayer facts (the register) persist ONLY in the encrypted bucket-scoped
  substrate. No plaintext side store, no temp file.

## The plan roadmap (L3, 6 waves / 40 steps)

- W01 Register foundation — DONE (above).
- W02 Provisional seed — P03: seed the carried prior definitiva by resolving the
  prior settlement revision via `select_revision(303, ejercicio-1, settlement)`
  (law-determined; never inject a stored revision id as the selector), reading
  the prior `iva.prorrata-porcentaje` observation, and re-confirming its stamped
  revision — DIVERGENCE BLOCKS, MISSING stamp ADVISES. P04: the 105.Dos and
  105.Tres provenance overrides feed the register through the single precedence
  ladder, with an observation cross-check (blocking contradiction vs
  informational regulated-difference notice).
- W03 In-year apportionment — the provisional % apportions deducible CUOTAS (not
  bases) inside the ONE shared ledger IVA aggregation resolver; a byte-identical
  regression for non-prorrata taxpayers, a field-flows "bites" test for a prorrata
  taxpayer, and a pull==calculate parity regression.
- W04 Settlement + oracle + promotion — casilla 44 and M390 fed from
  `compute_regularizacion_prorrata_anual` over operator-DECLARED annual volumes
  (that authority is unchanged); the ledger annual rollup is a divergence
  ADVISORY only (it cannot classify every art-104.Tres exclusion); the definitiva
  is written back to seed year+1. `PRORRATA_REGULARIZACION` promotes out of the
  deferred set ONLY after an end-to-end test proves it against a BUNDLED AEAT
  Manual práctico oracle (no tautological calculation tests).
- W05 Silent-zero-base resolution — applicability fail-closed-to-visible, a
  per-period missing-carry advisory, and a settlement verify advisory finding so
  the gate never grants verified-complete with zero findings on an under-declared
  base. This is the concrete close of the deferred silent-zero-base rows.
- W06 Deferred axes — schema slots from birth for prorrata especial / the +10%
  gate / sectores diferenciados / art-104.Tres special denominator / art-105.Cinco,
  each an honest deferred step, plus an independent close honesty review.

## Grounding surprises (consume, do not rebuild; do not conflate)

- The settlement advisory scaffold ALREADY EXISTS:
  `src/aeat/application/calculations/_prorrata_regularizacion.py`
  (`build_prorrata_regularizacion_advisory`, a pure function over the two
  percentages and the deductible IVA) and
  `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py` (which
  already scans the prior-year-definitiva observation). W04 CONSUMES these — do
  not rebuild them.
- The compute half is stable: `src/aeat/domain/iva/_prorrata.py`
  (`compute_prorrata_definitiva_anual`, `compute_regularizacion_prorrata_anual`,
  the art-106 especial classification). CONSUME it — do not re-open it.
- DO NOT CONFLATE: the IVA ledger's `_resolve_iva_prorrata_attachment` /
  `ProrrataLedgerReference` (per-transaction SOPORTADO tagging in
  `src/aeat/application/aggregation/_iva_ledger.py`) is a DIFFERENT concept —
  groundwork for the deferred especial per-input classification (W06). The
  register-% apportionment (W03) is a separate mechanism: a percentage applied to
  the deducible-cuota sum. Leave the per-tx tagging alone.
- `src/aeat/application/aggregation/_prorrata.py` does NOT exist at HEAD — the
  aggregation orchestrator is genuinely net-new.

## Constraining rules (the ADR's binding disciplines)

- carried-observations-stamp-their-revision: the cross-period carry re-confirms
  the stamp; DIVERGENCE BLOCKS, MISSING advises. Reusing
  `CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE` for the block is the
  canonical, tighter path (the concurrent S10/S11 already does this — good).
- revision-resolution-is-law-determined: resolve the prior revision via
  `select_revision`; a stored revision id may only be asserted-equal, never
  injected as the selector.
- one-aggregation-path-pull-equals-calculate: the in-year apportionment goes in
  the ONE shared resolver; a pull==calculate parity regression guards it.
- no-silent-under-declaration and no-dormant-source-resolvers: the deferred
  `PRORRATA_REGULARIZACION` source ADVISES while deferred; its promotion co-lands
  with enrollment and the oracle proof.
- aeat-roundtrip-discipline: every persistence boundary (the register) carries a
  strict roundtrip plus an anti-tautology proof.
- no-tautological-calculation-tests: the regularización figure must be proven
  against a bundled AEAT Manual oracle, never hand-computed from the same formula.

## Coordination state at handover

The W01 team stood down entirely on W02+ with ZERO working-tree footprint (no
`_seed.py` content, the `application.calculations` facade clean at HEAD, nothing
staged) so as not to collide with the concurrent builder that landed S10
(`157b0360b3`) and staged S11. The concurrent S10/S11 design (a frozen dataclass
`ProrrataSeedFinding` / `evaluate_carried_prior_definitiva_seed` plus the
`CrossPeriodCleanStateBlocker` divergence block) is rule-aligned; the W01 team's
alternative (a pydantic result reusing a `revision_carry_outcome` gate) was
equivalent — only ONE owner should hold `_seed.py`. The W01 register foundation
is the shared base both designs build on and it stands unchanged.
