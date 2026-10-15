# Python API overview

This page covers the first-party Python package boundaries for contributors:
which layers exist, what each one owns, and where to start reading before
following a link into the generated module reference. It is part of the full
documentation build only; taxpayer-facing builds exclude the API tree.

Cadrumo is a hexagonal application. Dependencies point inward: adapters and
entry points depend on the application and domain layers, never the reverse.
The generated reference mirrors each package tree, so the curated map below is
the fastest way to land in the right subpackage.

## Layers

- {doc}`cadrumo.core <cadrumo.core>` owns the shared spine: typed identifiers
  and closed-value enums (`Modelo`, period codes, source kinds), the JSON
  envelope contract, settings, and the product identity authority. Every other
  layer may import it; it imports none of them.
- {doc}`cadrumo.domain <cadrumo.domain>` owns tax semantics: the modelo
  registry's typed declarations and the reader for the published registry
  authority, calculation formulas and bindings, deadlines, and taxpayer
  records. Domain logic stays independent from adapters. The registry compiler
  is development tooling outside the shipped package.
- {doc}`cadrumo.application <cadrumo.application>` owns orchestration: filing
  workflows, calculation actions, the ledger, verification, exports, and the
  secure-storage services that compose domain primitives into operator verbs.
- {doc}`cadrumo.adapters <cadrumo.adapters>` owns the boundary
  implementations: inbound parsers (bank statements, borrador and
  justificante documents) and outbound integrations (the AEAT sede, Google
  Sheets, LLM providers).
- {doc}`cadrumo.entrypoints <cadrumo.entrypoints>` owns the process surfaces:
  the `aeat` command-line interface and its full-screen workbench. The
  `cadrumo-mcp` Model Context Protocol server ships in the separate
  `cadrumo_harness` package and drives the same application services.

## Where to start

Read a feature top-down: find its operator verb in the CLI entry point, follow
it into the application service it calls, then into the domain primitives that
service composes. Every public symbol has one defining module, and consumers
import it from that module; package `__init__` files are inert namespace
markers that export nothing.

The application API starts at the {doc}`cadrumo package root <cadrumo>`. The
neutral client contracts, installed runtime, MCP harness, and separate agent
service each have their own generated package root. Every full documentation
build generates these module pages from the canonical first-party source roots,
so they are never committed or edited by hand.

```{toctree}
:hidden:

cadrumo
cadrumo_client
cadrumo_runtime
cadrumo_harness
cadrumo_agent_service
```
