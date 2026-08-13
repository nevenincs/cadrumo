---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:0282b80fab74ffa353809d0bc3f1d21362c30cc958922380ff91ad90471bc365'
step_id: 'S34'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Reconcile two honest counts of the tolerance inventory, then measure whether the one-cent tolerance is ONE comparison primitive or several, and only then judge each site. Two independent measurements disagree - lead-live-sync counted ELEVEN and gatekeeper counted EIGHT partitioned registry-side from application-side. The direction of that difference is now known and must not be mis-stated again - the ELEVEN is the WIDER set, taken by a tree-wide search of production Python excluding tests for tolerance-named assignments and parameter defaults carrying a money value, and the verification-expectation surface where the min-strictest folding lives is a SMALL PART of it rather than a separate population. Exact membership of the eleven so nobody re-derives it - application/aggregation/_retencion_rate_advisory.py:189, application/aggregation/_retenciones.py:380, application/aggregation/_oss_ioss.py:123, application/modelo/_verification_predicates.py:192, application/modelo/_reconcile_casilla.py:98 now fixed, application/ledger/_evidence_advisory.py:53, domain/calculations/registry/_withholding_bindings.py:494, domain/calculations/registry/_invoice_bindings.py:734, domain/invoices/_service.py:37, and domain/invoices/_models.py at 68 and 70. Deliberately EXCLUDED from that count and correctly so - the float layout tolerances in adapters/inbound/declaracion/_parser.py are geometry rather than money, domain/transactions/_llm.py:177 is a confidence-sum epsilon rather than money, and registry schema tolerance FIELDS together with all registry TOML values are data declarations that constitute the authority rather than instances of the defect. The likely site of the gap is that if gatekeeper classes the four domain/invoices and domain/calculations/registry binding sites as registry-side, that alone is most of the difference and BOTH counts are correct over their own stated scope. EVIDENCE ON THE COMPUTATIONAL-VERSUS-REGULATORY QUESTION, measured by lead-live-sync and landed at f907b137f4 - the registry publishes tolerance per verification expectation and folds it min-strictest, and the bundled values VARY by modelo, with 303 folding to exact equality, 720 and 184 and 190 to 0.00, and 131 and 117 and 123 and 187 and 188 and 714 to 0.01. That demonstrates ONE of the eleven, the reconcile comparison, was shadowing a varying registry-published regulatory value. It does NOT settle the question for the other ten, which were not tested for that property, and several plainly lack it - invoice line arithmetic and OSS and IOSS reconstruction are internal consistency checks against the application's own derivation with no AEAT-published threshold to shadow, so cent-slack is very likely the correct reading for some of them. Record this as cutting against a blanket computational reading, never as settling it. Second, three parity suites for modelo 349 operador totals and modelo 193 retenciones totals and modelo 190 withholding totals each assert a one-cent boundary against what each calls the comparison primitive, and whether that names one shared primitive or three parallel ones is unmeasured. Third, judge each site individually. Mechanically collapsing them onto one shared constant is FORBIDDEN, because a site whose one cent is a pure arithmetic rounding guard is correct with a local literal while a site shadowing a registry-published regulatory parameter must read the authority instead, and those remedies are opposite so a uniform sweep gets one of them wrong by construction. Treat the eleven as INVENTORY and not as a duplication cluster, because no substitutability filter has been run across them. Gate - the two counts are reconciled against their stated scopes, the primitive count is measured, each site carries a per-site verdict of rounding-guard or authority-shadowing, and every remedy follows from its own site's verdict

## Scope

- `src/cadrumo/application/aggregation`
- `src/cadrumo/application/ledger`
- `src/cadrumo/application/modelo`
- `src/cadrumo/domain/calculations/registry`
- `src/cadrumo/domain/invoices`

## Description

- Reconciled the two counts against their stated scopes. The eleven is the
  wider tree-wide sweep; removing the four `domain/invoices` and
  `domain/calculations/registry`-binding sites the row already flagged as the
  likely classification boundary (the two `domain/invoices` sites, the
  withholding-bindings site, the invoice-bindings site) leaves a set close to
  gatekeeper's eight. Both counts are legitimate over their own stated scope;
  this is a classification-boundary difference, not a duplication needing one
  true number.
- Read every one of the eleven sites (the row's own line numbers were stale
  for several, as with the sibling rows this session; each was re-found by
  name) and recorded a per-site verdict:
  - `_retencion_rate_advisory.py` (`_conforms_to_fixed_rate`),
    `_oss_ioss.py` (`validate_oss_ioss_observation`),
    `_verification_predicates.py` (`_roll_forward_balance_reconciles`), and
    the three invoice-internal checks in `domain/invoices/_models.py`
    (subtotal / iva_amount / retention_amount): ROUNDING-GUARD. All six
    import the shared `core.money.CENT` constant rather than a locally
    duplicated literal, comparing the application's own single-rounding
    arithmetic against itself. No registry authority applies; correct
    as-is, no change.
  - `domain/invoices/_service.py` (`_DEFAULT_AMOUNT_TOLERANCE`): a distinct
    third category the row's rounding-guard/authority-shadowing binary does
    not name -- a link-suggestion MATCHING HEURISTIC, not an arithmetic
    invariant, already carrying an explicit comment against folding it onto
    `CENT`. No registry authority applies here either; correct as-is.
  - `application/ledger/_evidence_advisory.py` (`printed_iva_advisory`):
    compares OCR-extracted printed text against a derived figure with no
    modelo/revision/snapshot in scope at all -- there is no registry
    authority this could shadow. Correct as-is.
  - `_reconcile_casilla.py` (`detect_casilla_divergences`): AUTHORITY-
    SHADOWING, already fixed in an earlier session; confirmed its one
    production caller resolves and passes `policy.tolerance` from a real
    registry snapshot.
  - `_retenciones.py` (`compute_retenciones_totals_parity`, M193/M180),
    `_withholding_bindings.py` (`compute_withholding_totals_parity`, M190),
    and `_invoice_bindings.py` (`compute_modelo_349_operador_totals_parity`,
    M349): AUTHORITY-SHADOWING. All three are the "three parity suites"
    the row names, and all three share an IDENTICAL shape (a
    `*TotalsParity` pydantic model plus a `compute_*_totals_parity`
    function defaulting `tolerance: Decimal = Decimal("0.01")`) -- this
    measures the row's own open question: they are THREE PARALLEL,
    independently-implemented primitives, not one shared one. Per the
    row's explicit prohibition, they were NOT collapsed into one; each was
    judged and fixed on its own site.
- Measured the actual registry-published tolerance for the modelo each of
  the three parity functions is about, against the LIVE bundled registry:
  Modelo 193 2025 publishes EXACT equality (`0.00`), Modelo 190 2025
  publishes EXACT equality (`0.00`), and Modelo 349 declares NO verification
  expectations at all (`verification_policy()` refuses). The hardcoded
  `0.01` default on all three was therefore WRONG in the exact silent-
  absorption direction this campaign already caught once on modelo 303 --
  it would have silently absorbed a genuine one-cent under-declaration on
  the specific modelo each function's own docstring names.
- Fixed all three: default changed from `Decimal("0.01")` to `Decimal("0")`
  (the established safe fallback across this whole campaign -- exact
  equality when no snapshot is resolved or the revision declares no
  verification expectations), and each docstring corrected from "matches
  the registry's standard rounding tolerance" (false; the value varies by
  modelo) to the same "THE REGISTRY IS THE AUTHORITY... resolve with
  snapshot.verification_policy().tolerance and pass it" wording already
  used at the other fixed comparators.
- DISCOVERED, not part of the row's own text: all three totals-parity
  functions have ZERO production callers -- each is exercised only by its
  own dedicated test file. Recorded below; not wired into any live path in
  this row, which would be a materially larger, riskier change than fixing
  a tolerance default and is not what this row's gate asks for.
- Updated each function's own test file: the existing boundary test (which
  relied on the now-corrected default) was kept but made to pass
  `tolerance=Decimal("0.01")` explicitly, and a NEW test was added per
  function proving the corrected default is exact and a real one-cent gap
  is no longer silently absorbed -- each pinned against the LIVE published
  registry value for its own modelo, not a hardcoded expectation.

## Outcome

COMPLETE against the row's gate. The two counts are reconciled against
their stated scopes; the primitive count is measured (three parallel
totals-parity primitives, not one shared one, and consolidating them is
correctly forbidden); every one of the eleven sites carries a recorded
verdict of rounding-guard, authority-shadowing, or the distinct heuristic-
threshold case the binary framing did not name; and every remedy follows
from its own site's verdict -- three defaults corrected with real,
freshly-measured registry evidence, the rest left untouched because a local
literal is genuinely correct there.

Code: `application/aggregation/_retenciones.py`,
`domain/calculations/registry/_withholding_bindings.py`,
`domain/calculations/registry/_invoice_bindings.py`. Tests:
`application/aggregation/tests/test_modelo_193_retenciones_totals_parity.py`,
`application/calculations/tests/test_modelo_190_withholding_totals_parity.py`,
`domain/calculations/registry/tests/test_modelo_349_operador_totals_parity.py`
(17 total, all green). `ruff check`, `ruff format --check`, `basedpyright`
clean on every touched production file. Regression sweep across the full
`application/aggregation/tests/` package plus the M349 test file: 924
passed, the same 5 pre-existing failures already flagged during `P02.S31`
(confirmed unrelated again -- none of the three touched files appear in any
of their tracebacks).

## Notes

The dormancy finding (three parity primitives with no live caller) is a
genuine gap in operator protection -- an aggregation-vs-summary divergence
on M193, M190, or M349 today produces no finding at all, regardless of this
row's tolerance fix, because nothing calls these functions outside their
own tests. Wiring them into a live verify or calculate path is its own
scoped follow-up, not attempted here: it would touch each modelo's live
calculation/verification surface independently and carries the same
"do not rush a shared-worktree-wide change" caution this campaign has
already applied twice this session (`P02.S16`'s reverted registry migration
and the decision not to touch `validate_relation_source_coordinate_coverage`
under time pressure).

The row's own hardcoded-cent evidence (modelo 303 folding to exact and
absorbing real divergence when a comparator assumed a cent) generalised
exactly as predicted: two of the three parity functions this row fixed were
making the SAME mistake on modelos whose OWN published tolerance is also
exact, not the assumed cent. That is not a coincidence the row anticipated
in general terms -- it PREDICTED the specific defect class and this row
found two more live instances of it.
