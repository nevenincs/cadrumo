---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:690928a88bef6bb00c03b8b2652f04d8430ca76d572642eba48aa0dbf14289ab'
step_id: 'S88'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# retire every stale Modelo 303 reference to the deleted revision id and tighten the cutover gate's modelo attribution so a sibling modelo's legitimate identically-named revision is not flagged, making the cutover gate, the registry diff module and the reconcile verb green - EXCLUDES the two M303 application modules whose deducible-IVA fold changed underneath them, which the standing goal still requires and which S91 now carries

## Scope

- `src/cadrumo/application/registry/tests/test_diff.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py`
- `src/cadrumo/domain/calculations/registry/tests/test_m303_retired_revision_cutover.py`

## Description

- Replace the cutover gate's scope-wide attribution with nearest-modelo attribution, so the retired identifier is judged against the modelo actually named around the line.
- Narrow the selector-redeclaration check to containers that MAP the modelo token onto a revision - a dict key, or a branch test - rather than any container carrying both tokens.
- Retire the two registry-diff anchors the Modelo 303 span split invalidated, keeping the halves that still have a witness and stating the one that no longer does.
- Repoint the reconcile verb's pinned revision at the law-determined answer for its 2024 first-quarter fixture.

## Outcome

The cutover gate passes. The retired identifier has no remaining Modelo 303 location in any executable, test, fixture or locale surface, and the selector check reports none.

`test_diff` passes 14 of 14 and the cutover module 1 of 1: 15 passed. `ruff format --check` and `ruff check` pass on both targets.

Two attribution defects were the reason a clean corpus read as a violation. The retired identifier is a CURRENT, legitimate revision id for Modelo 180 and Modelo 721, and the old rule flagged a Modelo 180 assertion whenever anything else in the same function mentioned Modelo 303 - which one unrelated `m303_regimen_simplificado_scope` keyword argument forty-five lines away did. The selector check was never reached before, because the earlier assertion always failed first; on first evaluation it reported twelve locations, every one a work-unit, receipt or report fixture that merely names a modelo and a revision. Two of Modelo 303's live revision ids are now bare four-digit years, so a both-tokens-present rule reads `"ejercicio": "2025"` beside `"modelo": "303"` as a revision selector.

The narrowed selector check was proven to bite from outside the repository: three synthetic redeclarations (dict key, if branch, ternary) are all flagged, a carrying fixture is not, and the proximity rule attributes a Modelo 180 line to Modelo 180 while still attributing a Modelo 303 line to Modelo 303. Nothing under `src` was mutated for the proof. The gate had already demonstrated a real bite earlier in the same session, reporting ten genuine stale locations against the live corpus.

The registry diff lost two anchors to the span split. Orden HAC/819/2024 now grounds the two 2024 revisions, and the year-keyed diff entry point refuses a filing year carrying a mid-year design boundary, so the gained-a-later-orden witness is unreachable through that surface; the dropped-superseded-orden half is asserted instead and the unreachable direction is stated rather than faked. The 2025 coefficients parameter left the 2023 revision, so the added-parameters anchor moved to the two transitional reduced-rate percentages the 2023 revision introduces and the 2009 revision cannot declare.

## Notes

**Excluded, and what the standing goal still asks for.** The row originally named five modules. `test_modelo_303_deductible_evidence_gate` and `test_modelo_303_official_box_under_declaration` are excluded here because their remaining failures are not retired-identifier failures: an unevidenced purchase's IVA no longer folds into the deducible casillas at calculate, so a module whose whole contract is fold-then-block-at-verify now measures a zero it was written to prove non-zero. The standing goal still requires both modules green; S91 carries that, and it is an adjudication rather than a fixture repair because it decides where the deducible-evidence gate binds.

Work landed here reduced those two modules from ten failures to three by wiring the shared filing-evidence fixture into the official-box calculate path - the calculate action now requires typed Modelo 303 filing-instance evidence for every M303 revision. That edit is carried in this Step's commit and is a precondition of S91, not a claim that S91 is done. The third residual there is a casilla-27 export-ref assertion against layouts withdrawn from filing grade corpus-wide.

A peer landed the fixture repoint for the two application modules and the reconcile verb as `3241d5a173` while this Step was in flight; that half is theirs and was not re-authored.

**Blocked at commit.** `.git/index.lock` has been held since 19:31:00 with a frozen mtime and no HEAD movement for over half an hour - a dead holder. Removing anything under `.git/` is absolutely forbidden, so this Step's commit could not land in-session. No data loss and no destructive Git operation occurred.
