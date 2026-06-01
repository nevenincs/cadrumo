# Architecture

`aeat` follows a hexagonal layout. Business rules sit at the center and stay independent of the parsers, browsers, and storage that reach the outside world. Dependencies point inward: the outer layers know about the inner ones, never the reverse. This keeps tax logic testable in isolation and lets an adapter change without touching a single rule.

## The layers

`aeat` separates responsibilities into five layers under `src/aeat/`:

- **`domain`** holds pure records and tax rules - the modelo registry, casilla definitions, filing observations, and the calculations over them. The domain depends only on `core`.
- **`application`** orchestrates use cases. It joins domain rules with adapters to build filing drafts, aggregate the ledger, run diagnostics, and project state. It performs no external input or output of its own.
- **`adapters`** connects the application to the outside world, in three parts:
  - `inbound` parses incoming files (PDF, CSV, Excel, OFX).
  - `outbound` reaches external services, such as AEAT browser sessions, oracles, and authentication.
  - `persistence` stores records in a local encrypted database.
- **`entrypoints`** exposes the application to operators. The CLI lives here, and its surface is limited to the two root command families, `config` and `app`.
- **`core`** supplies cross-cutting infrastructure to every layer: configuration, the error taxonomy, the message catalogue, logging, and typed primitives.

Two boundary rules keep the layers honest. Boundary data crosses as validated pydantic v2 models, not loose dictionaries. Closed value sets - period codes, lifecycle states, authentication providers - are declared as typed enums in `core` and flow as enum members. As a result, the CLI reports the accepted values when an input is wrong.

## The registry authority flow

The authoritative tax-model definitions are not hard-coded. They move through a deterministic pipeline, from hand-authored source to the snapshots that runtime code reads:

1. **TOML authoring tree.** Each modelo and revision is authored as TOML fragments, a layout meant for editing.
2. **Loader and compiler.** `_loader.py` merges the fragments in a deterministic order, rejects ambiguous conflicts, and compiles them into complete runtime objects. It invalidates its cache against a fingerprint of the whole tree, so an edit can never serve stale data.
3. **Strict schema objects.** The compiler produces `ModeloDefinition` and `ModeloRevision` models - strict, validated, and self-checking.
4. **Validated authority.** `ValidatedRegistryAuthority` validates a modelo once, caches the result, and becomes the single production entry point for registry-backed access.
5. **Immutable snapshots.** For a given modelo, year, and period, the authority builds a `RegistrySnapshot`: a frozen, context-bound view with its legal and source references indexed and its referential integrity checked.
6. **Runtime projections.** Filing schema providers, formula execution, and export parsing read from snapshots or typed projections of them.

The authority, not the raw loader, is the production boundary. Runtime code requests validated modelos, deadline windows, and snapshots through it. The loader stays an implementation detail behind that line.

## The documentation surfaces

`aeat` keeps three English documentation surfaces, each generated or verified from the codebase rather than maintained by hand:

- **Repository markdown** - the README and the narrative guides under `docs/`, written for people orienting themselves to the project.
- **In-source docstrings** - Google-style docstrings on modules, classes, and functions, written for contributors reading the code.
- **Generated API reference** - Sphinx renders the docstrings into the reference under `docs/api/`. `aeat.apidocs` scaffolds the stub tree from the source modules. A correspondence test fails if any module lacks a stub, or if any stub outlives its module.

The CLI reference is generated the same way, from the command tree itself. A nitpicky documentation build, run with warnings treated as errors, catches a broken cross-reference or a malformed directive before it reaches a reader.

## Safety and legal grounding

The safety posture is a property of the structure, not a convention an operator has to remember. `aeat` has no submission command and no outbound adapter that writes to AEAT, so live filing is absent rather than guarded. Read-only live checks against external services stay behind an explicit opt-in.

Tax semantics are grounded in official sources - the Boletín Oficial del Estado (BOE), AEAT publications, AEAT workbooks, and registry sources - never invented. That grounding travels with the data. Each casilla observation carries its legal references, source references, and formula identifier as a typed envelope, from the registry definition through to the operator-facing output, so every computed figure can be traced back to the authority behind it.
