---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S222 Code Review

## Commit

3c5992db2 -- #222 M303 IVA autoconsumo promotor Art. 9.1.c LISIVA

## Status: APPROVE+FU

No CRITICAL or HIGH blocking issues. Two HIGH gaps (M390 missing,
AUTOCONSUMO_POSSIBLE diagnostic absent) confirmed as open follow-up items.
Two MEDIUM findings (scope drift, locale partial-backfill) noted.

---

## Critical Question Answers

Q1 - M303 bindings authored:
Yes. modelo-303-autoconsumo-promotor-base (input_kind=bound, profile_key
iva.autoconsumo_promotor_base) and modelo-303-autoconsumo-promotor-cuota
(input_kind=computed, formula multiply x 0.21) are present in
0001-casillas.toml and revision.toml. Both are in the
modelo-303-iva-autoliquidacion construct casillas, formulas, and bindings.

Q2 - M390 autoconsumo sum:
Not implemented. M390 exists in the registry but no autoconsumo casilla
or quarterly-aggregation binding was added. The quarterly promotor cuota
does not flow into M390. Follow-up required (GAP-001).

Q3 - AUTOCONSUMO_POSSIBLE diagnostic:
Not implemented. No profile-derived verification finding for
real-estate-developer + high IVA repercutido + inventory growth.
Follow-up required (GAP-002).

Q4 - CLI flag --autoconsumo-promotor-base:
Present on work_calculate in _modelo.py. Parses to Decimal, injects into
binding_values under key modelo-303-autoconsumo-promotor-base.
No explicit modelo=303 guard at CLI level; engine silently ignores unused
binding keys on non-M303 modelos (consistent with the SAL pattern).

Q5 - Wizard parity (#228/#239 family):
No wizard question added for autoconsumo promotor. The work compare-taxation
command (M100 conjunta comparator) is wired as incidental surface completion
but is unrelated to M303 autoconsumo. See DRIFT-001.

Q6 - legal_refs:
Registry authority keys are ley-37-1992:art-9 and ley-37-1992:art-79,
consistent with the project article-level key convention. Sub-paragraph
detail (Art. 9.1.c, Art. 79.4) is carried in the notes field.
ley-37-1992:art-90 is in the cuota casilla legal_refs and construct
legal_refs list. Satisfied.

Q7 - Locale parity es/en/ca/hu:
autoconsumo_promotor_base_help and autoconsumo_promotor_base_not_decimal
present in all four locales with substantive translations.
compare-taxation locale keys present in all four locales.
A pre-existing cli.manual.verify gap partially backfilled in en/es
but missing from ca/hu -- see LOCALE-001.

Q8 - Oracle test 1.4M to 294k:
Present as test_modelo_303_autoconsumo_promotor_art9_oracle_1400k_base_yields_294k_cuota.
Asserts iva.autoconsumo.promotor.cuota == Decimal(294000.00) and
iva.cuota-devengada-total == Decimal(294000.00). External authority:
Art. 90 LISIVA statutory tipo 21%. Not tautological.

Q9 - Anti-tautology:
Present as test_modelo_303_autoconsumo_promotor_cuota_proportional_to_base.
Asserts _run(700000) == 147000.00 (statutory), then
_run(1400000) == 2 * _run(700000). If the formula constant changed from
0.21 the ratio assertion catches it. Quality gate satisfied.

---

## Safety Domain (G1-G6)

G1: No os.environ or os.getenv introduced.
G2: Profile schema field autoconsumo_promotor_base declared type=money,
    sensitivity=financial, effective_dated=true. CLI injects as Decimal
    through binding_values: dict[str, Decimal]. Boundary is clean.
G3: All new user-facing strings go through tr(...) with locale keys and
    default fallbacks. Errors use typer.BadParameter.
G4: Locale keys appended inside existing YAML structure at correct depth.
    No structural tree changes.
G5: Binding constant defined once in revision.toml. No alias, shim, or
    re-export layer introduced.
G6: Oracle value from Art. 90 statutory tipo 21%, not from the formula
    under test. Anti-tautology proportionality check across two inputs.

Crash prevention: Decimal() parse wrapped in try/except (InvalidOperation,
ValueError) with BadParameter raise. No unguarded parse paths.
Resource safety: No file handles introduced.
Concurrency: No new synchronisation primitives.

---

## Findings

DRIFT-001 | MEDIUM | work compare-taxation command added out of scope

The work_compare_taxation function (~100 lines) and four locale keys
(compare_taxation_help, compare_taxation_work_unit_not_found,
compare_taxation_error, compare_taxation_recommendation_line) are new in
this commit. The application layer (compare_taxation_for_work_unit,
TaxationComparisonError, WorkCompareTaxationResult) pre-exists. CLI
surface completion wires cleanly to the existing application layer with
no safety concerns. Not scoped in S222.
Recommendation: note in step record; no revert required.

LOCALE-001 | MEDIUM | cli.manual.verify locale keys partially backfilled

Four locale keys (verify_dangling_section_ref,
verify_dangling_rule_section_ref, verify_missing_manifest, verify_failed)
were added to en.yml only. verify_missing_translation was added to
es.yml and en.yml but not ca.yml or hu.yml. Pre-existing domain drift.
Recommendation: raise a dedicated locale-parity cleanup step for
cli.manual.verify in ca/hu.

GAP-001 | HIGH (follow-up, not merge blocker) | M390 not updated

M390 has no quarterly autoconsumo sum aggregation from M303 promotor cuota.
Promotors filing M390 (annual IVA summary) will not have the autoconsumo
cuota in the annual resumen. The M303 calculation is correct and complete.
Must be addressed before the feature is fully closed for annual-filer
compliance.

GAP-002 | HIGH (follow-up, not merge blocker) | AUTOCONSUMO_POSSIBLE diagnostic absent

The profile-derived verification signal for real-estate developer + high IVA
repercutido + inventory growth is not implemented. ~50k affected SLs have
no proactive surfacing of the obligation unless they explicitly pass
--autoconsumo-promotor-base. The CLI flag solves the calculation;
the diagnostic is the discovery mechanism.

---

## Verdict

APPROVE+FU. The M303 autoconsumo promotor pathway is correctly and completely
implemented: bindings, formula, cuota-devengada wiring, CLI flag, profile
schema, legal authorities, locale coverage, oracle test, and anti-tautology
all pass. No safety, crash, or architectural violations found.
Two HIGH follow-up items must be tracked as separate steps:
GAP-001 (M390 quarterly aggregation) and GAP-002 (AUTOCONSUMO_POSSIBLE diagnostic).
