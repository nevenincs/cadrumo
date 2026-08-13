---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c53b9e0f859be73e16a75253160b1bd2e5b91faec1b82bb9e55d477e611c2688'
step_id: 'S04'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Adjudicate per site which catalogue entry each advisory message actually asserts, and declare it. This is a tax review against the provision the message states, never a lookup, and it does not parallelise into a sweep. Where the casilla already carries the exact provision the derivation is correct and should be used. Where the catalogue carries a finer entry the casilla does not reference, declare the finer one and record why the casilla's coarser ref was not used. Do NOT append the finer entry to the casilla legal_refs to make a derivation work, because a casilla's refs describe what establishes that box and an eligibility rule governing one of its inputs is a different subject. EXCLUDED FROM THIS ROW BY THE S03 HARD GATE, and the exclusion is not a deferral of convenience: the four Art. 81 guarderia advisory sites in the minimo-descendientes advisory module are _guarderia_shape_advisory, _segundo_ciclo_month_advisory, _cotizaciones_ceiling_advisory and _guarderia_madre_meses_advisory, carrying source kinds guarderia_spend_needs_monthly_detail, guarderia_segundo_ciclo_month_undeclared, guarderia_cotizaciones_ceiling_unbounded and guarderia_madre_meses_undeclared. Do not declare a provision on any of them. The ley-35-2006 art-81 entry still cites the two-vintage excerpt: the repoint is prepared under the legal-corpus-vintage plan and is waiting on an operator stamp, so declaring these ids now would resolve them against a document that does not contain the clauses the messages assert, which is worse than the prose because the prose claims no corroboration. Re-open them here only once that stamp lands

## Scope

- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/aggregation/`

## Description

- Enumerated the six sites the grounding reference's Population A/B tables name outside the S03 exclusion, read each message against the LIVA/LIRPF text it cites, and declared per site rather than by mechanical casilla lookup.
- `_minimo_descendientes_advisory.py`: added a private `_casilla_legal_refs(revision, casilla_id)` helper (casilla `legal_refs` union its binding's, mirroring the aggregation package's `_undeclared_activity_advisory` pattern) and threaded `revision` into `_undeclared_advisory`, `_prorrata_inferred_advisory` and `_rentas_undeclared_advisory`.
- `_undeclared_advisory` (plain "Art. 58"): Population A. Casilla 0513 already carries `ley-35-2006:art-56/art-58/art-61` at the exact granularity the message asserts. Declared via casilla-derived `legal_refs`.
- `_prorrata_inferred_advisory` ("Art. 61 norma 1ª" halving): also Population A, on inspection rather than assumption. No `art-61-norma-1` sub-entry exists in the catalogue; the whole-article `ley-35-2006:art-61` entry's own `required_text` already targets the norma 1ª prorrateo sentence specifically, which is what casilla 0513 already references. Declared via casilla-derived `legal_refs`, not `asserted_legal_refs`.
- `_rentas_undeclared_advisory` ("Art. 58.1" + "Art. 61 norma 2ª"): Population B. The casilla carries only the whole-article refs; the message asserts two finer sub-entries (`ley-35-2006:art-58-1`, `ley-35-2006:art-61-norma-2`) that already exist in the catalogue at that granularity. Declared via `asserted_legal_refs`, `legal_refs` left empty.
- `_prorrata_regularizacion_advisory.py`, pending-provisional diagnostic ("LIVA arts. 104-105"): Population B, no casilla-derived match for `art-105`. Declared `asserted_legal_refs=("ley-37-1992:art-104", "ley-37-1992:art-105")`.
- `_prorrata_regularizacion_advisory.py`, `_especial_mandatory_diagnostics` CHECK branch ("LIVA art. 103.Dos.2.º"): no casilla in scope (annual ledger totals, not a revision casilla). Declared `asserted_legal_refs=("ley-37-1992:art-103",)`.
- `_prorrata_regularizacion_advisory.py`, `_especial_mandatory_diagnostics` PROMPT branch (adds "(art. 106)" for the classification instruction): same no-casilla shape, message asserts both provisions. Declared `asserted_legal_refs=("ley-37-1992:art-103", "ley-37-1992:art-106")`.
- Updated the one direct-call test site (`test_minimo_descendientes_advisory_headroom.py`) for the new `revision` parameter, fetching a real M100 revision rather than a stub.
- Added grounding assertions to the sites' own integration tests (`test_minimo_descendientes_prorrata_inferred_advisory.py`, `test_minimo_descendientes_rentas_undeclared_advisory.py`, `test_minimo_descendientes_advisory_wiring.py`), each asserting BOTH the populated field and that the other field stays empty, so a future author cannot silently populate the wrong one.

## Outcome

Six construction sites named in the grounding reference's Population A/B tables (outside the four excluded by the S03 hard gate) are now grounded: two via the casilla-derived path (matching Population A once actually checked against the catalogue rather than assumed), and four via the advisory-asserted path (Population B, no casilla in reach or a coarser casilla ref than the claim). Every declared id was cross-checked present in the live bundled legal catalogue (`ley-37-1992:art-103/104/105/106` and `ley-35-2006:art-58-1/art-61-norma-2` all resolve; confirmed directly, not assumed). No casilla's `legal_refs` was appended to make a derivation work. 109 tests green across the touched modules (`_minimo_descendientes_advisory.py`'s and `_prorrata_regularizacion_advisory.py`'s full integration suites, plus the new grounding assertions), ruff/format clean on every touched file.

## Notes

**A pre-existing, unrelated integration-test failure was observed and left untouched.** `test_descendientes_count_desync_advisory.py::test_a_count_edited_away_from_its_rows_is_reported` fails on a message-wording assertion (`"descendiente add" in reported[0]`) against `_count_desync_advisory`, a function this Step's diff never touches (confirmed by diff). Reads as unrelated peer churn on the same module rather than a regression this row introduced.

**The `_casilla_legal_refs` helper duplicates `_undeclared_activity_advisory.py`'s private `_casilla_grounding`** rather than promoting a shared primitive to the aggregation facade. Given two private copies now exist of the same ~10-line pattern, promoting one is a legitimate small follow-up, deliberately not taken here to keep this Step's diff to the adjudication it was scoped for.

**Registry build could not be exercised as a full green run in this worktree during this Step**, for the same reason recorded in the sibling legal-corpus-vintage P02 records (a peer's in-flight Modelo 130 relation migration). Every declared id was instead confirmed to resolve directly against the loaded legal catalogue.
