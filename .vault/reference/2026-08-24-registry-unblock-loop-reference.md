---
related: []
date: '2026-08-24'
modified: '2026-08-25'
body_hash: 'sha256:c4b0b8c2693f20cd2264d098e1a266d78509152f61611aea3016e194b96232f9'
tags:
  - '#reference'
  - '#registry-completeness-closure'
---
# REGISTRY LOOP v4 — make the registry GREEN and WHOLE

GOAL, set by the operator: **the registry is green (every gate passes) and whole (every
revision is complete enough to file what it claims).** Nothing else is progress.

## THE PRODUCER-KEY CAMPAIGN IS DONE. DO NOT RE-TARGET IT.

`src/cadrumo/application/filing/tests/test_export_producer_resolution.py` **PASSES** as of
commit `e848cc54e2`. All 395 producer keys cited by every published export layout across
all seven modelos resolve. m200, m202, m210, m222, m232, m296 and m353 are finished.

Every earlier version of this brief opened by naming that work. It is spent. A fire that
starts by looking for unresolved producer keys in a SHIPPED layout will find none.

## WHAT IS ACTUALLY LEFT — from the gate, not from memory

The live worklist is
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`.
Run it first; it prints one line per revision that cannot file, each naming its own
blocker. As of 2026-08-24 it names **14 revisions across 13 modelos**, in five classes:

| blocker | revisions | actionable? |
|---|---|---|
| producer vocabulary | 036, 220/2024 | **YES — the worked pattern below** |
| design coverage (revision span outruns the cited design's era) | 182, 187, 188, 194, 220/2025, 763 | needs the older designs acquired, or the span split |
| era (no cited design governs this window) | 185/2003-2025 | as above |
| casilla surface | 390/2021 — 10 casillas where every filing-grade sibling has 325+ | author the casillas first |
| design extraction | 038 — the bundled artefact is a form DIAGRAM with a position ruler, not a field table | no parser repair fixes this |
| record terminator | 840 — the design numbers the line break as a field inside the record, the pipeline puts it on the transport | contract decision, not authoring |
| corpus — nothing bundled | 136, 721 | **NOT A BLOCKER.** Operator ruling: "missing not yet published is not a blocker, it's just not published." Do not chase these. |

**Prefer forms that CALCULATE.** Operator ruling: "forms that calculate nothing have no
need." Modelo 220 (fiscal-group IS consolidation) outranks 036 (censal; its own
`revision.toml` says this application reads the censal declaration through censo
synchronisation rather than producing it, and its `authority_grade` is `applicability`).

## THE DESIGN-COVERAGE ROWS — verified against AEAT, 2026-08-24

Six worklist rows say "ejercicios X-Y fall outside every cited design's era". Two obvious
cheap fixes were tested against AEAT's own pages and **both are wrong**. Do not retry them.

**Not a citation gap.** Every one of these revisions already cites every design registered
for its modelo. Checked by loading the authority and diffing `source_refs` against the
catalogue.

**Not an unregistered-corpus gap.** The corpus holds exactly what is registered for 182,
185, 187, 188, 194 and 763 — no bundled-but-unregistered design exists for any of them.
(The 40 unregistered bundled designs are all on 200, 202, 100, 036, 123, 111, 604, 130,
115, 349, 345 — none of which is on this worklist.)

**Not a mis-derived `applies_from` either.** The filenames read "actualizado en 2022",
which is an UPDATE year, so pinning `applies_from` to it looked like the error. AEAT's own
pages refute that: the current design for modelo 187 is published as *"Orden EHA/3021/2007
(actualizado por Orden HFP/823/2022 **para el Ejercicio 2022**)"*. AEAT scopes it to 2022
explicitly. Widening it back to 2019 would put a claim in the catalogue that AEAT's own
page contradicts.

**What is actually true:** AEAT publishes the missing designs on the *ejercicios
anteriores* pages and this corpus never fetched them. Verbatim from
`ejercicios-anteriores-modelos-100-199.html` on 2026-08-24:

- **182** — "Orden EHA/3021/2007 (incluye correccion de errores por BOE de 2 de noviembre
  de 2007)"; "(actualizado por Orden HAP/2250/2015)"; "(actualizado por Orden
  HFP/1351/2021, de 1 de diciembre)"; "(actualizado por Orden HAC/1504/2024, de 26 de
  diciembre)". Bundled: 2024 and 2025 only.
- **187** — "Orden HAP/1608/2014 (Ejercicio 2017)"; "(actualizado por Orden HAC/1417/2018
  para el Ejercicio 2018)". Bundled: the 2022 one only.
- **188** — "Orden EHA/3021/2007 (Ejercicio 2017)"; "(actualizados por Orden
  HAP/2118/2015)". Bundled: the 2023 one only.
- **194** — "Orden de 18 de enero de 1999 (actualizado por Orden HAC/1276/2019)";
  "(actualizado por Orden HFP/1284/2023)"; "18 de Febrero de 2014 - Version 1.0".
  Bundled: 2023 and 2024 only.

**And acquisition alone does not close them.** AEAT names 187's designs "para el Ejercicio
2018" and then "para el Ejercicio 2022", and publishes nothing for 2019-2021. Whether the
2018 design governs those three years is a judgement AEAT does not state. Per
`aeat-calculation-grounding` that is a TAX REVIEW against official sources recording honest
reviewer provenance — the orden's BOE text decides it — not something a fire may assert to
clear a gate. Acquire the artefacts first; then review the era boundaries against the
ordenes; only then register.

**220/2025-y-siguientes is descoped, not blocked.** Its revision is open-ended and the 2025
design ends 2025-12-31, so the "gap" is ejercicio 2026, whose design AEAT has not published
yet. That is the operator's "not yet published is not a blocker" ruling.

## THE WORKED PATTERN — producer vocabulary

Seven modelos were completed this way. For a modelo whose non-casilla fields have no
identity:

1. a typed `ModeloNNNProfileFacts` in `application/filing/_producer_snapshot.py`, each
   field annotated with its design offset and length
2. added to the `FilingModelProfileFacts` union
3. a snapshot validator dispatched from `_validate_snapshot_model_profile`
4. an `mNNN_producer_values()` resolver in `_export_producer.py`
5. its keys **derived** into the `shared` set in `filing_producer_ownership()` — splat the
   resolver's own map rather than restating the members, or the two drift

## AND THE SECOND DEFECT CLASS, FOUND ON m296 — REPEATED RECORDS

A producer key is the right home for a DECLARATION-WIDE fact. It is the wrong home for a
PER-ROW one, and modelo 296 shipped 100 of those.

Four of 296's five records are lists in AEAT's design — one row per payee, per pago, per
certificado — but were published as single non-repeating records. **Each held exactly one
row.** A 296 with two payees could not be expressed at all. That failure is silent in both
directions: a one-row ceiling emits a structurally valid file that under-declares by every
row after the first, and a per-row producer reads one declaration-wide value that is blank
or identically wrong on every row.

**Before writing a producer key, ask whether the field is per-record or per-row.** If the
AEAT sheet name says *relación*, or the record carries an "identificador de registro o
número de orden", it is a list. The fix is:

1. semantic map record declares `repeat = "projection_rows"`
2. its entries become `kind = "projection"` with a `projection_ref`
3. a field enum plus a ref type in `core/_filing_projection_ref.py`, added to the
   `FilingProjectionRef` union and promoted to the `cadrumo.core` facade
4. the revision declares one `projection_endpoints` entry per field — the semantic map and
   the declarations must biject or the map is refused
5. a row type on the profile facts, **generated from the field enum** so the reference and
   the row cannot disagree
6. a plan builder plus a `_projection_plan_for_layout` dispatch arm

**Carry no `slot` unless AEAT prints a fixed number of rows.** m200's party blocks have a
printed ceiling, so a slot is part of their address. Payees, pagos and certificados do not:
the RECORD repeats and the render occurrence identifies the row. A slot on an unbounded
family is a second row axis always equal to 1, and an invitation to cap the rows.

## REGENERATING AN EXPORT TREE

**Never hand-author or hand-render into `src/`.** Use
`publish_validated_generated_export_tree` (`dev/registry/pipeline/_tree_publication.py`),
which validates the candidate through the real loader and registry authority, journals,
swaps, verifies and finalises under a lock with rollback. Two traps, both hit and both
cost a cycle:

- **The candidate must be on the same volume as the registry.** The cutover is an atomic
  rename; a system temp dir on `C:` fails with WinError 17, rolls back correctly, and can
  never succeed. Pass `dir=Path.cwd()` to `TemporaryDirectory`.
- **A failed run leaves a journal** at
  `src/cadrumo/_data/registry/aeat/.generated-export-transaction-<modelo>-<revision>.json`
  (gitignored). The next run refuses with "journal candidate does not match the explicit
  caller temporary root". Confirm the tree is intact and both journal referents are gone,
  then delete it.

Render into `<temporary_root>/registry/aeat/modelos/<m>/revisions/<r>/export`, stage the
target's non-export authority beside it with `ignore_patterns("export")`, and stage every
modelo the target folds in (`supporting_modelos`) or validation refuses with "references
unknown source modelo" — an isolation artefact indistinguishable from a real gap.

A driver that works is at
`.../scratchpad/publish296.py`; adapt its constants.

## DISCIPLINE

- Start every fire by RUNNING the worklist gate. Do not trust this document's table — it
  is a snapshot and this campaign has repeatedly acted on stale counts.
- **USE vaultspec-rag**, not blind grep:
  `uvx vaultspec-rag search "<behaviour> <domain nouns>" --type code`, and
  `--type vault --doc-type adr` for the governing decision.
- **Four sessions share this tree.** `git log` before touching a modelo; commit by explicit
  pathspec only your own files. A peer sweep touching hundreds of test files landed
  mid-session — a bare `git add -A` would have consumed all of it.
- Compare the owning test directory against the same run with your change stashed.
  `application/filing/tests` is **63 failed / 449 passed** pre-existing; none of those
  failures mentions 036 or censo, so the claim that 30 of them block modelo 036 is FALSE.
- **Never** fabricate an offset, casilla number, stamp, or a claim about AEAT. Never trust
  a zero from a parser — the export TOML uses SINGLE quotes and a double-quote pattern
  silently returns nothing. Never believe a suite whose wall time ballooned.
- **Never write audit prose.** Fix the application.
- If a fire cannot honestly advance, say so and stop rather than manufacture work.
