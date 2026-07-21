---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S01'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# author the official M210 tipo-de-renta code list (01, 02, 27, 28, 29, 33, 35, ...) as declared registry data on the 2025 revision, each code row citing its bundled Orden EHA/3316/2010 and AEAT M210 instructions grounding

## Scope

- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters`

## Description

- Author the official Modelo 210 tipo-de-renta code list as declared registry data on the 2025 revision in a new `m210-tipo-renta-code-2025` parameter (`keyed_bracket_table`), so the code set carries the canonical registry legal-grounding gate.
- Declare only the 26 codes whose rate concept is grounded against the bundled corpus (`legal_refs` = TRLIRNR art-25.1.a / art-25.1.b / art-25.1.f + art-13.1.h; `source_citations` on the AEAT Modelo 210 instructions carrying the HOJA INFORMATIVA 210 table). Keep the establishing Orden EHA/3316/2010 as a `source_ref` reference (layout_authority tier, so it cannot be a source_citation).
- Leave the 11 special/cánones codes (08/09/10/11/12/13 cánones + asistencia-técnica, 19 reaseguros, 20 navegación, 27 imposición-complementaria, 31 premios) fetch-gated and undeclared — the bundled TRLIRNR is a Phase-1 extract carrying art 25 a/b/f only, so their rate is not bundle-verifiable and force-mapping any would fabricate a rate.

## Outcome

The 2025 revision declares the 26 rate-grounded official tipo-de-renta codes as registry data, and the full `validate_registry` passes with the codes carrying the same legal-grounding gate every registry value does — the gate caught and forced correction of a real issue (the Orden EHA/3316/2010 source is `layout_authority` tier and cannot back a source_citation). Landed in commit `0ce6abfafc` (Slice A S01+S02, 7 files, explicit-pathspec, zero-foreign).

## Notes

The `keyed_bracket_table` `value` column is a sentinel presence-marker (`1`) — a documented cleanliness item, not a correctness issue, recorded in the parameter's "KNOWN ITEM" comment block. If code-review pushes on the type-shape, the clean resolution is a categorical / string-valued parameter type (representation C) with the grounding staying registry-resident; do not rebuild it pre-emptively.
