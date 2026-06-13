---
tags:
  - '#adr'
  - '#modelo-registry-fragments'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-modelo-registry-fragment-architecture-research]]'
---



# `modelo-registry-fragments` adr: fragment authoring compiler for modelo registry definitions | (**status:** `accepted`)

## Problem Statement

The modelo registry cannot remain defensible while any single authoring file is
large enough that reviewers cannot inspect it. The first directory split removed
some multi-revision single-file surfaces, but M200 still has one revision file
with more than 130,000 lines. M100 also has six large year files. A revision per
file is therefore not a sufficient architecture.

The registry needs a layout that is reviewable for every modelo, not a one-off
split for the current largest files.

## Considerations

The runtime schema already has the right boundary: loaders parse TOML into raw
payloads, then strict Pydantic models validate `ModeloDefinition` and
`ModeloRevision`. Validators, snapshots, relation resolution, formula execution,
and application surfaces consume those runtime objects rather than source files.

Reference systems point to the same conclusion. OpenFisca and PolicyEngine use
small path-scoped legal parameter files and compile them into a navigable
parameter tree. Tax-Calculator keeps a runtime defaults object but separates
schema metadata and compact reforms. JSON Schema recommends modular source
schemas with stable references and bundling for consumption.

The important distinction is authoring layout versus runtime schema. The
registry should change authoring layout first and preserve runtime objects.

## Constraints

The implementation must be generic across modelos. It must not special-case
M200, M100, or any current modelo id.

The implementation must keep the public `ModeloDefinition`, `ModeloRevision`,
`RegistryCatalogues`, and `RegistrySnapshot` models stable.

Fragments must not introduce local legal/source catalogues or redeclare
`[modelo]`; shared catalogues remain under the legal catalogue tree.

Merge order must be deterministic, and cache fingerprints must include every
TOML file read by the loader.

Migration must preserve concurrent `data_type`, `semantic_role`, constraints,
legal references, and source references. Fragmentation cannot normalize or
flatten active schema-hardening work.

## Implementation

Directory-mode modelos gain a second revision source layout:

```text
modelos/<id>/
  manifest.toml
  revisions/
    <revision-id>.toml
    <revision-id>/
      revision.toml
      casillas/*.toml
      export/*.toml
      formulas.toml
      bindings.toml
      relations.toml
      ...
```

The existing `revisions/<revision-id>.toml` layout remains supported. A migrated
revision may instead be authored as `revisions/<revision-id>/...`. Each fragment
uses the existing `[revisions."<revision-id>"]` / `[[revisions."<revision-id>".kind]]`
shape. The loader merges all fragments for a revision into the same raw revision
payload that current TOML files produce.

Merge rules:

- known `ModeloRevision` array record kinds append in deterministic path order;
- scalar revision fields reject duplicate declarations;
- `export_layouts` with the same id merge only when their scalar metadata is
  identical, appending records deterministically;
- fragments declaring a revision id different from their directory name fail;
- fragments declaring `[modelo]` or local catalogue tables fail;
- final Pydantic validation and existing registry validation remain the
  authority for id uniqueness and reference closure.

## Rationale

This option solves the file-size problem without turning fragment mechanics into
runtime domain concepts. It allows any modelo to migrate incrementally, keeps
tests grounded in object equivalence, and makes M200 a pilot rather than a
special path.

It also avoids runtime inheritance. Inheritance would force every snapshot and
validator consumer to reason about partially materialized revisions. A
pre-validation compiler keeps downstream code on fully materialized
`ModeloRevision` objects.

## Consequences

The loader becomes responsible for deterministic source compilation, so loader
tests must cover fragment equivalence and duplicate rejection.

Any cache that fingerprints registry files must recurse through directory-mode
modelos. The filing runtime cache already needs this fix because it misses
directory-mode TOML files today.

M200 can be migrated by record kind after the generic loader support lands. M100
should first use physical fragmentation. A later ADR can decide whether
template expansion is worth adding for repeated year-to-year formulas, bindings,
and casilla families.
