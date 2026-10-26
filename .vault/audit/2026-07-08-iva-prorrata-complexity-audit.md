---
tags:
  - '#audit'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:c56b9767ab3dadfa19c69d685cac8171a76209204251afb19e939a638937deaa'
related: []
---

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

## Campaign-close honesty review (2026-07-08, fresh-context independent)

Triggered per the campaign-close honesty-review discipline before declaring the
20-step campaign structurally complete. The compute, persistence, aggregation, and
grounding layers are genuinely built, corpus-grounded, byte-identical-guarded, and
tested (real work, not a shell). But the two headline axes have no operator ingress.
Clean lenses: fabrication (verbatim corpus grounding, subvenciones-as-non-exclusion,
all `reviewed_by` honestly "operator to re-stamp"), transaction-field roundtrip,
byte-identical preservation, non-tautological verification, cross-step consistency
(sector routing composes with especial; art-104.Tres exclusions act on the annual
volume rollup as a pre-fill proposal, never a filed authority; one aggregation path
preserved). Findings:

### especial-and-sectores-axes-operator-unreachable | high | dormant, was undocumented

The especial (W02) and sectores (W03) apportionment routings fire ONLY from tests.
The sole production register writer is the settlement auto-seed in
`application/modelo/_revision_persistence.py` (`regime = GENERAL if volumen_sin_derecho
> 0 else NINGUNA` — hardcoded, never ESPECIAL, never a sector). An exhaustive non-test
grep of `src/aeat` confirms: no production code assigns `regime = ESPECIAL`, constructs
`SectorDefinition(`, or sets a non-None `sector_id`/`prorrata_sector_id`; no CLI or MCP
entrypoint reaches `ProrrataRegisterService` / `ProrrataRegisterRepository.save` at all.
Consequence on the live path (`_active_prorrata_apportionment`, `_iva_ledger.py`):
`register.is_sectorized` is always False so `_apply_sector_apportionment` is never
reached, and no register entry can be ESPECIAL so `_apply_especial_apportionment` is
never reached. The `--input-classification` flag (S14) is accepted but silently inert
without an especial register entry — a mild no-silent concern (false signal that
art-106 routing applies). The central ADR promises ("mixed trader deducts each input at
its lawful rate"; "each sector at its own %") are operator-unreachable. Remediation:
build the missing operator ingress — (a) an especial-regime election / register-entry
declaration CLI (the prorrata register has NO CLI at all, partly shared with the parent
cross-period-prorrata register), (b) a `SectorDefinition` partition declaration CLI,
(c) a per-row `--sector` tag — each proven by an anti-dormant end-to-end test that the
especial / sector apportionment now fires from the operator flow.

### aeat-oracle-claim-met-by-law-derived-scenario | medium | S15 + S20

Plan Verification and both axis-ADRs mandate an AEAT Manual práctico oracle. Reality:
`test_prorrata_especial_art106_oracle.py` (S15) and `test_sectores_diferenciados_verification.py`
(S20) both state in their docstrings that no bundled AEAT especial/two-sector oracle
ships and use hand-constructed law-derived registers through the production path with a
load-bearing anti-tautology assertion (honest, NOT fabrication — values derive from the
LIVA reglas, not the substrate under test). But S15/S20 are marked [x] as if the
AEAT-oracle criterion was met; the softening lives only in test docstrings.
(S05/art-104.Tres uses the real bundled 56% AEAT oracle; S09/art-105.Cinco's ADR
pre-authorized the hand-constructed alternative — both clean.) Remediation: bundle real
especial + two-sector AEAT oracles, OR amend the plan Verification bullet + the S15/S20
exec notes to state the claim as proven by law-derived-scenario-through-production-path,
so the plan's claim matches what shipped.

### interrupted-marker-encrypted-roundtrip-untested | low

`test_prorrata_register_roundtrip.py::_populated_register` populates carried-settled +
ESPECIAL sector entry + SectorDefinition non-default with corrupt + missing-field proofs
(good), but no `is_interrupted=True` entry — the interrupted marker crosses the encrypted
boundary untested here (covered only at the domain-JSON level). Per aeat-roundtrip-discipline,
add an interrupted entry to the encrypted fixture.

## Disposition (coordinator)

The 20-step compute/persistence/apportionment core is delivered and green (307 prorrata
tests pass -n0). The campaign is NOT declared structurally complete: the HIGH
operator-ingress gap is being CLOSED (a new W04 phase — especial election CLI, sector
declaration CLI, per-row `--sector` tag, with anti-dormant end-to-end proofs), the
MEDIUM oracle-claim reconciliation and the LOW interrupted-roundtrip fixture are folded
into that work, and the S21 +10% live-emit remains the separate ADR-gated follow-up.
