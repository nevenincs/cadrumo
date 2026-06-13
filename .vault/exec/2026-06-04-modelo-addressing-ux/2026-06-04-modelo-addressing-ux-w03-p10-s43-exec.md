---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S43'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W03.P10.S43 adjacent command and ID-linkage classification

Scope:
- `.vault/exec/2026-06-04-modelo-addressing-ux`

## Description

- Run W05 groundwork inventory with `rg` over source locales and docs for raw work-unit and calculation-revision ID leakage.
- Run W05 groundwork discovery with `fd` over modelo, work, revision, reconcile, project, compare, locale, quickstart, and filing-spine surfaces.
- Run W05 groundwork semantic discovery with `vaultspec-rag` for operator-facing raw-ID exposure, adjacent CLI commands, and internal pointer persistence.
- Classify adjacent commands, application services, CLI payloads, help/locales, docs, and exact-ID escape hatches against the accepted natural-key modelo addressing ADR.
- Preserve the ADR boundary that internal content-addressed IDs remain authoritative for audit, replay, storage, and machine consumers.

## Outcome

The classification matrix below is the required W03.P10.S43 record and also captures W05 inventory groundwork. W05 final closure steps remain open because this pass inventories coverage before implementation verification.

| Surface | Primary files | Classification | Required action |
| --- | --- | --- | --- |
| Work target selector | `src/aeat/application/modelo/_selectors.py` | Product-critical natural-key boundary | Keep exact `work_unit_id` escape hatch, but make active bucket/profile plus modelo, filing year, and period the common resolver. Resolver must search visible filing target before selecting or creating exact registry target. Ambiguity must refuse with candidates. |
| Work unit persistence | `src/aeat/domain/modelos/_work_unit.py`, `src/aeat/application/modelo/_revision_persistence.py`, `src/aeat/application/modelo/_actions.py` | Internal exact-ID authority | Keep content-addressed IDs and pointer fields authoritative. Standardize current pointer advancement on calculation and filed pointer advancement on filing/import/amendment flows. |
| Calculation revision persistence | `src/aeat/domain/modelos/_calculation_revision.py`, `src/aeat/application/modelo/_revision_persistence.py`, `src/aeat/application/modelo/_actions.py` | Multiple revisions under one work unit | Preserve immutable calculation attempts. Do not collapse revisions into a singleton. Add command-specific defaults through selectors rather than generic latest. |
| `work create` / future `work start` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py`, `src/aeat/application/modelo/_selectors.py` | Natural-key now | Make idempotent for active visible filing target: resume existing active unit, create if none exists, refuse if multiple active candidates remain after resolver axes. |
| `work calculate` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py`, `src/aeat/application/modelo/_revision_persistence.py` | Natural-key now | Accept modelo/year/period on the common path. Resolve active work unit, create a new calculation revision under it, and update `current_calculation_revision_id`. Keep raw `work_unit_id` as advanced exact addressing. |
| `work verify` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py` | Natural-key plus selector now | Default to the resolved work unit's `current_calculation_revision_id` only when it is a draft revision. Support explicit selectors and exact `calculation_revision_id` escape hatch. |
| `work file` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py`, `src/aeat/application/modelo/_revision_persistence.py` | Natural-key plus selector now | Default to current verified-complete revision, not arbitrary latest draft. Keep exact `calculation_revision_id` for advanced filing and audit replay. |
| `modelo export` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_export.py` | Natural-key plus selector now | Resolve by visible filing target on common path. Default to current filed revision when available, otherwise current verified-complete revision if policy permits. Refuse draft export unless explicit command policy allows draft approval. |
| `work revisions` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/entrypoints/cli/_modelo_payloads.py` | Natural-key discovery now | List revisions for visible filing target without requiring raw `work_unit_id`. Continue allowing exact ID filtering for machine consumers. |
| `work revision` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/entrypoints/cli/_modelo_payloads.py` | Natural-key selector plus exact-ID escape hatch | Support `--select current`, `latest-draft`, `latest-verified`, and `filed` under a natural target. Keep direct `calculation_revision_id` display for exact audit lookup. |
| `work status` | `src/aeat/entrypoints/cli/_modelo.py` | Natural-key now | Show active work unit and pointers for visible filing target. Exact ID may remain for historical or discarded work unit inspection. |
| `work rename` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py` | Natural-key now | Rename active filing workspace by visible filing target. Exact ID remains necessary for discarded/historical unit renaming if policy allows it. |
| `work discard` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py` | Natural-key now | Let users explicitly abandon the active filing workspace without copying IDs. Refuse ambiguous candidates and retain `--yes` confirmation. |
| `work history` / `modelo history` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_history.py` | Natural-key now for filing workspace history | Display lifecycle by visible filing target. Keep exact `work_unit_id` for historical audit lookup and bucket event replay. |
| `work compare-taxation` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_taxation_comparison.py` | Natural-key now | Resolve active filing target for operator comparison. Exact ID remains an advanced path for historical comparison. |
| `modelo reconcile` / `reconcile-from-justificante` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_reconcile.py`, `docs/how-to/reconcile.md` | Natural-key now | Stop requiring a copied `work_unit_id` for common reconciliation. Resolve the active filing workspace by modelo/year/period, with exact ID retained for imported or historical evidence matching. |
| `modelo project` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/state_projection.py` | Adjacent selector semantics audit | Audit for arbitrary latest revision selection and raw-ID output emphasis. Projection may remain a discovery command, but any follow-up action guidance must route through natural target commands. |
| `modelo compare` | `src/aeat/entrypoints/cli/_modelo.py` | Adjacent selector semantics audit | Audit year/period comparison defaults so they use command-specific revision policy instead of raw latest revision when a filing target is implied. |
| `work runs` / `work resume` | `src/aeat/entrypoints/cli/_modelo.py` | Exact run-ID surface with work-unit compatibility | Keep workflow run IDs as exact operational handles. Do not present work-unit IDs as the normal way to recover a modelo filing workflow when natural target resolution can find it. |
| `work amend` | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/application/modelo/_actions.py` | Filed-record exact surface for now | Amendment currently starts from a filing record, not a visible filing target. Keep exact filing-record addressing until a filing-record natural selector is designed, but make resulting work/revision linkage obey pointer standards. |
| External/imported filing flows | `src/aeat/application/modelo/_actions.py`, `src/aeat/domain/modelos/_filing_record.py` | Internal exact IDs plus natural-key candidate for future CLI | Preserve imported/filed history as auditable records. If exposed to operators, resolve the target by visible filing key and refuse if imported/filed history creates ambiguity. |
| CLI payload schemas | `src/aeat/entrypoints/cli/_modelo_payloads.py` | IDs retained for machine consumers | Keep IDs in structured JSON output. Text/table output should include human target fields prominently and avoid teaching copy/paste ID chaining as the default workflow. |
| CLI validation and type hints | `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py` | Exact-ID escape hatch guard | Retain validators for advanced exact IDs. Update user-facing hints so they redirect to natural target commands rather than telling users to generate and pass another raw ID. |
| Locales | `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, `src/aeat/locales/ca.yml`, `src/aeat/locales/hu.yml` | Must change after CLI behavior lands | Replace common-path help text that says work-unit ID or calculation-revision ID is required. Keep internal error messages for exact-ID escape hatches and machine-facing not-found cases. |
| User docs | `docs/getting-started.md`, `docs/tutorials/index.md`, `docs/how-to/quickstart.md`, `docs/how-to/filing-spine.md`, `docs/how-to/modelo-303.md`, `docs/how-to/modelo-390.md`, `docs/how-to/reconcile.md`, `docs/how-to/index.md` | Must change through documentation workflow after CLI behavior lands | Rewrite common tutorials around modelo/year/period and selector defaults. Remove instructions to copy `work_unit_id` and `calculation_revision_id` through the normal flow. |
| Generated CLI reference | `docs/cli/app.rst` | Generated output, do not hand-edit | Regenerate after CLI command signatures/locales change. Treat remaining raw-ID arguments in generated docs as a final W05 leakage gate. |
| Tests | `src/aeat/entrypoints/cli/test_modelo_work_ux.py`, `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`, `src/aeat/entrypoints/cli/test_modelo_work_id_type_hint.py`, `src/aeat/entrypoints/cli/test_modelo_export_verb.py`, adjacent reconcile/project/compare tests | Real-behavior enrollment required | Cover idempotent work start/create, no duplicate active workspace, ambiguity refusal, selector defaults, exact-ID escape hatches, and no user-facing raw-ID dependency in the common path. |

W05 groundwork exact leakage inventory found current raw-ID common-path exposure in:

- `docs/getting-started.md`
- `docs/tutorials/index.md`
- `docs/how-to/filing-spine.md`
- `docs/how-to/index.md`
- `docs/how-to/modelo-303.md`
- `docs/how-to/modelo-390.md`
- `docs/how-to/quickstart.md`
- `docs/how-to/reconcile.md`
- `docs/cli/app.rst`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

W05 groundwork discovery also identified the implementation blast radius:

- `src/aeat/application/modelo/_selectors.py`
- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/modelo/_revision_persistence.py`
- `src/aeat/application/modelo/_export.py`
- `src/aeat/application/modelo/_reconcile.py`
- `src/aeat/application/modelo/_history.py`
- `src/aeat/application/modelo/_taxation_comparison.py`
- `src/aeat/application/modelo/_result_summary.py`
- `src/aeat/application/state_projection.py`
- `src/aeat/domain/modelos/_work_unit.py`
- `src/aeat/domain/modelos/_calculation_revision.py`
- `src/aeat/domain/modelos/_filing_record.py`
- `src/aeat/domain/modelos/_repository.py`
- `src/aeat/domain/modelos/_calculation_repository.py`
- `src/aeat/domain/modelos/_filing_repository.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_work.py`
- adjacent CLI tests for work UX, natural-key, ID type hints, export, reconcile, projection, compare, history, calculate, and workflow resume.

## Notes

- No code, locale, generated docs, or user documentation files were changed in this step.
- W05 final gate steps remain open because the implementation is not complete in this slice.
- `vaultspec-rag` semantic search completed successfully and confirmed reconcile, export, revision display, payload, persistence, and pointer surfaces beyond exact `rg` matches.
