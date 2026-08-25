---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2a75d06047da62be10e0ef1f79cc0b8d43023309d7e8f7a4414cb8232f8d1c57'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `source-casilla-integration` research: `Modelo 296 withholding row source grounding`

The question is whether the existing encrypted withholding/perceptor owner can
be the authoritative source for Modelo 296 non-resident type-2 recipient rows.
The evidence supports the narrower position that it cannot: the current owner
and the typed candidate both lose mandatory M296 record identity and row grain.
It therefore favors preserving the existing refused, registry-blocked candidate
until a dedicated non-lossy route is grounded and accepted; an ADR or the
approved plan must make that decision.

## Findings

### Official row semantics require record-level identity, not only totals

The official M296 layout is the annually filed non-resident income/withholding
return. Its 2024 registry design is pinned locally as
`aeat-dr-296-2024` with SHA-256
`abec12e56073f8325b159c45a6b25de713bd53f8315c26c0f5243024f00d0378`;
the governing BOE order is pinned as `boe-modelo-296-form-layout` with SHA-256
`f5bdfa976ead9a08fdcb3c8cb3bb89543a19d80d6f756c4881780fe8df189b25`.
The official type-2 record includes recipient tax identity, representative,
natural/legal-person marker, name, country and income/withholding keys. More
importantly, its record identifier is a declarant-owned, unique key, and the
current AEAT note requires it to remain unique across the declarant's high
declarations and to remain associated with Annex A/B data. A row projection
that recomputes an ordinal cannot stand in for that identity.

The official AEAT procedure page is locally pinned as
`aeat-modelo-296-procedure` with SHA-256
`1acee493b408c9aa4d6300847c7561268fc41bdc704d36349468f67678012c54`.
The current AEAT 193/296 informative note is locally pinned as
`aeat-modelo-193-296-note-2025` with SHA-256
`d71fcd7ccd03d7f4ca205b418d4415a2bd74093ca95269b0aaa4fab05e02cf17`.

### The current M296 candidate is not a durable, non-lossy source

`Withholding296Observation` models a useful portion of the official recipient
fields, including a `source_id`; however,
`_build_withholding296_rows` groups observations by country, recipient NIF,
clave, and subclave, sums values, and creates a sorted ordinal
`registro_orden`. Thus multiple official detail records with the same grouping
key collapse, the declarant's actual unique record identifier is not retained,
and the Annex associations cannot be replayed. The row-set assembler creates
the observation `source_id` from its local row index and supplies a default
date, which is presentation plumbing rather than captured financial evidence.

The registry's 2024-and-later M296 revision deliberately records no formulas:
boxes 01--03 are declarant aggregations of their own type-2 rows and box 04 is
a conditional manual summary. The relation-prefill bindings for boxes 02/03 do
not establish a M296 recipient-row ingress. The fixed-width perceptor exporter
does repeat caller-populated profile rows, but its own producer-snapshot
contract says the caller population can disagree with the figure ledger. That
is an output path, not a direct/manual authoritative source for type-2 rows.

### The encrypted M180/193 retention store is not substitutable for M296

The existing encrypted `RetencionObservationRepository` is explicitly the
M180/M193 perceptor store. Its retention observation retains source kind/object
identifier, NIF/name, annual scheme, taxable base, withholding amount, and
accrual date. Its scheme catalogue has no M296 scheme, and no M296 calculation
resolver reads the encrypted set. Even a reuse of its encrypted envelope would
omit legal representative, recipient legal form, non-residence/country data,
IRNR clave/subclave and related conditional keys, the official record identity,
source-document/capture provenance, and revision/replay semantics. Encryption
alone cannot supply the required non-loss property.

The source-connectivity census consequently identifies
`rows.withholding296` as `registry_blocked` with a 2026-11-30 follow-up deadline
and 2026-12-31 expiry. Its source-kind taxonomy and typed assembler exist, but
no live registry binding, encrypted repository, revision/replay route, or
calculation source resolver owns them. The source-kind spelling itself is
consistent (`withholding296`); the dormant mismatch is semantic: the aggregate
grouping and synthetic identifier cannot satisfy the official record grain.

### Bounded route for reopening

Before an implementation step can connect the source, the accepted official
binding schema must cover the complete current type-2 row and applicable Annex
records. A separate encrypted financial owner, or an accepted extension proven
equivalent, must retain each original row without aggregation, its durable
official record identifier (or safely auditable original key before filing),
all conditional identity/country/income/withholding fields, capture and
source-document provenance, and an immutable record/revision identity.

The subsequent resolver must read that owner under `withholding296`, preserve
row multiplicity and actual values, and prove encrypted persistence, replay,
provenance, diagnostics, review, repeated-record export, and Annex association
end to end. Until then, a caller-populated projection or the legitimate manual
box 04 must not be represented as a connected M296 recipient-row source.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/irnr.toml:881`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2713`
- `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/revision.toml:1`
- `src/cadrumo/domain/calculations/registry/_withholding296_bindings.py:1`
- `src/cadrumo/application/calculations/_row_set_assembly.py:872`
- `src/cadrumo/application/aggregation/_retencion_observations_repository.py:1`
- `src/cadrumo/application/aggregation/_retenciones.py:55`
- `src/cadrumo/_data/source_connectivity/census.toml:332`
- `src/cadrumo/application/filing/_m296_projection.py:1`
- `src/cadrumo/application/filing/_producer_snapshot.py:274`
- https://www.boe.es/buscar/act.php?id=BOE-A-2008-18497&p=20240131&tn=1
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI22.shtml
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_24/DR_296_2024.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Tema/Declaraciones_informativas/2024/Notas_informartivas/Nota_informativa_193-296.pdf
