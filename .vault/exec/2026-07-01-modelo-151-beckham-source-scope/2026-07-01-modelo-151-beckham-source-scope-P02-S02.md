---
tags:
  - '#exec'
  - '#modelo-151-beckham-source-scope'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S02'
related:
  - "[[2026-07-01-modelo-151-beckham-source-scope-plan]]"
---

# Ingest the art. 93.2.e.2 savings-band corpus and add the source-scoped base del ahorro and its escala

## Scope

- `src/aeat/_data/corpus/normatives/html`
- `src/aeat/_data/registry/aeat/modelos/151`

## Description

- Ground the art. 93.2.e).2.º escala del ahorro against the already-bundled authoritative consolidated corpus: add legal catalogue entry `ley-35-2006:art-93-ahorro` in `irpf-impatriados.toml`, `corpus_ref` pointing at `corpus/normatives/html/ley-35-2006.html#a93`, with `required_text` transcribed verbatim from the BOE table (the intro clause plus the distinctive cumulative cuotas `44.880` and `71.880`). Verified real against the bundled corpus with the live `verify_legal_reference` gate.
- Model the 2025 Ley 7/2024 amendment as a genuine revision boundary (the registry's standard law-change mechanism, mirroring the per-year revisions of Modelo 100): cap the existing `2015-y-siguientes` revision at `valid_to = 2024-12-31` / `period_selector.year_to = 2024`, and add a self-contained `2025-y-siguientes` revision so a 2025 filing resolves unambiguously.
- Author the source-scoped base del ahorro in the new revision: casilla `impatriado.base-liquidable-ahorro` (the parte del ahorro of art. 25.1.f TRLIRNR Spanish-source dividends, interest and savings gains) plus its escala parameter `modelo-151.escala-cuota-integra-ahorro` (`bracket_table`, tramos 19/21/23/27/30 with cumulative cuotas 0/1.140/10.380/44.880/71.880, `valid_from` 2025), grounded on `ley-35-2006:art-93` + `ley-35-2006:art-93-ahorro`.
- Wire the savings cuota chain: formula `modelo-151-cuota-integra-ahorro` (`lookup_bracket` over the escala del ahorro) feeding `impatriado.cuota-integra-ahorro`, and fold it into the cuota diferencial (`subtract(add(cuota-integra-general, cuota-integra-ahorro), retenciones)`). Extend the construct, completeness manifest, verification predicates (add the base-ahorro implies-cuota-ahorro advisory), verification expectations, application links and workbook parity refs for the new revision.
- Add the grounded, non-tautological test `test_modelo_151_ahorro_escala.py`: expected cuotas are transcribed from the BOE published breakpoint cumulatives and marginal rates (never re-computed from the registry formula); a dedicated case pins the Beckham-specific 30 % top rate (distinct from the 28 % general IRPF savings scale) so the test fails on drift onto the wrong table.
- Update the two hard-coded parametrization blocks in `test_orden_aplicabilidad.py` to reflect the split (the open-ended M151 revision is now `2025-y-siguientes`).

## Outcome

Implemented ADR Phase 3. Modelo 151 now taxes the parte del ahorro (art. 93.2.e.2º) by its own grounded escala del ahorro, alongside the existing general escala (art. 93.2.e.1º). The savings escala figures are verified verbatim against the bundled consolidated Ley 35/2006 corpus and reproduced independently by the engine: a probe calc for 2025 returns cuota 21.880,00 for a 100.000 € savings base, 58.380,00 for 250.000 €, and 101.880,00 for 400.000 €, exactly the BOE escala arithmetic; the cuota diferencial correctly sums both cuotas íntegras. M151 loads and validates cleanly through the full `RegistryValidator`, revision resolution is unambiguous (2024 -> 2015-y-siguientes, 2025 -> 2025-y-siguientes), the legal grounding gate is green for `art-93` and `art-93-ahorro`, and `pytest --collect-only src/aeat` collects clean. All M151-scoped tests pass (the registry, continuity, aggregation, verification, orden-aplicabilidad, applicability, workbook-parity, deadline and CLI consumer suites, plus the 12 new savings-escala tests). ruff and pyright are clean on the changed surface (pyright emits only the two `reportPrivateUsage` warnings the sibling `test_renta_escala_estatal_ahorro_bracket_resolution.py` already carries for the same helper imports).

## Notes

- Grounded-or-deferred scope decision: the escala del ahorro has four legal versions across the 2015+ window (2015 transitional DT; Ley 11/2020 for 2021; Ley 31/2022 for 2023; Ley 7/2024 for 2025). Only the 2025+ redacción vigente table is groundable verbatim from the bundled consolidated corpus (the 2016-2024 intermediate tables are not bundled), so only the 2025+ escala is authored — dated `valid_from` 2025 in the new revision. Grounding any 2016-2024 savings escala, and adding the source-scoped ledger classifier for savings income (dividends/interest/gains, currently a manual base input mirroring how the general base was manual before its classifier landed), are the honest follow-ups.
- Corpus grounding uses the already-bundled authoritative consolidated `ley-35-2006.html` (which carries the verbatim art. 93.2.e.2º table) rather than editing the `ley-35-2006-art-93.html` fragment excerpt, per the codified preference to point `corpus_ref` at the bundled authoritative file over hand-authoring a duplicate; this also avoids regenerating the fragment's `.extracted.json` (keyed by `source_sha256`).
- Naming-convention note: the older revision keeps its id `2015-y-siguientes` while now being capped at 2024 (the codebase convention uses `YYYY-YYYY` ids for closed ranges). The registry validator accepts the capped id and a rename would churn the directory name, the eleven revision TOML keys and roughly five consumer test files in this shared worktree; the rename is left as an optional follow-up.
- Shared-worktree full-tree state: the full registry test sweep shows seven failures, all peer-owned and pre-existing (corpus sha / order-chain grounding for Modelos 202, 210, 349 and the orden HAC/242 deadline source, plus the reviewability line-count baseline driven by a peer-modified `_validate_surfaces.py`, and two codebase-size budgets whose offenders are all peer files). None touch Modelo 151 or the changed surface; owner-triaged as peer churn per the full-tree-gate-must-distinguish-owner rule.
- Code review is mandatory and still pending: the orchestrator must run the `vaultspec-code-reviewer` audit on this change before the step is treated as finally landed.
