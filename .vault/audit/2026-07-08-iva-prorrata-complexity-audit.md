---
tags:
  - '#audit'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `iva-prorrata-complexity` audit: `prorrata-especial +10% advisory dormant: live-emit plumbing gap`

## Scope

W02.P03 closeout review flagged that the S13 art-103.Dos.2 +10% mandatory-especial advisory (`build_prorrata_especial_mandatory_advisory`, `application/calculations/_prorrata_regularizacion.py`) is built and unit-tested but NEVER emitted on the live M303 settlement path. This audit records why a live emit is not a simple wire, and the exact plumbing plus ADR-level data gap that a follow-up (plan step W02.P03.S21) must resolve. Honesty gate invoked: an honest "needs X" is recorded rather than forcing a hollow emit.

## Findings

### plus-ten-percent-advisory-dormant | high | built + tested but never emitted on the live settlement path

The `is_especial_mandatory`-driven advisory fires nowhere in production. The live settlement collector `collect_prorrata_regularizacion_diagnostics` (`application/modelo/_prorrata_regularizacion_advisory.py`), called by `collect_bucket_aggregation_advisory_diagnostics` (`application/modelo/_calculation_diagnostics.py`) from `_calculation_actions.py:907`, surfaces the sibling prorrata advisories (missing-provisional, art-105.Cuatro regularización) but not the +10% especial-mandatory one. A built-but-unwired advisory is a dormant advisory (no-silent-under-declaration / no-dormant-source-resolvers).

### plus-ten-percent-needs-dual-regime-annual-reaggregation | high | collector has only one regime's whole-year total

The advisory compares the ejercicio's whole-year deducible IVA cuota total under the GENERAL regime against the total under the ESPECIAL regime. The live path computes only ONE of them: the caller passes `revision.casilla_values` (the year's deducible total under the bucket's DECLARED regime) plus `bucket_id`; it does NOT pass the `IvaLedgerAggregation`, and the aggregation itself apportions under a single regime. Obtaining the OTHER regime's total requires a SECOND full annual ledger re-aggregation under the opposite apportionment (`aggregate_iva_ledger_observations_from_repositories` for the annual period + `resolve_iva_ledger_binding_values` with a general vs especial `IvaLedgerProrrataApportionment`, summing the deducible cuota bindings). That is a new `application/modelo` (light casilla_values collector) → `application/aggregation` re-aggregation dependency the collector does not currently carry — the exact "re-aggregating the raw ledger under especial classification" plumbing the honesty gate names.

### plus-ten-percent-general-filer-audience-uncomputable | high | the art-103.Dos.2 target has no per-input classifications

Art. 103.Dos.2 targets a filer computing under GENERAL prorrata, checking whether especial would deduct >=10% less (making especial mandatory). A general-regime bucket carries NO per-input `input_classification` (declaring it is itself the especial-election workflow, S14). So the especial-regime total is genuinely NOT derivable for the intended audience without the operator first classifying inputs. A live emit could therefore only ever fire CONFIRMATORILY for a bucket ALREADY under especial (validating the election), never nudge the general filer the obligation is designed for — inverting the advisory's purpose. Serving the intended audience needs an ADR-level decision (prompt the operator to classify, or a documented especial-shadow computation), not a wiring step.

## Recommendations

- Track W02.P03.S21 (added, UNCHECKED) as the explicit follow-up. Do NOT force a hollow emit.
- Scope S21 to: (a) a settlement-time helper that computes both regime annual deducible totals (dual re-aggregation), non-blocking `Notice`/`CalculationSourceDiagnostic` with both totals in context, and an anti-dormant live-path test that fires on a real breach and stays silent otherwise; PLUS (b) an ADR-level decision on serving the general-filer audience (no classifications -> no especial total). If (b) is unresolved, S21 can land only the confirmatory-especial slice and must document the general-filer case as still deferred.
- The S13 builder + its four unit tests are correct and land as-is; only the live wiring is deferred.
