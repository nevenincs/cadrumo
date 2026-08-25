---
tags:
  - '#audit'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:eaf763bf3a89450efbf836dc70d3d90c887fc17a878b12da1e0d5524cb345546'
related: []
---

# `registry-suite-red-at-head` audit: `registry suite red at HEAD: root-cause clustering and filing impact`

## Scope

Diagnosis only, no repair, of the red state of
`src/cadrumo/domain/calculations/registry/tests/` at commit `3241d5a173`. The
question asked was whether the concentration of failures in tax-calculation
modules means the engine computes wrong numbers, and what actually broke, when,
and whether the test or the code is at fault.

Two independent full runs were compared. A prior capture reported 157 failed /
4195 passed / 220.82 s. This audit's re-run reported **160 failed / 4192 passed
/ 238.49 s**, exit 1. The two failure sets were diffed: the 160 is a strict
superset of the 157, with no failure present in the first run and absent from
the second. The three-test delta is `test_loader_cache_isolation.py`
`test_bundled_tree_fingerprint_cache_hit_skips_the_directory_walk`,
`test_export_projection_refs.py`
`test_active_snapshots_materialize_repeated_and_fixed_binding_records[720-2024-0A-type_1-None]`,
and `test_modelo_303_regimen_simplificado_modulos_engine.py`
`test_general_scope_neutralises_internal_regimen_simplificado_formulas[2025]` —
loader-cache and snapshot-cache tests, which is the documented concurrent-I/O
race on this share. The race therefore explains the 3, not the 157. The 157 are
deterministic and reproduced exactly.

Two methodological corrections to the brief are recorded because they change how
the numbers should be read. First, **neither run was sequential.** The project
sets `addopts = "-n auto --dist=loadfile ..."` in `pyproject.toml`, so `pytest`
inherits xdist unless `-n0` is passed explicitly; `-p no:randomly` disables
ordering randomisation only. Both captures carry `[gw5]` worker tags. The
serial recipe is `just test-unit-serial`, which passes `-n0`. Second, **neither
run was against committed HEAD.** The working tree carries 143 modified tracked
files under `src/` (128 of them `.py`) plus 7 modified registry TOML files. Every
file implicated in the clusters below was individually confirmed clean against
HEAD before its cluster was attributed, so the attributions hold, but a
literal "red at committed HEAD" figure would need a clean checkout this shared
worktree cannot safely produce.

The single most important production check was run separately and is reported in
full under the findings: the committed registry tree loads and validates clean.

One conclusion spans every cluster below and belongs here rather than buried in
one of them: **no test expectation was moved to match the engine anywhere in this
suite.** Every failure examined is a gate that stopped agreeing with the code and
was left red, never a gate quietly re-pointed at the code's current answer. The
project's standing prohibition was not violated. This is the "we broke something
and noticed" case rather than the "we broke something and hid it" case, and it is
why the surviving assertions can still be trusted to encode what someone believed
correct at authoring time — including in the one cluster where the assertion
itself turned out to be the stale party.

## Findings

### registry-verify-is-a-false-assurance-surface | high | an operator-facing command reports `Verificado=True` over 157 failures, without disclosing the axes it never checked

`uv run --no-sync aeat app registry verify` exits 0 at HEAD with
`Verificado=True`, 73 modelos, 94 revisiones, 16800 casillas, 1385 fórmulas. This
is the same command CI invokes at `.github/workflows/ci.yml:175`. It is the
decisive production signal and it is green: the registry compiles, every typed-ID
reference resolves, and every per-source binding selector satisfies its selector
model. No committed registry binding fails the tightened IVA selector validation
— the two bindings that appear in failure output as violating
`_IvaLedgerSelector`, `m390-super-reducido-total` and `m303-super-reducido`, exist
only in `src/cadrumo/domain/calculations/registry/tests/test_rate_box_partition.py`
and appear nowhere under `src/cadrumo/_data/registry/`.

What is lost, and this is the finding rather than the aside: the verb does not run
the relation offset-period check, the export-layout population check, or the
published-design span attribution checks that the suite runs. It is not merely a
CI step — it is an **operator-facing verification command**, answering in Spanish,
that a person runs to ask "is my registry sound?". It answers `Verificado=True`
while 157 tests fail, including the M232 revision carrying no export layouts at
all and the M390 record-position and published-design gaps recorded below. The
operator has no way to know which invariant families were never consulted. A
verification surface that reports green over an unchecked axis is worse than one
that reports nothing, because it actively retires the question.

Remediation: extend `aeat app registry verify` to run the relation
offset-derived-period check and the export-layout population check, or have the
verb enumerate in its own output which invariant families it does not cover, so
its green cannot be over-read. Prefer widening it — an operator will not read a
scope disclaimer as loudly as they read `Verificado=True`.

One qualification, recorded with the relation-cluster correction below. On the
relation axis specifically, the verb's silence turned out to be *harmless* —
the defect there was in the check, not the registry, so there was nothing for the
verb to catch. That does not retire this finding, and the reasoning matters: a
verification surface that happens to be right while measuring nothing is not a
working gate. The axes it genuinely does not cover — export-layout population and
published-design span attribution — carry real registry defects that are red in
the suite and invisible to the verb.

### relation-consistency-check-cannot-express-a-two-revision-filing-year | high | VERDICT REVERSED on tracing the runtime — the carry is sound and the check is stale; no filing impact

`src/cadrumo/domain/calculations/registry/tests/test_relation_consistency.py:156`
fails with 12 offences, all on `modelo-303-rel-self-compensacion-anteriores`.
AEAT split ejercicio 2024 into two M303 revisions and the registry followed, in
`4395a2db04 feat(registry): split modelo 303 record design revisions`
(2026-08-10): `2024-hasta-08-y-2t` (accepting 1T, 2T) and `2024-desde-09-y-3t`
(accepting 3T, 4T). Both halves declare the same `previous_period` self-relation
with `source_period_offset_from_target = -1` and
`source_revision_selector.filing_year_delta = 0`, at
`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2024-hasta-08-y-2t/relations/0001-relations.toml`
and its `2024-desde-09-y-3t` sibling.

**CORRECTION.** The first pass of this audit recorded this cluster as a
registry-data defect with direct over-payment risk, on the strength of the test's
own error text. Tracing the runtime path instead of trusting that text reverses
the verdict: **the runtime carry is sound, and the defect is in the consistency
check.** The reversal is recorded in place rather than quietly rewritten, because
the first verdict was relayed onward before it was checked.

Two distinct faults in the check produce the 12 offences, and neither is present
at runtime.

First, the check discards the year. `_derive_offset_source_anchor` at
`src/cadrumo/domain/calculations/registry/_relations.py:344` returns a
`(year_delta, period)` pair, and `apply_period_offset` at
`src/cadrumo/domain/calculations/registry/_period_offset_math.py:28` documents and
computes that delta correctly — 1T with offset -1 yields `(-1, "4T")`. The
period-only wrapper `_derive_offset_source_period` at `_relations.py:339` throws
the delta away, and `test_relation_consistency.py:123` calls that wrapper. So the
check looks for 1T's prior quarter *inside filing year 2024*, and reports
`['4T'] not accepted by 303/2024-hasta-08-y-2t` for a source that legitimately
lives in 2023. Those offences are artifacts.

Second, and more fundamentally, the check's remaining assertion is unsatisfiable
once a filing year carries two revisions. `_relation_consistency_errors` at
`test_relation_consistency.py:51` collects **every** revision matching the
selector — for `filing_year_delta = 0` against 2024 that is both halves — then
`_offset_derived_period_errors` demands that **each individual candidate** accept
**all** derived periods. `2024-hasta-08-y-2t` accepts only {1T, 2T} and
`2024-desde-09-y-3t` only {3T, 4T}, so any relation spanning the year fails
against both by construction. That is what generates the neighbouring-year
offences for 2023, 2025, 2026-y-siguientes and 2009-y-siguientes too. The
assertion encodes an assumption — one filing year, one revision — that the split
retired.

The runtime never makes either mistake. `relation_source_requirements` at
`_relations.py:134` calls the *anchor* helper, keeps `period_year_delta`, and adds
it to the source year at `_relations.py:139`. It then emits a
`RegistryFoldRequirement` keyed by `(source_modelo, source_year, source_periods,
source_casilla_id, ...)` — modelo, year and period, **never a revision id**.
`_gather_observations_for_snapshot` at
`src/cadrumo/application/calculations/_relation_prefill.py:144` iterates those
periods, builds `Period.from_year_and_code(requirement.filing_year, period)` and
pulls the stored observations for that triple. Which revision half produced the
source period is irrelevant to the fetch, and revision resolution stays
law-determined per period exactly as the standing rule requires. The 2T→3T carry
across the split therefore resolves.

Filing impact: **none demonstrated.** The M303 compensación carry — the *cuotas a
compensar de periodos anteriores* a taxpayer rolls forward when a period settles
negative — is not shown to be broken by this failure. This audit no longer claims
an over-payment defect here. What is lost is the check itself: the one gate
watching relation source consistency is now firing on its own stale assumption, so
it would not distinguish a real relation defect from its current noise.

Remediation: fix the check, not the registry. Consume
`_derive_offset_source_anchor` so the year delta is applied, and re-express the
period assertion as a claim over the **union** of the candidate revisions for the
resolved source year, rather than over each candidate independently. Do not
silence it by pinning the current revision set. A separate, genuinely open
question — whether any consumer other than relation prefill pins a single source
revision per fold — is recorded as the follow-up in the companion research
document, along with the M303 2018 unmodelled split, which is a registry-coverage
gap rather than an instance of this check defect.

### maternidad-binding-landed-without-its-registry-layer-harness-sweep | high | 43 M100 failures, one cause, no production consequence

43 failures raise
`RegistryValidationError: binding 'renta-2024-profile-deduccion-maternidad' has no supplied value`
from `src/cadrumo/domain/calculations/registry/_formula_runtime.py:1559`. The
binding fragment
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0067-renta-2024-profile-deduccion-maternidad.toml`
and its formula were added in `a17b3ed7a2 feat(profile): ground required fields
and debit authority` (2026-08-09, 117 files).

This single cause accounts for the brief's largest apparent clusters:
`test_modelo_100_tarifa_real` 16, `test_m100_rental_reduccion_art23_2` 8,
`test_modelo_100_settlement_chain` 6, `test_modelo_100_ahorro_base_chain` 5,
`test_minimo_contribuyente_age_increment` 5, `test_modelo_100_cripto_1812_propagation` 3,
plus singles. They are not 43 independent defects.

Production is unaffected and this was verified rather than assumed. The
application layer injects the fact: `_inject_derived_deduccion_maternidad_facts`
at `src/cadrumo/application/modelo/_profile_binding.py:1066`, called at line 1330
in the profile-resolution path, writes
`renta_family.deduccion_maternidad_{filing_year}` whenever the revision declares a
consumer. For filing year 2024 a childless taxpayer resolves
`ceilings_resolved=True` and `cotizaciones_ceiling_inexpressible=False` at
`_profile_binding.py:412`, so the injector proceeds and writes a real zero rather
than returning early — the settlement chain is not bricked for the majority
population. The failing tests call `calculate_registry_snapshot(...)` directly at
the registry layer, bypassing that injector, and supply hand-built binding values
that never learned about the new binding.

What is lost: the M100 2024 settlement chain — `0587` cuota líquida, `0609` total
pagos a cuenta, `0610` cuota diferencial, `0670` resultado de la declaración — has
no executing registry-layer coverage. The tests are dark, not wrong. **The test
harness is at fault, not the code**, and nobody moved an expectation to match the
engine.

Remediation: sweep the registry-layer M100 harnesses to supply the new binding.
The correct value is the one the production injector computes, not a hand-picked
literal, so the fixture helper should call the same
`compute_deduccion_maternidad_0611` authority rather than hardcoding a number.

### iva-observation-deduction-authority-blinds-the-aeat-worked-examples | high | 37 failures at fixture construction, so the grounded oracles never execute

37 failures raise
`ValidationError: ... input IVA facts require exact deduction authority` from the
`_enforce_exemption_article_category` model validator at
`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:489`. Commit
`173a9a5038 feat(iva): bind deduction fact authority` (2026-08-11) made
`deduction_fact_kind` and `deduction_provenance` mandatory on every input
(soportado / inversión del sujeto pasivo) `IvaLedgerObservation`.

Production was swept. `src/cadrumo/application/aggregation/_iva_ledger.py:651`
and `src/cadrumo/domain/iva/_invoice_classification.py:284` both pass the two
fields through from their candidate. One site,
`src/cadrumo/application/aggregation/_modelo_bindings.py:1619`, passes both as
`None`; that site was carried as an open residual in the first pass of this
audit and has since been closed on evidence — see the dedicated finding below.

This cluster carries the finding that matters most for how the red should be
read. It takes down
`test_m322_2024_grupo_entidades_manual_worked_example` (2),
`test_m353_2024_grupo_entidades_manual_worked_example` (1),
`test_m390_2024_annual_manual_worked_example` (5),
`test_ledger_iva_aggregation_binding_reverse_charge` (9),
`test_modelo_390_base_imponible_bindings` (12) and
`test_modelo_390_aic_isp_routing_split` (6) — the externally-grounded AEAT manual
worked examples the brief correctly identified as the highest-stakes tests. But
they fail at **fixture construction**, before any figure is compared. At
`test_m322_2024_grupo_entidades_manual_worked_example.py:121` the failure is
inside the `IvaLedgerObservation(...)` constructor, reached from `_calculate` at
line 151, never at an assertion.

What is lost: these gates prove nothing right now, in either direction. They do
not show the engine computing wrong tax numbers, and they no longer show it
computing right ones. The honest statement is that the AEAT-grounded oracles for
M322, M353 and M390 are **dark**, and have been since 2026-08-11. No expectation
was altered to match the engine — the standing prohibition was not violated here.

Remediation: sweep the fixture builders to declare the deduction authority the
real projection would carry for each observation. Derive it from the invoice
classification path rather than picking a `deduction_fact_kind` that makes the
test pass, and re-run the worked examples to confirm the figures still reproduce
before declaring this closed — that re-run is the actual proof the engine is
correct, and it has not happened yet.

### declared-category-base-only-null-deduction-authority-is-safe-but-ungated | medium | the one live production question in this audit is CLOSED — no path can reach the refusal, but nothing locks that

This finding closes the single open production risk the first pass of this audit
raised. `src/cadrumo/application/aggregation/_modelo_bindings.py:1619` constructs
an `IvaLedgerObservation` with `deduction_fact_kind=None` and
`deduction_provenance=None`. The refusal at
`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:489` fires when
`flow_direction` is `SOPORTADO` or `INVERSION_SUJETO_PASIVO`, the category is not
`RECARGO_EQUIVALENCIA`, and either authority field is `None`. The question was
whether any caller can drive that combination. **It cannot**, and the guarantee
rests on three independent guards rather than on the reading of one.

The enclosing function is `_declared_category_base_only_observation` at
`_modelo_bindings.py:1561`, and it has exactly one caller, at
`_modelo_bindings.py:1702`. `flow_direction` is not free at that call site: it is
`declared_flow`, resolved at `_modelo_bindings.py:1700` solely by
`_DECLARED_CATEGORY_BASE_ONLY_FLOWS.get(category)`. That table, at
`_modelo_bindings.py:1547`, is closed and holds exactly two entries —
`DOMESTIC_REVERSE_CHARGE` to `OPERACION_CON_INVERSION`, and
`INTRA_COMMUNITY_SERVICE_SUPPLY` to `REPERCUTIDO`. Neither value is in the
refusal's trigger set. The call site additionally gates on
`invoice.kind is InvoiceKind.ISSUED`, so only output-side invoices reach the arm
at all.

The near-miss deserves recording because it is the kind of thing a faster reading
gets wrong: `OPERACION_CON_INVERSION` is *not* `INVERSION_SUJETO_PASIVO`. They are
distinct members of `IvaFlowDirection` at `src/cadrumo/domain/iva/_flow.py:130-133`
— the supplier's side and the recipient's side of the same LIVA art. 84.Uno.2.º
operation. The enum's own docstring records that the fourth member exists because
a supplier's reverse-charge invoice was once routed to
`INVERSION_SUJETO_PASIVO` and self-assessed as though the supplier were the
recipient. Had those two members been collapsed, this site *would* raise in
production.

What is lost: nothing today, but the safety is by construction and **nothing
tests it**. `_DECLARED_CATEGORY_BASE_ONLY_FLOWS` is referenced only inside its own
module — no test in the tree names it. Adding a third entry mapping a category to
`SOPORTADO` or `INVERSION_SUJETO_PASIVO` would be a live production defect at the
next reverse-charge or intra-community projection, and no gate would catch it
before an operator did.

Remediation: add a guard asserting every value of
`_DECLARED_CATEGORY_BASE_ONLY_FLOWS` lies outside the refusal's trigger set, so a
future entry fails at test time rather than at projection time. Gate on the
property, not on the current two-entry membership — pinning the exact pair would
encode a moment and detect nothing.

### iva-ledger-selector-gained-two-required-fields-without-a-fixture-sweep | medium | 16 failures, same shape as the cluster above, no production consequence

16 failures raise `Field required` for `observation_roles` and
`cash_accounting_treatments` on `_IvaLedgerSelector`, declared at
`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:522-523` with
`Field(min_length=1)`. Introduced by `f644d84b32 feat(m303): close DP30301 scalar
authorities` (2026-08-11, 306 files), confirmed by
`git log -S'observation_roles: tuple'`.

Hits `test_rate_box_partition` (9), `test_iva_rate_value_selector` (3),
`test_ledger_iva_aggregation_binding` (3), `test_binding_aggregation` (2). Several
are `pytest.raises` tests asserting a *different* refusal — for example
`test_ledger_iva_aggregation_binding.py:129` expects a match on
`exemption_articles` and now gets the two missing-field errors instead. Committed
registry TOML carries the new fields correctly, which the green
`aeat app registry verify` confirms. Test-harness fault, no filing impact.

Remediation: sweep the selector fixtures; for the `pytest.raises` cases, confirm
the originally-asserted refusal still fires once the fixture is valid, rather than
loosening the match pattern.

### m232-2016-2017-has-no-export-layouts-at-head | medium | 10 failures and every IndexError trace to one empty directory

`src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/export_layouts/`
is empty on disk, and `git ls-tree HEAD` confirms it is empty **at HEAD** — this
is not peer working-tree churn. `test_modelo_232_registry.py` asserts
`revision.export_layouts` is non-empty and gets `()`, then all 8 `IndexError:
tuple index out of range` failures in the run follow from helpers indexing that
empty tuple at `test_modelo_232_registry.py:355` and `:360`.

Unlike the harness clusters this is a genuine registry-data gap: revision
`2016-2017` claims an envelope export layout it does not carry. Filing impact is
bounded — M232 is the *declaración informativa de operaciones vinculadas*, an
informational return, and the affected revision covers filing years 2016-2017,
long closed. No current-year filing produces a wrong number from it. Recorded as
a real defect with low operational urgency.

Remediation: either author the missing envelope header and footer fragments for
`2016-2017`, or, if the revision is genuinely layout-less, remove the empty
directory and narrow the test to the revisions that do declare layouts.

### m390-and-m720-export-layout-and-span-attribution-gaps | medium | 12 structural failures across export offsets and published-design coverage

Several smaller registry-data defects share the export-layout and revision-span
surface, and all trace to the M303 record-design split campaign of 2026-08-10.

`test_modelo_390_box_34_47_disclosure_split.py:97` reports `no field at
modelo-390-page-02:1628` and a companion assertion reports `no fragment under
export_layouts declares 'casilla_id = "iva.anual.total-bases-cuotas-iva"' -- the
gate is stale, diagnose before re-anchoring` — the gate's own message is a warning
against exactly the re-anchoring that would silence it.
`test_revision_span_matches_published_designs.py` (7) reports `2015 is covered by a
bundled design but attributed to nothing` and `2018 should carry two distinct
Modelo 303 designs (AEAT split it mid-course) but 0 distinct payload(s) survived
enumeration`, so 2018 is a second, *unmodelled* AEAT mid-course split beside the
2024 one already handled. `test_layout_design_applies_to_claimed_years.py` reports
`modelo 720 revision '2013-y-siguientes' claims filing year(s) 2012-2012 but its
declared layout design(s) ['aeat-dr-720'] apply only from 2013`.

These are structural and consistency defects with no direct numeric consequence
for a current filing, with one caveat: the 2018 M303 split finding is the same
class of defect as the critical relation finding above, one ejercicio earlier, and
should be triaged with it rather than separately.

Remediation: triage the 2018 M303 split alongside the 2024 relation ADR. Handle
the M720 2012 claim by narrowing the revision's claimed years or declaring the
layout that actually covers 2012. Diagnose the M390 offset 1628 anchor rather than
re-pointing the gate, as the gate's message instructs.

### registry-locales-and-structural-naming-gates | low | 8 remaining failures, no filing impact

The residue does not cluster tightly and carries no numeric consequence.
`test_registry_locales_parity.py:68` fails because
`CasillaDefinition('iva.repercutido.general').get_help("en")` returns `None` — a
missing English help string, to be fixed through the `dev.locales` CLI in all four
catalogues, never by hand-editing the YAML.
`test_registry_reviewability.py` (2) reports validator and workbook-parity modules
grown past their reviewed complexity baselines. `test_export_header_key_naming.py`
(2), `test_casilla_fragment_naming.py` (1), `test_casilla_keying_convention.py` (1)
and `test_fed_alias_beside_starved_box.py` (2) are naming and detector-population
gates. Two of these — `test_the_scan_reaches_a_real_population` and
`test_the_detector_still_resolves_export_ownership` — are anti-vacuity guards
reporting that their own detector no longer reaches a population, which is the
guard working as designed and must not be closed by shrinking the assertion.

The brief's two named known clusters were confirmed present and not
re-litigated: the `Justificante.csv` / `AeatCsv` retyping, and the withdrawn M130
`previous_filing`-to-relation migration.

### ci-is-not-gating-this-suite | critical | the workflow has not completed a run since 2026-08-07 and the queued run has no runner

The suite is red and nothing stopped it reaching main. `Cadrumo CI Full` is
configured at `.github/workflows/ci.yml:29-42` to trigger on `push` to `main`
(with `paths-ignore` for docs and vault trees) and on `workflow_dispatch`, and the
unit job at line 293 runs `CADRUMO_PYTEST_WORKERS=8 just test-unit 50`, which does
cover these tests. Configuration is not the problem; execution is. Every listed
run of that workflow carries `event=workflow_dispatch`, the most recent completed
run is `31177121860` on **2026-08-07** with `conclusion=failure`, and the newest
run `31624887976` (2026-08-12T17:53) has sat at `status=queued` — the jobs are
self-hosted, and a queued run with no runner never reports. Five days of commits,
including all three schema tightenings identified above, landed with no completed
unit lane. Separately, recent failures on other workflows
(`ci-runner-probe-perm.yml`, `Cadrumo Docs Check`, `Cadrumo Agent Harness Eval`)
were merged past.

This is the finding that explains all the others: three unswept schema changes
landed across three days because nothing was executing the gate that would have
caught the first one. The `aeat app registry verify` step stayed green throughout,
which made the red look narrower than it was.

Remediation: restore self-hosted runner capacity or move the unit lane to hosted
runners, then treat a queued-but-never-started run as a hard block rather than a
neutral state. A required check that never reports is indistinguishable from a
passing one at the merge button.

## Recommendations

Sequence the repair by filing risk, not by failure count. The 157 failures are
**nine root causes**, and after the relation-cluster correction recorded above,
**none of them is a demonstrated wrong number on a return.** That is a materially
different conclusion from this audit's first pass and it should be read as the
headline. The strongest honest statement is narrower and less comfortable: the
engine is not shown to compute wrong tax, and — because the AEAT-grounded oracles
for M322, M353 and M390 do not currently execute — it is not shown to compute
right tax either.

The correction also carries a method lesson worth more than any single cluster
here. The first pass read a failing test's error text as a description of the
production defect. It was not: the message described the *check's* model of the
world, which the 2024 revision split had retired. Trace the runtime before
attributing a test failure to the code, especially when the test's message is
articulate enough to sound authoritative.

Fix the relation consistency check rather than the registry: apply the year delta
by consuming the anchor helper, and assert derived periods against the union of
candidate revisions for the resolved source year rather than against each
candidate alone. Do not pin the current revision set to restore green. The M303
2018 unmodelled split is a separate registry-coverage gap and should not be folded
into this repair.

Restore CI execution next, ahead of the harness sweeps. Three unswept schema
tightenings landed in three days because the gate was not running; sweeping them
without restoring the gate leaves the same door open. Treat a permanently queued
required check as a blocking state.

Then sweep the three harness clusters, in this order: the deduction-authority
fixtures first, because they are what un-blinds the AEAT worked examples for M322,
M353 and M390. **The sweep is not the deliverable — the re-run is.** Until those
oracles execute and reproduce their manual figures, this audit's position is that
the engine's IVA grouped-entity and annual-summary figures are *unverified*, not
*correct*. Derive every fixture value from the same production authority the real
path uses, never from a literal chosen to make the test pass, and never move an
expectation to meet the engine.

The one live production question this audit raised is now closed on evidence, not
on belief: `_modelo_bindings.py:1619` cannot reach the deduction-authority
refusal, because its single caller draws `flow_direction` from a closed two-entry
table holding neither trigger value, behind an `InvoiceKind.ISSUED` gate. What
remains is a cheap guard: assert the table's values stay outside the trigger set,
gating on the property rather than pinning the current pair.

Close the registry-data defects (M232 empty export layouts, M390 offset 1628, M720
2012 layout claim, the missing `iva.repercutido.general` English help) on their own
merits, at low urgency. Diagnose the stale detectors rather than re-anchoring
them; two of these gates are anti-vacuity guards whose current failure is the
guard doing its job, and shrinking the assertion to restore green would remove
the only thing telling us the detector has lost its population.

Finally, treat `aeat app registry verify` as a false-assurance surface until it is
either widened or made honest about its own scope. This is not a tooling nicety.
It is an **operator-facing verification command**: it answers in Spanish, reports
`Verificado=True` across 73 modelos, and is the command a person runs to ask "is
my registry sound?". It returns exit 0 while 157 tests fail and while the M303
compensación carry cannot resolve across the 2024 split. An operator has no way to
know the verb never checked relation offsets or export-layout population, so its
green reads as a clean bill of health over a defect that makes them over-pay.
Either extend it to cover those invariant families, or have it enumerate what it
did not check, so its green cannot be over-read. This is also the mechanism by
which the whole red suite came to look like a test-only problem.
