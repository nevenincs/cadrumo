---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S29'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# M202 deferred items grounded decisions

This record documents an honesty-review-driven closure pass, not an
originally planned Step. The research (`2026-06-30-modelo-verify-nonzero-guards-research`)
flagged two M202 open items -- casilla `33` ("Minimo a ingresar, CN >= 10
millones euros") and the Mod. 40.3 LIS B2 "casos especificos" lane (casillas
`61`-`66`) -- as "not investigated this pass," and no plan Step ever picked
either up, unlike the parallel M714 items the same research flagged, which
Wave `W02` Phase `P06` tracked and closed. A fresh-context honesty review
surfaced this gap; this record closes both items, modelling the rigor on the
`2026-06-30-modelo-verify-nonzero-guards-audit` M714 decision.

## Description

- Re-read the plan, ADR, research, and the M714 `W02.P06` audit to model the
  required investigation rigor.
- Re-confirmed casilla `33` is `input_kind = "manual"` with no formula or
  binding linkage, byte-identical across all three M202 revisions
  (`2019-2022`, `2023-2024`, `2025-y-siguientes`).
- Read the bundled `ley-27-2014-art-40.html` corpus text in full (five
  numbered paragraphs) and confirmed it contains no minimum-tax floor for
  large taxpayers; searched `legal/is.toml` and the bundled corpus tree for a
  `ley-27-2014:art-30-bis` or equivalent disposition establishing the INCN >=
  EUR 10.000.000 pago-fraccionado-minimo and found none.
- Traced the full B2 "casos especificos" lane: casillas `19`-`26` (tipo
  1/tipo 2 tramos, all three revisions) and `61`-`66` (tipo 3/tipo 4 tramos,
  2025-only), their formulas (`0009`-`0013`), and the `modelo-202-foundation`
  construct's declared formula ordering.
- Confirmed casillas `63`/`66` are formula-derived from `61`/`62` and
  `64`/`65` via the `percent` operator -- the same shape as the shipped `04
  -> 13` and M131 `01 -> 02` precedents -- and authored two ADVISORY guards
  accordingly.
- While tracing the B2 lane, discovered that casilla `26` (B2 resultado
  previo, formula-derived from `22 + 25 + 63 + 66 + 50 + 42 + 51 + 52`) is
  never read by any formula in any of the three M202 revisions --
  specifically not by `modalidad-40-3-resultado` (casilla `32`), which reads
  only casilla `18` (B1 caso general), byte-identical across all three
  revisions. Corroborated against the official export-layout field ordering
  and the construct's declared formula sequence, both of which place casilla
  `26` immediately upstream of casilla `32`.
- Decided not to author a predicate over the unwired casilla `26` -> `32`
  relationship: the correct combination semantics cannot be safely inferred
  from the bundled corpus or the formula's own vague source citation without
  further legal/workbook verification; escalated it as a critical follow-up
  instead of guessing.
- Persisted all three decisions (documented non-guard for casilla `33`,
  authored ADVISORY for the B2 tipo-3/tipo-4 tramos, critical escalated
  non-guard for the casilla `26`/`32` wiring gap) in a new audit document
  (`.vault/audit/2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit.md`).
- Authored the two ADVISORY predicates in
  `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/verification_expectations/0002-verification_predicates.toml`,
  appending to the existing (peer-authored, in-flight) `04 -> 13` guard file
  without disturbing it.
- Added a registry-shape test asserting the two new predicates'
  `predicate_id`/`expression`/`finding_kind`/`legal_refs`, plus two locking
  registry-shape tests asserting the deliberate absence of a casilla-`33`
  guard and the continued absence of casilla `26` from the casilla-`32`
  formula's expression tree, to
  `src/aeat/domain/calculations/registry/tests/test_modelo_202_registry.py`.
- Added the gate-behaviour two-tier test pair (FIRES / HOLDS / trivial-HOLD)
  for both new predicates to
  `src/aeat/application/modelo/tests/test_verification_m202_advisory.py`.
- Ran the focused registry and gate-behaviour suites and confirmed a clean
  pass; confirmed the full M202 registry still loads and validates.

## Outcome

Three grounded decisions, none silently dropped:

1. Casilla `33` (minimo a ingresar, CN >= 10M) -- **documented non-guard**
   (wontfix-for-now), same shape as the M714 riskier-edge decisions: no clean
   antecedent casilla, and the binding minimum-tax provision is ungrounded in
   this codebase.
2. B2 casos especificos tipo-3/tipo-4 tramos (casillas `61`-`66`, 2025-only)
   -- **authored** as two ADVISORY guards
   (`modelo-202-2025-b2-base-tipo-3-implica-importe-pago-fraccionado-tipo-3`,
   `modelo-202-2025-b2-base-tipo-4-implica-importe-pago-fraccionado-tipo-4`),
   both grounded in `ley-27-2014:art-40-3` and `art-29`.
3. Casilla `26` (B2 resultado previo) unwired from casilla `32`
   (modalidad-40-3-resultado) -- **critical escalated finding, documented
   non-guard for now**: a suspected formula-correctness defect confirmed
   across all three M202 revisions, requiring dedicated legal/workbook
   verification before any formula change or predicate is authored.

Full focused test run
(`test_modelo_202_registry.py`, `test_verification_m202_advisory.py`,
`test_modelo_714_registry.py`, `test_verification_m714_advisory.py`): 60
passed.

## Notes

Two transient environment incidents, no lasting effect on this Step's own
files: a pytest run of `test_verification_m202_advisory.py` failed with a
registry-validation error naming unknown casillas `29`/`39` on an unrelated,
untracked Modelo 714 file
(`src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0002-verification_expectations.toml`),
and a second, later run failed with a different unrelated error naming a
Modelo 100 binding source-citation gap on untracked/modified M100 registry
files (`.../100/revisions/2024/bindings/0026-...`,
`.../100/revisions/2025/bindings/0049-...`). Both poisoned the process-wide
`resources()` registry-authority cache used by every
`resources().modelos.authority`-based test (including the pre-existing,
peer-authored M202 `04 -> 13` gate-behaviour tests this Step did not touch).
Both files were live, in-flight peer WIP (untracked or actively modified, not
part of this plan or its M714/M202 Steps); per `uncommitted-wip-is-not-orphaned`
both were left untouched. In both cases a re-run shortly after passed cleanly
-- the owning peer agents corrected their files in place between runs (the
M714 file: bare `"29"`/`"39"` -> the correct `patrimonio.cuota-integra` id).
Verified via a standalone probe using `_committed_modelo("202")` (bypassing
the shared cache) that the new predicates' FIRES/HOLDS/trivial-HOLD behaviour
was correct independent of this transient poisoning, before confirming the
full pytest re-run was green each time. No file outside this Step's own scope
was edited to work around either incident. The `vaultspec-core vault add audit` / `vault add
exec` scaffolds for this Step both collided on their default
`2026-07-01-modelo-verify-nonzero-guards-audit.md` /
`2026-07-01-modelo-verify-nonzero-guards-exec.md` paths with a
concurrent peer's already-landed M123 grounding audit/exec pair (a genuinely
different, unrelated honesty-review follow-up on the same feature and date);
per the feature's own documented topic-infix convention
(`yyyy-mm-dd-<feature>-<topic>-audit.md`) this record and its audit were
authored at a `m202-deferred-items`-infixed path instead, hand-matching the
`.vaultspec/templates/audit.md` and `exec-step.md` frontmatter shape (and the
concrete shape the CLI had just produced for the colliding peer pair) since
the installed CLI (`vaultspec-core` 0.1.36) has no `--topic`/`--slug` flag to
produce the infix directly and a scratch-directory scaffold attempt failed for
lacking a `.vaultspec/` root.
