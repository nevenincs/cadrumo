---
tags:
  - '#adr'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-research]]'
---

# `codebase-monolith-decomposition` adr: `hexagonal facade preserving monolith decomposition` | (**status:** `accepted`)

## Problem Statement

The codebase still contains production modules above the 1250-line decomposition objective after the initial CLI extraction waves. Some remaining modules are pure CLI transport roots, but most are application, domain, adapter, persistence, or core modules whose boundaries affect public imports, domain ownership, persistence contracts, or external-service adapters.

## Considerations

- The project uses a hexagonal architecture: core primitives sit at the bottom, domain logic is independent, application services orchestrate use cases, and adapters own external-system translation.
- Top-level packages and public modules are the consumer-facing facade. New implementation submodules may be private, but clients should not need to import from those private modules.
- Mechanical line-count splitting is acceptable for CLI command registrars when behavior and command names are preserved. It is not enough for backend modules whose split changes ownership or import direction.
- The final guard needs truthful enforcement. A blanket 1250-line guard is only valid once the current over-limit inventory is gone; until then, shrinking legacy budgets must make residual debt explicit.

## Constraints

- Decomposition must not move business policy into entrypoints or adapters.
- Domain modules must not import application or adapter code.
- Core modules must remain free of upward dependencies.
- Adapter splits must preserve external contract behavior and typed error boundaries.
- Existing public imports must either remain available from the top-level facade or be intentionally migrated through an ADR-backed change.
- Tests must exercise real behavior and must not use fakes, stubs, monkeypatches, skips, or xfails to simulate safety.

## Implementation

Future slices will split each oversized module by ownership boundary. Extracted implementation helpers will live in focused private submodules, while the package or root module remains the public facade by importing and re-exporting the supported consumer surface. CLI roots continue using registrar modules for command groups. Application/domain/backend files receive separate ADR-backed tranches when the split affects public contracts, storage boundaries, registry authority, or external adapters.

The static guard will be extended in two stages: first with exact legacy budgets for current over-limit modules so no residual monolith can grow silently, then with a hard 1250-line ceiling once the queued modules are decomposed below that threshold.

## Rationale

The research inventory shows that many remaining files are not equivalent in risk. CLI roots can be reduced through command registrars because their job is transport wiring, while registry, storage, AEAT, and application orchestration modules require explicit boundary choices. Preserving top-level facades keeps consumers stable and reinforces the existing hexagonal design instead of exposing private implementation modules as a new integration surface.

## Consequences

This decision makes the decomposition slower but safer. The plan must carry explicit follow-on rows instead of treating the final guard as complete while oversized modules remain. The upside is a cleaner backend with stable public imports, better targeted tests, and guardrails that report real residual debt.

## Codification candidates

- **Rule slug:** `service-imports-via-top-level-reexports`.
  **Rule:** Consumers must import application, domain, adapter, and core services through public top-level facades rather than newly extracted private implementation modules.
