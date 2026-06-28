---
tags:
  - '#adr'
  - '#error-code-registry'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-error-code-registry-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
---



# `error-code-registry` adr: `error-code-registry` | (**status:** `accepted`)

## Problem Statement

Iteration 6 of the Kent-first CLI hardening plan requires a stable error
contract that the current codebase does not have. Today the CLI mixes
`typer.BadParameter`, ad hoc `Console.print()` prefixes, bare `typer.Exit`,
and uncatalogued `AeatError` subclasses. That fragmentation prevents clean
stderr automation, stable copy-paste recovery guidance, and any shared
registry that later foundations can reuse for `--json`, concurrency
classification, and trilingual error messaging.

## Considerations

- The controlling design input is iteration 6 of the 2026-04-24 CLI
  wireframe reference, backed by the parent CLI wireframe ADR and EPIC #392.
- The project already standardises on typed domain exceptions and strict
  Pydantic v2 models, so the registry should extend that shape rather than
  introduce a parallel mechanism.
- The user explicitly fenced off `src/aeat/entrypoints/cli/workflow/run.py` and
  `src/aeat/entrypoints/cli/workflow/next.py` until sibling issue #393 lands.
- Later foundational issues reuse this work directly:
  - issue #399 consumes the error envelope and JSON discipline;
  - issue #400 consumes the registered `LOCKED`, `INTEGRITY`, and `REFUSED`
    categories;
  - issue #401 consumes the `default_message_es/en/hu` and
    `default_suggestion` fields.
- Prior-art research showed that Click's central exception translation and
  Pydantic's split between human and machine error surfaces fit the contract,
  while Typer/Rich default exception rendering is too presentation-heavy for a
  grep-stable operator interface.

## Constraints

- The existing public import path `from aeat.core.errors import ...` must keep
  working, even though the single-file `aeat.core.errors` module needs to grow a
  `_registry.py` sibling.
- Every concrete `AeatError` subclass on `main` needs a registered code, but
  the implementation must stay phaseable enough to avoid a repo-wide manual
  rewrite of every CLI error site in one pass.
- The issue requires ASCII-stable prefixes and Windows-safe stderr handling for
  non-ASCII localized messages.
- The public surface must remain `aeat.core.errors`; callers should not import
  directly from `aeat.core.errors._registry`.

## Implementation

- Convert `aeat.core.errors` from a single module into a package and re-export the
  existing public symbols from `aeat.core.errors.__init__`.
- Add `aeat.core.errors._registry` with:
  - a closed `ErrorCategory` enum for the stable stderr prefixes;
  - strict, frozen Pydantic models for `ErrorCode` and `ErrorEnvelope`;
  - a registration surface that binds a code record to each `AeatError`
    subclass at declaration time;
  - secret-scrubbing, localized rendering, deterministic JSON serialization,
    and placeholder exit-code mapping helpers.
- Keep the category policy separate from per-error metadata. Prefix and exit
  code derive from the category; message defaults, retryability, and recovery
  command derive from the per-error record.
- Apply a shared Typer callback wrapper from the CLI root so most commands gain
  the new stderr envelope without file-by-file decorator edits. The wrapper
  skips `workflow run` and `workflow next` to respect the coordination
  boundary.
- Add static-analysis tests that import-walk the `aeat.*` tree, assert every
  `AeatError` subclass has a registered code, and ensure there are no orphan
  categories or duplicate code bindings.
- Add regression tests for deterministic JSON serialization, suggestion parsing
  against the live CLI tree, stderr prefix stability, stdout/stderr separation,
  and Windows-safe non-ASCII error emission.
- Generate `docs/error-codes.md` from the live registry via a script under
  `scripts/`, and update the Kent capability matrix once the feature is in
  place.

## Rationale

This design is the smallest defensible shape that satisfies iteration 6 and
supports the next three foundations cleanly.

The category table is the real contract. It owns prefix vocabulary and exit
policy in one place, so later changes do not drift across dozens of error
classes. A separate `ErrorCode` record keeps per-code metadata strict and
machine-readable without duplicating category policy. That mirrors the useful
parts of Pydantic's structured errors and Click's central exception handling
while staying idiomatic to this repo's typed-exception design.

Applying the CLI boundary centrally is also deliberate. The codebase has too
many registered callbacks to make per-file wrapping safe in the same change,
and issue #393 already owns two workflow entrypoints. Root-level traversal gets
the new behavior onto the Typer tree while keeping those two callbacks
untouched until their sibling branch merges.

Finally, the registry binds at subclass declaration time rather than through a
separate manual list. That keeps the enforcement local to the exception type,
reduces clerical drift, and lets the static test prove that the imported tree
and the registry stayed aligned.

## Consequences

- `aeat.core.errors` becomes a package, so the implementation must preserve
  imports and avoid circular-import regressions.
- The first landing provides the registry, envelope, and central CLI emission
  path, but it does not finish the parse-time Click translation problem or the
  full `--json` rollout. Those remain coordinated follow-on work, principally
  issue #399.
- Existing commands that still raise `typer.Exit` or `typer.BadParameter`
  directly continue to exist; the new registry now gives the repo a shared
  contract to migrate them toward.
- `workflow run` and `workflow next` stay undecorated in this branch on
  purpose. The implementation and plan both record that deferral until #393
  merges.
- The generated error-code documentation becomes a new maintenance surface, so
  the docs file must always be produced from the live registry rather than
  edited by hand.
