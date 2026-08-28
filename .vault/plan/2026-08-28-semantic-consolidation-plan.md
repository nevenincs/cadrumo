---
tags:
  - '#plan'
  - '#semantic-consolidation'
date: '2026-08-28'
tier: L2
related:
  - '[[2026-08-28-semantic-consolidation-research]]'
  - '[[2026-08-28-semantic-consolidation-cli-payload-projection-adr]]'
modified: '2026-08-28'
body_schema: body-v2
body_hash: 'sha256:007c237b460fbc224adcd948ea6b8b92e0ebf42ce9f3ccc2a5111a8ac17924ab'
---
# `semantic-consolidation` plan

## Description

## Steps

### Phase `P01` - Retire the duplicated lazy re-export resolvers

Six package namespaces carry a PEP 562 __getattr__ resolver, four of them byte-identical in behaviour. This is duplication and an independent rules breach: package namespaces must be inert and export maps are prohibited. Closed first because it removes code rather than reconciling it, and because every later phase reads imports that these resolvers currently obscure.

### Phase `P02` - Reconcile the CLI payload models against the models they restate

116 payload classes under entrypoints/cli duplicate a model in application, domain or adapters, restating at least 715 annotated fields. The ruling this phase needs is whether a CLI payload is a legitimate wire contract or a copy; that ruling is an ADR, and the reconciliation itself is model work requiring judgement about constraint shape rather than mechanical rehoming.

### Phase `P03` - Consolidate the repeated secure-repository configuration shape

Eleven repository classes declare the identical namespace, payload_type, schema_version and sensitivity quartet. The question this phase answers is whether they are eleven restatements of one configuration shape or eleven legitimately distinct repositories that share four field names, and the answer decides whether a shared base is a consolidation or a false merge.

### Phase `P04` - Close the confirmed single-function duplicates

Behaviour-fingerprint matches that are small, self-contained and mechanically rehomable once a canonical home is ruled: the uppercase-alphanumeric code validator across domain auth and the CLI payloads, the passphrase strength renderer across two TUI screens, the projection row selector across M200 and M296, the snapshot lister across borrador and justificante, and three identical secure-persistence constructors.

### Phase `P05` - Adjudicate the enum-subset rebuilt groupings

Fifty-two enum-subset clusters at two to six sites, each a candidate partition of a closed axis stated more than once. Every one needs the substitutability pre-filter before collapse, because two modules naming the same members for genuinely different rules must stay apart. The home-office family grouping closed earlier is the worked precedent for both the fix and the gate.

## Parallelization

## Verification
