---
tags:
  - '#research'
  - '#taxpayer-profile'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:17d41e8f68bc862b6f04aa52ea3fe7d8675bc6e8d293004640b35d50ccefeeb9'
related: []
---

# `taxpayer-profile` research: `Census domain grounding`

How AEAT's census services divide taxpayer facts (researched 2026-09-21). These are domain distinctions for profile scope, not proof that Cadrumo implements every field.

## Findings

### Census facts are several families, not one record

AEAT's census services separately cover addresses, activities and premises, representatives, and tax circumstances. Its consultation guidance exposes activity start and end dates and obligations with their periodicity and status. What can be consulted depends on the taxpayer and on representation permissions. A profile therefore has to distinguish current configuration, imported census evidence and the context of an existing filing, and keep each fact's provenance and effective date where supported.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/censos-nif-domicilio-fiscal/tramites-censales-relacionados-empresarios-profesionales-retenedores/datos-censales.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/datos-censales.html
