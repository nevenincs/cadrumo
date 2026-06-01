# Architecture

`aeat` follows a hexagonal layout. Business rules sit at the center and stay independent of the parsers, browsers, and storage that reach the outside world. Dependencies point inward: the outer layers know about the inner ones, never the reverse. This keeps tax logic testable in isolation, and it lets an adapter change without touching a rule.

Throughout, AEAT is the Spanish tax authority, the Agencia Estatal de Administración Tributaria.

## The layers

`aeat` separates responsibilities into five layers under `src/aeat/`:

- **`domain`** holds pure records and tax rules: the modelo registry, casilla definitions, filing observations, and the calculations over them. It depends only on `core`.
- **`application`** orchestrates use cases. It joins domain rules with adapters to build filing drafts, aggregate the ledger, run diagnostics, and project state. It performs no input or output of its own.
- **`adapters`** connects the application to the outside world, in three parts. `inbound` parses incoming files, such as PDF, CSV, and Open Financial Exchange (OFX) statements. `outbound` reaches external services, such as AEAT browser sessions, calculation oracles, and authentication providers. `persistence` stores records in a local encrypted database.
- **`entrypoints`** exposes the application to operators. The command line lives here, and its surface is limited to the two root command families, `config` and `app`.
- **`core`** supplies cross-cutting infrastructure to every layer: configuration, the error taxonomy, the message catalogue, logging, and typed primitives.

Two boundary rules keep the layers honest. Boundary data crosses as validated pydantic v2 models, not loose dictionaries. Closed value sets, such as period codes, lifecycle states, and authentication providers, are declared as typed enums in `core` and flow as enum members. When an input is invalid, the command line reports the accepted values.

## The registry authority flow

The authoritative tax-model definitions aren't hard-coded. They move through a deterministic pipeline, from hand-authored source to the snapshots that runtime code reads:

1. **Authoring tree.** Each modelo and revision is authored as fragments of TOML (Tom's Obvious Minimal Language), a layout meant for editing.
2. **Loader and compiler.** `_loader.py` merges the fragments in a deterministic order, rejects ambiguous conflicts, and compiles them into complete runtime objects. It invalidates its cache against a fingerprint of the whole tree, so an edit can't serve stale data.
3. **Strict schema objects.** The compiler produces `ModeloDefinition` and `ModeloRevision` models, which are strict, validated, and self-checking.
4. **Validated authority.** `ValidatedRegistryAuthority` validates a modelo once and caches the result. It is the single production entry point for registry-backed access.
5. **Immutable snapshots.** For a given modelo, year, and period, the authority builds a `RegistrySnapshot`. The snapshot is a frozen, context-bound view: its legal and source references are indexed, and its referential integrity is checked.
6. **Runtime projections.** Filing schema providers, formula execution, and export parsing read from snapshots or from typed projections of them.

The authority, not the raw loader, is the production boundary. Runtime code requests validated modelos, deadline windows, and snapshots through it. The loader stays an implementation detail behind that line.

## How documentation stays true to the code

The discipline that governs the layers governs the documentation too: nothing a reader relies on is maintained by hand where the code can supply it. `aeat` keeps three English documentation surfaces, and each is generated or verified from the codebase.

The repository markdown, the README and the guides under `docs/`, is hand-written for people orienting to the project. Every technical claim in it is checked against the code before it lands. In-source docstrings are the single source for the reference documentation, so a signature is never copied into prose. The generated reference, both the source-code interface and the command-line tree, is scaffolded from the code itself.

Because these surfaces are generated, they can't silently drift from the code. Correctness is enforced at build time rather than by reviewer vigilance. A strict build, with warnings treated as errors, fails on a broken cross-reference, a missing stub, or a command reference that no longer matches the commands.

## Safety and legal grounding

The safety posture is a property of the structure, not a convention an operator has to remember. `aeat` has no submission command and no outbound adapter that writes to AEAT, so live filing is absent rather than guarded. Read-only live checks against external services stay behind an explicit opt-in.

Tax semantics are grounded in official sources: the Boletín Oficial del Estado (BOE), AEAT publications, AEAT workbooks, and registry sources. They're never invented. That grounding travels with the data. Each casilla observation carries its legal references, source references, and formula identifier as a typed envelope. The envelope travels from the registry definition through to the operator-facing output. Every computed figure can therefore trace back to the authority behind it.
