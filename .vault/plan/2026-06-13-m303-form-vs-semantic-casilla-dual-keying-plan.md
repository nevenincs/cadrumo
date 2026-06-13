---
tags:
  - '#plan'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
tier: L2
related:
  - '[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]'
  - '[[2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research]]'
  - '[[2026-04-17-modelo-303-formulas-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `m303-form-vs-semantic-casilla-dual-keying` `M303 official Diseno box population via semantic projection (Stage 2)` plan

### Phase `P01` - Authoritative box-to-semantic source map

Produce the authoritative, label-cross-checked projection map as a reference document before any TOML edit: each in-scope numbered box paired with the single semantic casilla id it copies, the box's existing legal_refs, and the resolved box-37 source (or its deferral). No source is wired without an exact 1:1 label match; box 37 stays manual if genuinely ambiguous.

- [x] `P01.S01` - Author the authoritative box-to-semantic projection map as a reference document, pairing each in-scope cuota box with its single semantic casilla id, cross-checked box-label against semantic-label, and copying each box's existing legal_refs; `.vault/reference/2026-06-13-m303-form-vs-semantic-casilla-dual-keying-reference.md`.
- [x] `P01.S02` - Pin box 37 deducible source by label-exact match to iva.autorepercutido.intracomunitaria.deducible (AIC leg), documenting the registry self-label collision with iva.autorepercutido.interior.deducible and deferring box 37 to manual only if genuinely ambiguous after confirmation; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`.

### Phase `P02` - Devengado cuota projections

Flip each in-scope devengado numbered box (09/06/03/11/13) and the devengado total (27) from input_kind manual to computed, adding a single-leaf projection FormulaDefinition that copies the box's semantic source via the existing _evaluate_leaf primitive. No binding, no re-aggregation, no second aggregation path. Each box carries its own legal_refs verbatim; the formula carries them too.

- [x] `P02.S03` - Flip box 09 (RG 21pct cuota) to input_kind computed with formula modelo-303-dr303-09-projection, a single-leaf FormulaDefinition target 09 copying iva.repercutido.general, carrying box 09 legal_refs; `verify the calculated box 09 equals iva.repercutido.general on a ledger calculate; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`.
- [x] `P02.S04` - Flip box 06 (RG 10pct cuota) to computed with formula modelo-303-dr303-06-projection copying iva.repercutido.reducido, carrying box 06 legal_refs; `verify box 06 equals iva.repercutido.reducido on calculate and via pull (one-aggregation-path parity); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`.
- [x] `P02.S05` - Flip box 03 (RG 4pct cuota) to computed with formula modelo-303-dr303-03-projection copying iva.repercutido.super-reducido, carrying box 03 legal_refs; `verify box 03 equals iva.repercutido.super-reducido registry-authoritatively; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`.
- [x] `P02.S06` - Flip box 11 (AIC bienes y servicios devengado cuota) to computed with formula modelo-303-dr303-11-projection copying iva.autorepercutido.intracomunitaria.devengado (oficial casillas 10/11 parity casilla, NOT the netted iva.autorepercutido.intracomunitaria), carrying box 11 legal_refs; `verify box 11 equals that source; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`.
- [x] `P02.S07` - Flip box 13 (otras ops inversion sujeto pasivo excl intracom cuota) to computed with formula modelo-303-dr303-13-projection copying iva.autorepercutido.interior.devengado (oficial casilla 13), carrying box 13 legal_refs; `verify box 13 equals that source; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`.
- [x] `P02.S08` - Flip box 27 (Total cuota devengada) to computed with formula modelo-303-dr303-27-projection copying iva.cuota-devengada-total, carrying box 27 legal_refs; `ensure topological order computes iva.cuota-devengada-total before box 27, and verify box 27 equals the total registry-authoritatively; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`.

### Phase `P03` - Deducible cuota projections

Flip each in-scope deducible numbered box (29/33/37/45) from manual to computed with a single-leaf projection formula copying its semantic source. Box 37 is wired to its exact AIC-deducible source or left manual per Phase P01's resolution. Same projection mechanism, grounding, and ordering guarantees as the devengado phase.

- [x] `P03.S09` - Flip box 29 (interiores corrientes deducible cuota) to computed with formula modelo-303-dr303-29-projection copying iva.soportado.interiores, carrying box 29 legal_refs; `verify box 29 equals iva.soportado.interiores on calculate and pull (parity); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`.
- [x] `P03.S10` - Flip box 33 (importaciones bienes corrientes deducible cuota) to computed with formula modelo-303-dr303-33-projection copying iva.soportado.importaciones (oficial casilla 33), carrying box 33 legal_refs; `verify box 33 equals that source; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`.
- [x] `P03.S11` - Flip box 37 (AIC corrientes deducible cuota) to computed with formula modelo-303-dr303-37-projection copying the P01-pinned source iva.autorepercutido.intracomunitaria.deducible, carrying box 37 legal_refs; `if P01 deferred box 37 as ambiguous, leave it manual and keep the Stage 1 advisory for it instead; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`.
- [x] `P03.S12` - Flip box 45 (Total a deducir cuota) to computed with formula modelo-303-dr303-45-projection copying iva.cuota-deducible-total, carrying box 45 legal_refs; `ensure topological order computes iva.cuota-deducible-total before box 45, and verify box 45 equals the total registry-authoritatively; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`.

### Phase `P04` - Verify-gate transition and parity gates

Add an equality/consistency operator to the verification predicate DSL, narrow the Stage 1 implies_any_nonzero advisories to the boxes that remain manual, add a per-box consistency predicate (box == semantic source) for every populated box, and confirm pull==calculate parity, the export/BOE casilla refs now carry value, and the workbook parity gate stays green.

- [x] `P04.S13` - Author the ten single-leaf projection FormulaDefinition blocks (modelo-303-dr303-NN-projection for boxes 09/06/03/11/13/27/29/33/37/45) in revision.toml, each with target the box id, an expression that is the one semantic casilla-id leaf, money-2 rounding, and the box legal_refs; `register each id in the revision formula list; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`.
- [x] `P04.S14` - Add an equality/consistency operator to the verification predicate DSL registry KNOWN_VERIFICATION_PREDICATE_OPERATORS, separately grounded, so a box-equals-source consistency predicate can be authored; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P04.S15` - Extend the predicate authoring-time validator to accept the new equality operator and reject malformed equality expressions; `src/aeat/domain/calculations/registry/_validate_surfaces.py`.
- [x] `P04.S16` - Implement the equality-operator branch in the predicate evaluator so the consistency predicate returns True iff the box value equals its semantic source value; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `P04.S17` - Narrow the devengado implies_any_nonzero advisory predicate to drop the now-populated constituents (03/06/09/11/13) and retire or retain it only for boxes that remain manual, so the advisory and calculate diagnostic stop firing for populated boxes and keep firing for manual ones; `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`.
- [x] `P04.S18` - Narrow the deducible implies_any_nonzero advisory predicate to drop populated constituents (29/33 and 37 if wired) and keep it firing only for any box left manual (e.g. 37 if deferred); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`.
- [x] `P04.S19` - Add one box-equals-source consistency verification predicate per populated box using the new equality operator, each grounded in the box legal_refs, to catch a future mis-edit (box re-flipped to manual or projection pointed at the wrong source); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/0001-verification_predicates.toml`.
- [x] `P04.S20` - Verify the pull path and the calculate path produce identical values for every populated box on a shared revision (one-aggregation-path-pull-equals-calculate), proving the projection is transport-identical; `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`.
- [x] `P04.S21` - Verify the BOE/fichero export field modelo-303-page-01-casilla-27 and the sibling casilla-NN export refs now write the projected value not zero, and confirm the workbook/BOE parity gate stays green (modelo-export-mirrors-official-structure); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/`.

## Description

This plan implements Stage 2 of the M303 official-Diseno box wiring authorised and ratified by the 2026-06-13 dual-keying ADR. On a ledger calculate the engine folds real cuota into the semantic aggregate layer (iva.repercutido.general, iva.soportado.interiores, iva.cuota-devengada-total, etc.) while every official numbered cuota box stays zero, so an operator transcribing the numbered boxes to the AEAT sede sees a silent under-declaration and the BOE/fichero export writes zero into the official positions. Stage 1 (commit 330ab6771) made the contradiction non-silent with a calculate advisory and two ADVISORY implies_any_nonzero verify predicates. Stage 2 POPULATES the in-scope numbered boxes so the operator transcribes real cuota.

The mechanism is a single-source projection, not a second aggregation. Each in-scope numbered box flips from input_kind manual to input_kind computed and gains a FormulaDefinition whose expression is one casilla-id leaf naming the already-computed semantic source. The leaf resolves through the existing _evaluate_leaf primitive (src/aeat/domain/calculations/registry/_formula_runtime.py) — the same primitive the existing iva.cuota-devengada-total formula uses — so the box is a pure copy evaluated in topological order after its source. No binding, no ledger re-selection, no relation, no previous_filing carry: one value keeps exactly one aggregation path, satisfying one-aggregation-path-pull-equals-calculate and calculation-source-canonical-mechanism by construction. Because pull and calculate evaluate the one formula graph, the projection is transport-identical.

The plan honours the ratified defaults: only cuota-bearing boxes with an exact single semantic source are populated (09/06/03/11/13 devengado, 27 devengado total, 29/33/37 deducible, 45 deducible total); base, tipo, regimen-simplificado, and eight-LIVA-article-blocked boxes stay manual and advisory-covered, never force-fitted. Box 37's source is pinned by label-exact match in Phase P01 (the registry self-labels two casillas "casilla 37"; the AIC label selects iva.autorepercutido.intracomunitaria.deducible), and box 37 stays manual if the executor judges it genuinely ambiguous. Each projection formula carries the box's existing legal_refs verbatim, honouring registry-calculation-legal-grounding, and the export/workbook parity gate keeps the official structure (modelo-export-mirrors-official-structure).

Authorising documents are carried in the `related:` frontmatter and inherited by every Step: the 2026-06-13 dual-keying ADR (the Stage-2 decision and ratification), the 2026-06-04 research, the 2026-04-17 M303 formulas ADR, the 2026-06-10 aggregation-taxonomy ADR, and the 2026-06-09 IVA routing/carry ADR.

## Steps







## Parallelization

P01 (the box-to-semantic map and the box-37 pin) is a hard precondition for P02 and P03: no box is wired until its source is fixed and box 37 is resolved or deferred. P02 (devengado) and P03 (deducible) are independent of each other and can run in parallel once P01 lands — they touch the same two casillas TOML files but disjoint box rows, so two coders may proceed if they coordinate on the shared files per the worktree WIP-abort discipline.

P04 is partially ordered. S13 (authoring the projection FormulaDefinition blocks in revision.toml) is the companion edit to the P02/P03 box flips and lands with them — the box flip references a formula id that must exist. The DSL-operator trio S14/S15/S16 (schema registry, validator, evaluator) is a self-contained sequence (registry before validator before evaluator) and can proceed in parallel with the projection work; it is a precondition only for the consistency predicates S19. The advisory-narrowing S17/S18 and the consistency predicates S19 must follow the box flips (the predicates reference populated boxes). The parity and export verification S20/S21 are the closing gates and run last, after all projections and predicates are in place.

Assign the registry projection and verification-DSL Steps to vaultspec-high-executor (core calculation and gate logic); assign the reference-map and parity/export verification Steps to vaultspec-standard-executor; dispatch a vaultspec-code-reviewer pass over the box-37 pin and the advisory-narrowing to confirm no manual box silently loses its advisory coverage.

## Verification

Every Step carries an externally-grounded verification gate; the plan is complete when every Step is closed and every gate below passes.

- Per-box equality: for each populated box, a ledger-fed calculate produces a box value that equals its named semantic source casilla value, asserted registry-authoritatively (the source is itself registry-computed, never a hand-computed number), satisfying no-tautological-calculation-tests. The equality is the projection's defining contract.
- One-aggregation-path parity: the pull path and the calculate path produce identical values for every populated box on a shared revision (S20), proving the projection introduced no second aggregation surface and the two transports cannot drift (one-aggregation-path-pull-equals-calculate).
- Export/BOE value carriage: the export field modelo-303-page-01-casilla-27 and the sibling casilla-NN export refs now write the projected value, not zero (S21), and the workbook/BOE parity gate (casilla set, numbering, section order) stays green (modelo-export-mirrors-official-structure).
- Legal grounding: each projection FormulaDefinition carries the box's existing legal_refs, and no projection is authored for a box whose semantic source is ungrounded or absent (registry-calculation-legal-grounding).
- Advisory narrowing: the Stage 1 implies_any_nonzero advisory and its calculate diagnostic stop firing for populated boxes and continue firing for any box left manual (base/tipo/blocked, and box 37 if deferred), verified against a ledger calculate that populates the semantic layer.
- Consistency predicates: each populated box carries a box-equals-source consistency verification predicate using the new equality operator, exercised by a registry-validation test; the operator is registered in KNOWN_VERIFICATION_PREDICATE_OPERATORS and rejected when malformed by the authoring-time validator.
- Collection clean: `uv run --no-sync pytest --collect-only -q` is clean before each commit, and the M303 registry and verification test surfaces pass.

No code is in scope beyond the registry TOML edits, the projection FormulaDefinition blocks, and the small grounded verification-DSL equality operator. The semantic aggregation layer and the already-computed resultado-chain boxes (46/64/65/66/69/71) are untouched.
