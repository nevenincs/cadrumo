# Package namespaces

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-001` · **Topic:** [Document and financial imports](../topics/document-and-financial-imports.md)

<!-- preserved:article -->
## Scope

This implementation chunk covers `src/cadrumo/__init__.py` and `src/cadrumo/adapters/__init__.py` (67 source lines total; 3,050 bytes and 608 measured proxy tokens per the chunk manifest). I read both files in full. This is static inspection of the on-disk snapshot: it does not establish runtime import behavior beyond the statements and definitions visible here.

## Product capabilities and actors

These two modules expose no user workflow or adapter implementation. The root package explicitly sets an empty `__all__` and says callers should import the module that defines a capability rather than depend on a root-level barrel (`src/cadrumo/__init__.py`). The adapter namespace likewise exports no concrete classes and directs callers toward focused `inbound`, `outbound`, and `persistence` subpackages (adapters/__init__.py (`src/cadrumo/adapters/__init__.py`)). The product capability that can be confirmed here is architectural: these namespaces are meant to make internal layer boundaries legible. Actual parsing, integration, storage, and use-case behavior belongs to the child modules and is outside this chunk.

The package documentation assigns responsibilities: `core` for shared primitives and runtime context, `domain` for business authorities, `application` for orchestration, `adapters` for infrastructure, and `entrypoints` for operator transports such as a Typer CLI (`src/cadrumo/__init__.py`). The adapter docstring describes translations between internal contracts and PDFs, financial statements, AEAT Sede pages, browser sessions, Google services, LLM providers, local profile stores, and encrypted storage (adapters/__init__.py (`src/cadrumo/adapters/__init__.py`)). These are descriptions of intended module ownership, not evidence that any integration is implemented or usable.

## How it works

Both files contain only module documentation, `from __future__ import annotations`, and an empty `__all__` tuple. There is no constructor, function, state mutation, I/O, dependency wiring, recovery path, or external interface in the inspected code. The visible import surface is intentionally narrow. The root package docstring states that importing `cadrumo` should not configure logging, load registries, open storage, or materialize browser/PDF integrations, and that logging policy is centralized in `core.logging.configure_logging` (`src/cadrumo/__init__.py`). This code is consistent with that stated goal because it performs no such operation itself; proving transitive import behavior would require inspecting imports at the package import boundary and/or runtime execution, which this static-only assignment excludes.

The adapter namespace describes an outer infrastructure layer: adapters may depend on `core`, while lower layers are not meant to import adapter internals to obtain transport or persistence behavior (adapters/__init__.py (`src/cadrumo/adapters/__init__.py`)). The package file does not enforce that dependency rule. Enforcement, if any, must come from separate architecture checks, build tooling, or code review.

## Knowledge and data

Neither module loads or stores application data. References to registries, corpora, secure storage, and external services are navigation pointers to other modules, not data authority or provenance evidence. This chunk provides no evidence about freshness, persistence formats, or how adapters consume external or bundled knowledge.

## Security and safety

The empty module bodies avoid package-level side effects and therefore do not themselves open files, make network calls, initialize browser/PDF libraries, configure logs, or handle credentials or personal data. This is a concrete local observation; the stronger import-safety statements in the docstring remain stated design intent until the referenced modules and import graph are inspected. No authorization checks, redaction, encryption, or irreversible actions are implemented here. Their absence in namespace files says nothing about controls in concrete adapters.

## Implementation assessment

The namespace files are small and their import-light intent is easy to audit. Their limitation is that the layer and import-boundary rules are documentation only in this chunk; no check or test is present here to prevent a future side effect or forbidden inward dependency. No tests or test references occur in these files. A static review cannot certify that importing the package tree remains inert when child modules are involved.

## Dependencies and follow-up

The docs point synthesis toward `core.logging`, `core.resources`, `application.operator_surface`, and the `adapters.inbound`, `adapters.outbound`, and `adapters.persistence` modules. Follow-up analysis should establish whether these stated boundaries are reflected in concrete imports, how package-level import behavior is exercised, and where operator capability contracts and security controls are actually enforced.

## Complete assigned-file coverage

- `src/cadrumo/__init__.py` — all 32 lines read.
- `src/cadrumo/adapters/__init__.py` — all 35 lines read.
<!-- /preserved:article -->
