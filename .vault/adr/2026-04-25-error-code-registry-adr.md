---
tags:
  - '#adr'
  - '#error-code-registry'
date: '2026-04-25'
modified: '2026-07-17'
body_hash: 'sha256:4da5c2874c02d675c867d2342477ca6d11a23a296fb6d94c372a0565a58e9773'
related:
  - "[[2026-04-25-error-code-registry-research]]"
  - "[[2026-05-14-cli-workflow-redesign-error-registry-exhaustiveness-invariant-adr]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `error-code-registry` adr: `error-code-registry` | (**status:** `accepted`)

## Problem Statement

CADRUMO needs one stable error contract shared by domain exceptions and the
operator-facing CLI boundary. Without a central registry, exception classes,
stderr categories, exit codes, localized messages, recovery commands, and JSON
error envelopes can drift into independent authorities.

## Considerations

- The codebase standardises on typed `CadrumoError` subclasses and strict Pydantic
  models, so the registry extends that hierarchy rather than introducing a
  parallel exception mechanism.
- The canonical Python package is `cadrumo`; the sole human CLI executable is
  `aeat`. The executable name is an operator contract, not a Python import
  namespace.
- Click/Typer exception translation belongs at the CLI boundary. Domain and
  application layers expose typed errors and structured metadata, not terminal
  formatting.
- The later error-registry-exhaustiveness decision strengthens this ADR with a
  repository-wide one-class/one-code invariant.

## Constraints

- The public Python surface is `cadrumo.core.errors`. Callers MUST NOT import
  registry implementation modules directly.
- The retired `aeat` Python import namespace MUST NOT be preserved through
  aliases, wrapper packages, fallback imports, or compatibility shims.
- Every concrete production `CadrumoError` subclass MUST have exactly one declared
  `ErrorCode`, and every declared code MUST belong to exactly one subclass.
- The registry MUST be the single authority for category, message key, default
  recovery command, retryability, and runbook identity.
- Text prefixes and process exit codes MUST derive from the registered
  `ErrorCategory`; error sites MUST NOT maintain parallel category mappings.
- Text and JSON rendering MUST share the same registered metadata and secret
  scrubbing path.
- Recovery commands stored in registry rows MUST use the canonical `aeat`
  executable and resolve against the live command tree.

## Implementation

- Keep `cadrumo.core.errors` as the public package and re-export its supported
  exception and registry symbols from `cadrumo.core.errors.__init__`.
- Keep the registry implementation behind that public facade, with:
  - a closed `ErrorCategory` enum for the stable stderr prefixes;
  - strict, frozen Pydantic models for `ErrorCode` and `ErrorEnvelope`;
  - one explicit catalogue of qualified `cadrumo.*` exception classes and their
    `ErrorCode` records;
  - class-declaration binding from each `CadrumoError` subclass to that catalogue;
  - secret-scrubbing, localized rendering, deterministic JSON serialization,
    and category-owned exit-code mapping.
- Keep the category policy separate from per-error metadata. Prefix and exit
  code derive from the category; message defaults, retryability, and recovery
  command derive from the per-error record.
- Route CLI callback failures through
  `cadrumo.entrypoints.cli._errors.command_error_boundary`, installed across the
  live Typer tree by `decorate_typer_app`.
- Enforce the catalogue with tests that import-walk `cadrumo.*`, discover every
  production `CadrumoError` subclass, reject missing or duplicate bindings, reject
  orphan codes and categories, and validate every registered `aeat ...`
  suggestion against the live command tree.
- The deferred binding queue exists only to complete the registry module's
  circular-import initialization. It MUST drain into the same explicit
  catalogue and MUST NOT become a fallback code, alias registry, or compatibility
  path for undeclared errors.

## Rationale

The category table owns coarse operator outcome policy once, while each
`ErrorCode` owns strict per-error metadata. The public facade prevents callers
from coupling to catalogue partitioning or initialization details. Central CLI
decoration prevents command modules from creating competing rendering and exit
policies.

Finally, the registry uses one explicit catalogue of qualified exception classes
and their `ErrorCode` records. Each `CadrumoError` subclass binds to that catalogue
at class-creation time, while exhaustive import-walk and raw-declaration tests
prove that class ownership and code ownership remain one-to-one. This keeps the
catalogue reviewable without allowing a second alias list or implicit duplicate
authority.

## Consequences

- Adding or renaming a concrete `CadrumoError` requires updating the explicit
  catalogue in the same change; CI refuses incomplete or duplicate ownership.
- Operator text and JSON errors remain consistent because both resolve through
  the same registered record and scrubbing pipeline.
- Circular-import handling remains an internal initialization concern and does
  not weaken exhaustiveness.
- The architecture carries no `aeat` Python package compatibility surface. The
  name `aeat` remains valid only for the sole CLI executable and for genuine
  Spanish tax-authority vocabulary.
