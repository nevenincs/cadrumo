---
generated: true
tags:
  - '#index'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-14-bindings-interface-hardening-reference]]'
  - '[[2026-06-14-bindings-interface-hardening-research]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P01-S01]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P01-S02]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P01-S03]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S04]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S05]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S06]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S07]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P03-S08]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P03-S09]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P03-S10]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P04-S11]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P04-S12]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P04-S13]]'
  - '[[2026-06-15-bindings-interface-hardening-plan]]'
---

# `bindings-interface-hardening` feature index

Auto-generated index of all documents tagged with `#bindings-interface-hardening`.

## Documents

### adr

- `2026-06-14-bindings-interface-hardening-adr` - `bindings-interface-hardening` adr: `bindings interface hardening: one validation contract, provenance parity, semantic disambiguation` | (**status:** `accepted`)

### exec

- `2026-06-15-bindings-interface-hardening-W01-P01-S01` - add a BindingAggregationOp StrEnum and a typed BindingAggregation pydantic model in core, then wire the typed aggregation field onto DataBindingDefinition replacing the free-form mapping
- `2026-06-15-bindings-interface-hardening-W01-P01-S02` - replace the ~10 ad-hoc op re-parses with one typed accessor and one declared per-family default, removing the divergent sum-vs-rows silent defaults
- `2026-06-15-bindings-interface-hardening-W01-P01-S03` - add typed-aggregation roundtrip and per-family default tests that fail if the typed op is dropped or a wrong family default is applied
- `2026-06-15-bindings-interface-hardening-W01-P02-S04` - introduce one canonical binding source-kind enum in core reconciling AggregationSourceKind and RowSetGroupingKind, realigning the related_party, atribucion and refund tokens to match enum values
- `2026-06-15-bindings-interface-hardening-W01-P02-S05` - derive every per-family source-kind frozenset from the canonical enum, fix the incomplete LEDGER_BINDING_SOURCE_KINDS, and reconcile every consumer into one accept-or-reject state per the retired-enum rule
- `2026-06-15-bindings-interface-hardening-W01-P02-S06` - wire the dead typed_enum schema field to a real consumer or delete it outright per no-legacy-compatibility, with the deletion test asserting no module reads it
- `2026-06-15-bindings-interface-hardening-W01-P02-S07` - add a taxonomy parity gate asserting the canonical source-kind enum equals the registry binding source set
- `2026-06-15-bindings-interface-hardening-W02-P03-S08` - define one validate(binding)->list[str] validator per source family registered in the single binding dispatch table alongside the selector model
- `2026-06-15-bindings-interface-hardening-W02-P03-S09` - lift the four detail-record family and previous_filing op/fact invariants to registry-build, routing each through selector_as_dict and preserving the underlying pydantic field error in the diagnostic
- `2026-06-15-bindings-interface-hardening-W02-P03-S10` - collapse the near-verbatim invoice and counterpart resolver and validator duplication to one shared implementation parameterised by source kind
- `2026-06-15-bindings-interface-hardening-W02-P04-S11` - run every family validator from the single dispatch table inside the registry-build section validator so all families are checked at snapshot build
- `2026-06-15-bindings-interface-hardening-W02-P04-S12` - add build-time rejection tests per family plus an anti-tautology proof asserting a malformed binding fails at build for each family, not only at resolve
- `2026-06-15-bindings-interface-hardening-W02-P04-S13` - fix any latent malformed registry TOML the new build gate surfaces so the full registry suite collects and builds clean

### plan

- `2026-06-15-bindings-interface-hardening-plan` - `bindings-interface-hardening` plan

### reference

- `2026-06-14-bindings-interface-hardening-reference` - `bindings-interface-hardening` reference: `bindings interface code anchors: validator dispatch, selector models, carrier and CLI payloads`

### research

- `2026-06-14-bindings-interface-hardening-research` - `bindings-interface-hardening` research: `bindings interface: definition, validation, boundary and semantic-spread discovery`
