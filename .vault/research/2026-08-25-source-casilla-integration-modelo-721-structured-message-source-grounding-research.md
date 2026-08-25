---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c809414e2111b22be3afcaec1f93debeb6dc46ac1b13e8df90f0009d9abf3dfd'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-25-source-casilla-integration-m721-structured-message-source-owner-deferral-adr]]'
---

# `source-casilla-integration` research: `modelo 721 structured-message source grounding`

This research establishes the factual boundary for Modelo 721 source facts,
casillas, and value arrival in the two selected annual structured-message eras.
The BOE annexes define declaration targets and their distinct annual field
grammars; they do not identify an acquisition source, a secure source owner, or
provenance and absence semantics. The model-scoped ADR must choose the
connectivity disposition without treating the wire contract or an export plan as
such evidence.

## Findings

### Two exact, finite annual message eras define the target facts

The original Modelo 721 annex in BOE-A-2023-17429 / Orden HFP/886/2023 is a
294,687-byte BOE primary package with SHA-256
`afc706b7c41a34a3cd119ea6221dc2091eac73e64669189b93d6eeed43821acb` and
an exact 2023-01-01 through 2023-12-31 applicability window. It requires
annual computer messages, provides the message fields, and defers the transport
format and design to the AEAT Sede. The final provision limits its first
application to exercise 2023. `src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml:130`
`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2023-17429-modelo-721-layout.pdf.corpus_text.json:1`

BOE-A-2024-27528 / Orden HAC/1504/2024 article 9 substitutes the annex, and
its final provision limits the new package to exercise 2024 declarations filed
in 2025. The shipped 827,110-byte BOE primary package has SHA-256
`27995a7285f61a3a3ff2ddd259d9b252143d2ef6fc5d999936738bbd8b116a31` and
the exact 2024-01-01 through 2024-12-31 window.
`src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml:143`
`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2024-27528-modelo-721-layout-amendment.pdf.corpus_text.json:1`

The independently selected loaded revisions agree: only `2023/0A` and
`2024/0A` exist, both at applicability grade. No source fact or conclusion in
this research extends to 2025 or a later exercise.
`src/cadrumo/domain/calculations/registry/tests/test_modelo_721_registry.py:23`

### Each era requires a repeated custody-and-valuation fact, not five manual fields

Both annexes require the transmission/exercise/schema and declarant/contact
envelope, a stable repeating-detail identifier, the declarant's ownership role,
custodian identity and address branches, currency identity, the number of
units, EUR unit valuation, valuation origin, end-of-condition date where
applicable, year-end balance, and an origin/status value. The 2023 annex names
the status alternatives as first declaration, previously declared after the
statutory increase, and loss of the declared condition. The substituted 2024
annex is a separately scoped grammar; the established structured-message
reference records an explicit `ValorMoneda` precision change rather than
claiming cross-era interchangeability.
`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2023-17429-modelo-721-layout.pdf.corpus_text.json:1`
`src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2024-27528-modelo-721-layout-amendment.pdf.corpus_text.json:1`
`.vault/reference/2026-08-24-registry-completeness-closure-modelo-721-structured-message-design-and-filing-boundary-reference.md:24`

Accordingly, the native fact grain for either selected era is at least
declarant, exercise and revision, unique detail identity, declarant role,
custodian identity/location, virtual-currency identity, number of units, unit
EUR value and valuation origin, year-end balance, and the status/date branch.
The supplied status branch does not make an omitted source row an authoritative
absence, and no source record in the repository supplies a distinct absent,
inapplicable, zero, or supplied-value state for this grain. Those meanings
cannot be recovered by treating a missing manually entered casilla or a message
field as a source event.

### The loaded manual and secure-observation paths are not a source owner

Each selected revision carries seven casillas only: two informational header
facts and five manual custody/token/balance fields. It has no bindings; its
loaded source references are the BOE form-spec and the procedure page, which
are declaration authority rather than a carrier of an acquired taxpayer fact.
`src/cadrumo/_data/registry/aeat/modelos/721/revisions/2023/revision.toml:1`
`src/cadrumo/_data/registry/aeat/modelos/721/revisions/2024/revision.toml:1`
`src/cadrumo/domain/calculations/registry/tests/test_modelo_721_registry.py:86`

The existing threshold-continuity test persists and reloads manually constructed
ordered observations through the encrypted calculation-observation repository.
That is a genuine secure retention route for the currently typed declaration
observations and must remain available as a direct/manual path. It is not a
non-lossy owner of either complete official detail fact: the test starts with
operator-supplied values, does not acquire custodian or valuation evidence, and
does not attach capture provenance, a durable external source identity, or an
explicit source absence state. The verify-time regression independently keeps
M721 without an evidence binding, so the same observation cannot be falsely
used as both evidence and declaration.
`src/cadrumo/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py:349`
`src/cadrumo/application/modelo/tests/test_modelo_720_redeclaration_e2e.py:413`

The earlier accepted `2026-06-02-modelo-721-cripto-data-fidelity-adr` remains
the decision home for threshold-continuity and ordered manually entered
observations. It does not decide a complete pre-filing custodian/value source
owner for either finite structured-message era, so it cannot authorize the
source-connection question here.

### SOAP/XML and export work establish no source acquisition route

The AEAT procedure page is an official guidance source, hash-pinned as
`99e6600135617e9a51c4e61cfb3c583839a4ffe6e81a3953b054a152d7db001c` for
the retrieved 37,997-byte page. The technical reference records AEAT's
WSDL/XSD and validation publication, but also that no Modelo 721 service
package is enrolled or hash-pinned in the source catalogue.
`src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml:155`
`.vault/reference/2026-08-24-registry-completeness-closure-modelo-721-structured-message-design-and-filing-boundary-reference.md:37`

Those materials specify a submission target. They do not establish that
Cadrumo acquired an authoritative custodian balance, market valuation, ownership
condition, provenance, or absence. The canonical export plan leaves S97--S99
open precisely for distinct 2023/2024 technical inventory, canonical local
serializer, and emitted-payload proof; none supplies an M721 source fact or
owner today. Exact searches likewise find no M721 binding, source-mesh
resolver, source-connectivity census row, producer, semantic map, or model
serializer to redeclare.
`.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md:157`
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:447`
`.vault/audit/2026-08-24-registry-completeness-closure-s80-correction-rereview-audit.md:28`

The outstanding ADR question is therefore whether the real two-era source
domain can be connected without a non-lossy owner. The evidence supports neither
a present connection nor a not-applicable classification: it identifies a real,
repeated source fact while leaving its secure ingress and full lifecycle
unproven.

## Sources

- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-17429
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-27528
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI55.shtml
- `src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml:130`
- `src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml:143`
- `src/cadrumo/_data/registry/aeat/legal/monedas-virtuales.toml:155`
- `src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2023-17429-modelo-721-layout.pdf.corpus_text.json:1`
- `src/cadrumo/_data/manual_corpus_text/normatives/pdf/boe-a-2024-27528-modelo-721-layout-amendment.pdf.corpus_text.json:1`
- `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2023/revision.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2024/revision.toml:1`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_721_registry.py:23`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_721_registry.py:86`
- `src/cadrumo/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py:349`
- `src/cadrumo/application/modelo/tests/test_modelo_720_redeclaration_e2e.py:413`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:447`
- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-721-structured-message-design-and-filing-boundary-reference.md:24`
- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-721-structured-message-design-and-filing-boundary-reference.md:37`
- `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md:157`
- `.vault/audit/2026-08-24-registry-completeness-closure-s80-correction-rereview-audit.md:28`
