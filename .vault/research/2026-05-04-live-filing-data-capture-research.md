---
tags:
  - '#research'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-research]]'
---



# `calculation-truth-registry` research: `live filing data capture`

## Question

The registry requires previous-filing facts and live AEAT cross-reference
evidence. The live-read backend must therefore answer whether AEAT can provide
full filed-declaration data, not only filing existence, CSV, timestamp, and
receipt totals.

## Current Codebase Facts

`src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` implements Cl@ve
Movil authentication and persists a Playwright storage-state session after a
human phone approval. The session is a read credential only; downstream readers
must still enforce no-write policy.

`src/aeat/adapters/outbound/aeat/sede/_declarations.py` drives AEAT's
authenticated `Consultar declaraciones presentadas` surface. It can query one
modelo and tax year, parse register rows into typed `Declaration` records, and
capture the justificante PDF behind the row's `Ver` link. The parsed row carries
modelo, ejercicio, period, expediente, estado, presentation timestamp,
justificante-link presence, and submitted-file/archive-link presence.

`src/aeat/adapters/outbound/aeat/sede/_walker.py` walks `Mis Expedientes`,
resolves a CSV verifier link, and captures a justificante PDF. This is useful
as a second read-only path, but it is a procedures tree and not the canonical
filed-declarations register.

`src/aeat/adapters/inbound/justificante/_parser.py` and
`src/aeat/adapters/inbound/justificante/_extract.py` parse receipt metadata:
CSV, modelo, period, ejercicio, presentation id, timestamp, tax id, totals,
verification URL, source path, and source hash. This parser does not currently
recover the full casilla table.

`src/aeat/adapters/inbound/declaracion/_parser.py` resolves template identity
but then fails because registry-backed casilla extraction is not implemented.
That boundary is correct as a refusal, but it leaves the live-read backend
unable to normalize full filed-declaration data into registry-shaped
observations.

`src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`
can extract a limited Modelo 100 summary block, including activity and payment
summary casillas. It is not a general declaration parser and must not become a
filing-grade authority outside registry extraction profiles.

## AEAT Surface Facts

AEAT's filed-declarations consultation help describes three outputs from the
presented-declarations query: copy of the declaration, download of the submitted
file, and justificante. The submitted-file download is described as a TXT file
containing the declaration. For Modelo 130, AEAT's own help describes export as
BOE-format `.130` suitable for import/presentation, and the final PDF as a
document that includes presentation information and the full declaration copy.

References:

- https://sede.agenciatributaria.gob.es/Sede/irpf/declaraciones-presentadas/consulta-declaraciones-presentadas.html
- https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/consulta-declaraciones-presentadas.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/presentacion-declaraciones-ayuda-tecnica/modelo-130/presentacion-electronica-modelo-130.html

## Design Finding

The live reader is incomplete. Authentication and register traversal already
exist, but the backend stops at filed-row metadata and justificante capture. A
registry-grade live read must capture every available filed-declaration artefact:
register metadata, submitted TXT or model-specific file, full declaration copy
PDF where available, justificante PDF, source URL, retrieval timestamp, and
content hashes.

The submitted TXT/model file should be preferred for machine reading because it
is the closest structured representation of filed casillas. The full
declaration PDF is a required fallback and evidence artefact. The justificante
is provenance evidence and payment/receipt metadata, not a complete
calculation-data source by itself.

## Implementation Implications

The live-read backend needs one normalized output shape for filed-declaration
observations. It must preserve source artefacts and hashes, parse casilla values
into registry ids, preserve metadata separately, and classify extraction
coverage. It must never mark a declaration observation filing-grade unless the
target registry snapshot validates the modelo, revision, period, extraction
profile, required casillas, and source evidence.

The read-only guard must cover the declaration-register form drive, the
justificante download, the submitted-file download, the full declaration copy
download, and any PDF/TXT/archive fetch. Allowed remote operations are limited
to read navigation and read downloads. Presentation, signing, payment, direct
debit, server-side save, amendment, cancellation, and document submission remain
forbidden.
