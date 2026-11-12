---
tags:
  - '#adr'
  - '#informativa-party-name'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:a220f0db25ff8eb0b19d193dddd97bfff5ccc42a325e5977e33fb5184f6a7e7e'
related:
  - "[[2026-11-11-informativa-party-name-adr]]"
  - "[[2026-11-11-informativa-party-name-research]]"
---
# `informativa-party-name` adr: `M193 pending-record name amendment` | (**status:** `proposed`)

## Problem Statement

The accepted ADR `2026-11-11-informativa-party-name-adr` says under Migration that "the M193 placeholder name and the ledger-payment 256-character bound stop feeding exports". That holds for the 256-character bound. It does not hold for the Modelo 193 pending-collection record, because the design itself fixes that record's name. The 2024-and-later design (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf.extracted.md:858-882`) covers position 117 PENDIENTE, for claves A, B or D only. When that field is marked, the record carries "N.I.F. PERCEPTOR: 999 999 999", "N.I.F. REPRESENTANTE: 999 999 999" and "APELLIDOS Y NOMBRE, RAZÓN SOCIAL O DENOMINACIÓN: VALORES PENDIENTE DE ABONO". The earlier design prints the same text (`07-193-orden-eha-3377-2011-de-1-de-diciembre-512-kb-pdf.pdf.extracted.md:1076`). Read literally, the accepted sentence would stop the export from writing a value the design requires.

## Considerations

- The pending record names no third party. The text is the design's content for a holder who has not come forward, not a name the operator states, so the declared-name door has nothing to ask.
- The landed code already keeps the prescribed text. `src/cadrumo/domain/calculations/registry/withholding_party_rows.py:31-63` declares the NIF and name the design fixes, and `is_prescribed_pending_record` recognises the record only when NIF, name and the PENDIENTE flag all agree. `src/cadrumo/application/filing/tests/test_modelo_193_perceptor_devengo_bytes.py` proves the bytes against the printed design.

## Considered options

- **Apply the sentence literally: the pending record refuses until a name is declared. Rejected.** No party exists whose name could be stated, and any stated value other than the prescribed text would contradict the design.
- **Amend the Migration sentence to except the design-prescribed pending record. Chosen.** It matches the design and the landed code, and it narrows the exception to one record shape.

## Constraints

- Only the Modelo 193 record whose PENDIENTE field is marked, under claves A, B or D, with NIF 999999999 and the name VALORES PENDIENTE DE ABONO, is excepted. The text comes from the design's own content, carried where the design is declared, and no frontend authors it.
- Every other 193 perceptor and gasto row reads the declared filing name and refuses through the door when it is missing, as the accepted ADR rules. The 256-character ledger-payment bound still stops feeding exports.
- A design edition that changes or drops the prescribed text changes the exception with it.

## Implementation

We will amend the Migration paragraph of `2026-11-11-informativa-party-name-adr` in place, keeping the accepted wording and adding a dated note. The note will say that the Modelo 193 pending-collection record keeps the design-prescribed name and NIF, which do not pass through the declared-name door, and that only the ledger-payment bound and free-text placeholder names stop feeding exports. No code change is needed. The landed `is_prescribed_pending_record` path and its byte test already implement this.

## Rationale

The design states the content of this field for this record. Exporting anything else, or refusing for want of a declaration no party can make, would make the fichero non-conforming.

## Consequences

- The accepted record and the landed code agree. A later reader sees no instruction to remove the prescribed name.
- The exception is keyed to the design's own conditions, so it does not open a path for other placeholder names.
