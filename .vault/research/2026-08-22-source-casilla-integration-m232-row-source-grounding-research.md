---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:3a1f8a399585d4a0d7908d336652ab51b77ec1f97497f2140a8efb52cdf0a75f'
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

# `source-casilla-integration` research: `m232 row source grounding`

Modelo 232 is informative, not a tax calculation. Official evidence supports a row family at counterparty / operation-type / valuation-method grain, but not a pre-existing Cadrumo secure repository as authority; S93 must select explicit worksheet ingress or retain deferral.

## Findings

### Official reporting grain prevents a generic ledger owner

Article 3.1 of Orden HFP/816/2017 requires separate income/payment reporting, no compensation, grouping by related party/entity, operation type, and valuation method; operations with different methods are separate. Required facts include identity/name/residence, relationship type, amount before reductions and excluding IVA. https://www.boe.es/buscar/doc.php?id=BOE-A-2017-10042

Thus S93 cannot resolve arbitrary ledger transactions or merge merely by counterparty. The current observation lacks direction and relationship-type fields, and its helper groups `(party, country, kind, method)` while summing amounts: gaps that require an authority decision, not defaults. `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:69`

### Existing row assembly is not ownership

The registry/worksheet path can assemble M232 cells into `RelatedPartyOperationObservation`, with a synthetic worksheet source id; the source mesh explicitly leaves `RELATED_PARTY_OPERATION` deferred. Official semantics do not establish a secure Cadrumo source for direction, relationship type, or valuation method. `src/cadrumo/application/calculations/_row_set_assembly.py:680` `src/cadrumo/application/aggregation/_source_mesh.py:290`

### Bounded S93-S95 proof program

S93 may remove deferral only for one established ingress owner preserving every official axis, stable source identity, grouping, and collision/override refusal. S94 must prove real worksheet export/pull through S90, encrypted revision read-back, mutation refusal for erased direction/method distinctions, replay/review, and repeated official-record export. S95 may close the census only after formal review confirms those facts; the present revision expressly has no projection-row endpoint, so export support cannot be inferred. `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml:73`

## Sources

- https://www.boe.es/buscar/doc.php?id=BOE-A-2017-10042
- `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py:69`
- `src/cadrumo/application/calculations/_row_set_assembly.py:680`
- `src/cadrumo/application/aggregation/_source_mesh.py:290`
- `src/cadrumo/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/revision.toml:73`
