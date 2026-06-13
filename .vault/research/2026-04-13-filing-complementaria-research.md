---
tags:
  - "#research"
  - "#filing-complementaria"
date: 2026-04-13
modified: '2026-04-13'
title: Filing Complementaria / Amendment Engine — Research
related:
  - "[[2026-04-12-filing-draft-engine-research]]"
  - "[[2026-04-12-modelo-303-390-research]]"
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-12-synthetic-filing-fixtures-research]]"
issue: wgergely/aeat#93
---

# research: filing complementaria

## problem statement

Issue #93 closes the current gap between a filed return and a legally valid
correction flow. The codebase already builds original drafts for modelos
`130`, `303`, and `390`, persists submitted filings as strict JSON, and parses
justificantes, but it has no typed amendment model, no builder that computes a
casilla delta against a prior filing, no amendment submission path, and no CLI
surface for review and dispatch.

The implementation must respect two external constraints:

- The legal correction mechanism depends on the type of model and, for IVA,
  also on the filing period date.
- Sibling work on `aeat.adapters.outbound.aeat.auth`, `aeat.adapters.outbound.aeat.browser`, `aeat.status`, and Track B
  provenance internals is not available for hard imports; integration must stay
  inside the public surfaces already on `main` or use Protocol seams.

## legal findings

### lgt baseline

- `Ley 58/2003`, article `120.3` and `120.4`, updated by `Ley 13/2023`
  effective `2023-05-26`, preserves the classic rectification path and adds
  `autoliquidación rectificativa` where the tax's own regulation enables it.
- `Ley 58/2003`, article `122.1` and `122.2`, still defines
  `autoliquidación complementaria` as the correction path only when the new
  return produces a **higher amount to pay** or a **lower amount to refund or
  compensate** than the prior self-assessment.
- In every other case, article `122.2` pushes the taxpayer back to article
  `120.3` / `120.4`, meaning rectification rather than complementaria.

Implication for #93:

- The engine may only accept a `complementaria` when the liability delta is
  monotonic in the State's favour.
- Any amendment that reduces liability, increases a refund, or increases an
  amount to compensate is outside scope and must fail fast as a separate
  rectification process.

### rgat / model-shape baseline

- `Real Decreto 1065/2007`, article `118`, distinguishes
  `declaración complementaria` from `declaración sustitutiva`: the first
  partially updates the earlier filing, the second replaces it completely.
- `Real Decreto 1065/2007`, article `119.2` and `119.3` requires a
  complementaria to carry the **full set of declared data**, not just the
  changed fields, and the amount from the original filing must be deducted from
  the recomputed total.

Implication for #93:

- The internal amendment engine can store only the delta for auditability, but
  the transport layer must still be able to reconstruct or project the full
  amended filing shape expected by AEAT.
- `sustitutiva` is not a synonym for complementaria. It is a separate amendment
  kind for models whose official instructions say the prior declaration must be
  replaced in full.

## model-specific findings

### modelo 130

- AEAT's `Modelo 130` record design includes explicit complementaria fields for
  the prior return: `Código electrónico declaración anterior` and
  `nº justificante declaración anterior`.
- The existing record design also exposes a "resultado de las anteriores
  declaraciones" field, which matches the legal rule that the prior filing is
  deducted from the recomputed total.

Implication for #93:

- `130` is a genuine complementaria path on current AEAT forms.
- The amendment builder can anchor the liability check on the final payable
  casilla already computed by the current builder (`07`).
- The submitter path should try to set the complementaria radio/fields when the
  underlying browser form exposes them, but this may need a guarded stub if the
  current `Modelo130Submitter` abstraction does not yet model that branch.

### modelo 303

- `Orden HAC/819/2024`, published `2024-08-05`, effective `2024-08-06`,
  states that the `modelo 303` correction path changed to
  `autoliquidación rectificativa`.
- The order is applicable for the first time to monthly filings for
  `September 2024` and quarterly filings for `2024Q3`.
- The same order explicitly says returns for periods **before** monthly
  `2024-09` or quarterly `2024Q3` cannot be corrected through the new
  rectificativa model variant.

Implication for #93:

- The amendment engine must be **date-sensitive** for `303`.
- For `303` periods before the cutover, a complementaria-style delta engine is
  still coherent with the legacy model shape.
- For `303` periods on or after `2024-09` / `2024Q3`, the legally correct
  correction path is `rectificativa`, not `complementaria`, so #93 should not
  pretend to support a complementaria there. The safest outcome is a hard
  validation error documenting the gap.

### modelo 390

- AEAT's `Modelo 390` instructions and file design expose a
  `declaración sustitutiva` marker plus `número de justificante de la
  declaración anterior`.
- The instructions describe the sustitutiva as the path that "anula y sustituye
  completamente" the earlier annual summary.

Implication for #93:

- `390` should map to amendment kind `sustitutiva`, not `complementaria`.
- The amendment builder can still compute and store a casilla delta for audit
  review, but submission semantics are full replacement semantics.
- The current issue's `AmendmentKind` enum is therefore correct: the public
  surface must support both `complementaria` and `sustitutiva`.

## codebase findings

### filing

- `aeat.application.filing` currently exposes only original draft builders and strict draft
-level types: `FilingDraft`, `FilingValue`, `FilingDraftStatus`.
- `130` ends in payable casilla `07`, `303` in result casillas `69` and `71`,
  and `390` in annual-result casillas `86` and `95` depending on the schema.
- There is no amendment schema, no amendment builder, and no public export for
  a prior-filing delta.

Implication:

- `src/aeat/application/filing/_complementaria.py` is the correct place for the new strict
  pydantic v2 amendment types and the builder function.
- The public package root should re-export only the issue-mandated public
  surface from `aeat.application.filing`.

### submission

- `aeat.adapters.outbound.aeat.export` persists `SubmittedFiling` records as JSON under
  `settings.aeat_submissions_dir`; there is no DB-backed submission repository.
- `SubmissionEngine` already owns the live/dry-run contract and the persistence
  helper.
- `Modelo130Submitter` only fills ordinary casilla inputs and clicks the final
  submit button; it does not yet model complementaria-specific controls.

Implication:

- Amendment submission can safely reuse the existing file-based persistence
  substrate and extend it with a parallel strict model for amendment
  submissions.
- The issue note about stubbing the transport gap is necessary: the amendment
  engine can ship even if the browser submitter lacks a trustworthy
  complementaria toggle abstraction.

### storage and prior-filing lookup

- `aeat.adapters.persistence.storage` on `main` is currently the SQLAlchemy-backed repository for
  model/catalogue records, not for filed returns.
- The real persisted filing history on `main` is file-based:
  `aeat.application.filing` drafts under `aeat_drafts_dir`, `aeat.adapters.outbound.aeat.export`
  submissions under `aeat_submissions_dir`, and synthetic historical fixtures
  under `aeat.domain.testing`.
- `aeat.domain.testing` already carries historical complementaria fixtures with
  `complementaria_of`, which is useful as synthetic ground truth for unit tests
  but is not the production persistence surface.

Implication:

- The issue text saying "read previously submitted filings from the storage
  layer" should be implemented against the existing persisted submitted-filing
  records rather than by forcing a new SQLAlchemy filing repository into #93.
- A thin amendment-store helper inside the existing file-backed filing/submission
  substrate is lower-risk than introducing a new DB feature.

### justificante and audit trail

- `aeat.domain.justificante.Justificante` already provides `csv`, `modelo`, `period`,
  and AEAT presentation metadata.
- Issue `#82` requires every persisted record to preserve provenance and to use
  Protocol stubs for in-flight Track B integrations.

Implication:

- The amendment engine should persist `original_csv` from the prior
  justificante/submission record and keep the human `reason` at the
  `CasillaChange` level.
- Any optional audit-trail adapter should be injected via a local Protocol
  rather than by importing `aeat.domain.financial.audit`.

## implementation constraints derived from the issue set

- Stay out of `aeat.adapters.outbound.aeat.auth`, `aeat.adapters.outbound.aeat.browser`, and `aeat.status` because branches
  `#94` and `#95` own them.
- Do not change AEAT site-health parsing or certificate logic.
- `AEAT_LIVE_TESTS_ENABLED` must gate live tests via
  `aeat.entrypoints.cli._live.requires_live_enabled()`.
- The "repeat the 14-bullet list from SLOT A1 verbatim" instruction could not
  be resolved from fetched issue/thread context or repo search. The controlling
  local conventions therefore remain the checked-in `AGENTS.md`,
  `.codex/rules/*`, and the issue's own explicit scope constraints.

## recommended architecture

- Introduce a new strict amendment schema in `aeat.application.filing` rather than trying
  to overload `FilingDraft`.
- Compute amendments from a prior persisted `SubmittedFiling` plus a new set of
  casilla inputs, using the existing draft builders to obtain the new absolute
  casilla values and then deriving a `CasillaDelta`.
- Define a per-model liability anchor map:
  `130 -> 07`, `303 legacy -> 69/71`, `390 -> annual result / replacement
  semantics`.
- Enforce legal invariants centrally:
  `complementaria` may only increase payable liability or reduce refund /
  compensation; `390` maps to `sustitutiva`; `303` at or after the 2024 cutover
  should raise a gap error because the legal path is `rectificativa`.
- Extend `aeat.adapters.outbound.aeat.export` with a parallel amendment-submission record and
  engine method, but let the browser submitter path degrade to a typed "gap"
  error or stub where the current `Modelo130Submitter` abstraction cannot
  safely express the AEAT complementaria branch.

## primary sources

- BOE consolidated `Ley 58/2003`:
  https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186
- BOE consolidated `Real Decreto 1065/2007`:
  https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984
- BOE `Orden HAC/819/2024` for `modelo 303`:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-16129
- BOE `Real Decreto 117/2024` introducing `artículo 74 bis` IVA:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-1771
- AEAT `Modelo 130` record design:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_100_199/archivos/dr130.08.pdf
- AEAT `Modelo 390` instructions:
  https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/instr390.pdf
