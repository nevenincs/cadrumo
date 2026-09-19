---
tags:
  - '#audit'
  - '#repo-gate-integrity'
date: '2026-08-27'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f9a74c1f58abbd3ebf09583992da113a6687b4dea40022009d075526838193f9'
related: []
---

# `repo-gate-integrity` audit: `the identifier ratchet scanned the tooling tree, hiding eighteen bare fields`

## Scope

## Findings

## Recommendations

## Finding

 computed its
scan root as `Path(__file__).resolve().parents[2]`. That was correct while the
file lived under `src/`. When it was relocated into its dev family home
(`c0a7feef24`), the same upward arithmetic began naming `dev/` -- so the
ratchet has been scanning the TOOLING tree, not the product.

Nothing about the failure said so. Its free-text anchor reported
"module ... no longer exists" for a file that exists; its adjudications
reported as stale because no live field was ever seen; and its candidate
population was dev tooling.

Fixed in `b4bd112f89` by naming the repository root downwards and deriving the
source root from it, with an import-time refusal if that root is not the
package. Five adjudications whose modules had been promoted out of their
underscore names were followed to their current homes in `d0bb89f338` --
same model, field and reason in each case.

## What the repaired gate reports

Eighteen identifier-named model fields are declared bare `str` and are not
adjudicated. They are not new; they were unreachable while the root was wrong.

    src/cadrumo/application/filing/_producer_snapshot.py:540 Modelo210ContribuyenteFacts.foreign_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:543 Modelo210ContribuyenteFacts.tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:567 Modelo210DeclaranteFacts.tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:593 Modelo210DevolucionFacts.cuenta_titular_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:603 Modelo210GananciaInmobiliariaFacts.conyuge_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:626 Modelo210IngresoFacts.cuenta_titular_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:660 Modelo210PagadorFacts.tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/filing/_producer_snapshot.py:697 Modelo210RepresentanteFacts.tax_id: str | None [BARE] token=tax_id
    src/cadrumo/application/registry/_diff.py:78 RenumberedCasilla.continuidad_id: str [BARE] token=continuidad_id
    src/cadrumo/domain/calculations/registry/gasto193_bindings.py:56 Gasto193Observation.representative_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/domain/calculations/registry/support_matrix.py:149 ModeloRenameRecord.continuidad_id: str [BARE] token=continuidad_id
    src/cadrumo/domain/calculations/registry/withholding296_bindings.py:86 Withholding296Observation.representative_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/domain/calculations/registry/withholding_bindings.py:219 WithholdingObservation.representative_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/domain/calculations/registry/withholding_bindings.py:222 WithholdingObservation.spouse_or_unit_titular_tax_id: str | None [BARE] token=tax_id
    src/cadrumo/entrypoints/cli/_config_payloads.py:436 ConfigProfileAddRowResult.content_digest: str [BARE] token=content_digest
    src/cadrumo/entrypoints/cli/_modelo_payloads.py:489 WorkSelectResult.selected_work_unit_id: str | None [BARE] token=work_unit_id
    src/cadrumo/entrypoints/cli/_modelo_support_matrix_payloads.py:26 ModeloRenamePayload.continuidad_id: str [BARE] token=continuidad_id
    src/cadrumo/entrypoints/cli/_registry_diff_payloads.py:51 RenumberedCasillaPayload.continuidad_id: str [BARE] token=continuidad_id

Twelve are tax identifiers on Modelo 210 producer facts and on withholding /
gasto observation models. Two more are `continuidad_id` on registry rename
records and their CLI payloads, and the rest are a content digest, a work-unit
id and a casilla continuity id.

## Why this is recorded rather than fixed here

Each site needs one of two things, and both are judgements rather than
mechanics: type the field with its `core.identity` alias, or record a
falsifiable adjudication with a stated reason. Typing a tax identifier on a
FILING producer path changes what the model will accept, and the existing
adjudications in this gate show the shape of the argument that has to be made --
several exist precisely because a value is carried as SUPPLIED rather than as
validated, and refusing it at the model boundary would turn a recoverable
refusal into a construction error.

Making that call for eighteen sites, eight of them on the Modelo 210 filing
path, is not something to absorb inside an unrelated tick.

## Status

Open. The gate is live again and will hold the line at eighteen; each site
needs an adjudication or an alias.
