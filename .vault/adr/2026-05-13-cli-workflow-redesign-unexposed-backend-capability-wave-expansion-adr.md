---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-audit-research]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-audit]]"
---



# `cli-workflow-redesign` adr: `unexposed-backend-capability-wave-expansion` | (**status:** `accepted`)

## Problem Statement

The CLI workflow redesign epic already removes rejected roots and establishes
the approved operator topology, but the current source tree still contains
implemented backend and adapter packages whose execution placement is not
represented as explicit plan waves. Leaving those packages as informal
inventory creates the same failure mode the redesign is meant to remove:
business capability exists, but the approved UX cannot reach it through a
cohesive backend service and tests cannot prove the intended path.

This ADR converts the unexposed capability inventory into named implementation
waves. Each wave defines the backend owner, the approved app or config
destination, the deleted operator vocabulary, and the verification obligation.

## Considerations

The apex decision fixes the root contract to `aeat config` and `aeat app`.
Every command remains a thin adapter. No business logic is implemented in the
CLI layer. Every CLI handler calls centralized, standardized, tested Pydantic
backend services and uses central logging, central error handling, and `_emit`
schema output.

The current source tree has meaningful backend packages that are not abandoned
code: `application/topics`, `application/verification`, `domain/justificante`,
`domain/submission`, `domain/attachments`, `adapters/inbound/declaracion`,
`adapters/inbound/justificante`, `adapters/inbound/sanitizer`,
`adapters/outbound/llm`, and `adapters/outbound/aeat/export`. These packages
must be harvested into approved workflows or removed where they only preserve a
rejected operator surface.

Live AEAT submission remains forbidden. Any wording that implies live submit,
present, sign, pay, or remote write is rejected. Read-only live signals remain
under the accepted `app live` design.

Every persisted mutation is scoped to the active profile bucket and emits a
bucket event. Profile reads use `workflow_state_repository()`. Sensitive tax,
financial, identity, filing, evidence, OCR, extracted, or LLM-derived data is
not written outside the secure storage bucket associated with the active
profile.

## Decision

The epic plan adds one wave for each unexposed backend capability cluster:

- Topic corpus harvest: `application/topics` is consumed by
  `aeat app registry citations` and `aeat app registry manuals`. No `topic`,
  help-root, or standalone topic command exists.
- Declaracion verification parser harvest: `application/verification` and
  `adapters/inbound/declaracion` are consumed by `aeat app modelo verify`,
  `aeat app modelo reconcile`, and filing-record import services.
- Justificante import harvest: `domain/justificante` and
  `adapters/inbound/justificante` are consumed by
  `aeat app modelo filing-record import` and `aeat app modelo reconcile`.
- Submission preflight and status harvest: `domain/submission` is consumed by
  internal `aeat app modelo verify` and `aeat app modelo file` services for
  preflight and historical status records. It exposes no live submit verb.
- Sanitizer intake harvest: `adapters/inbound/sanitizer` is consumed by ledger
  attach/import and modelo artefact import services. It exposes no standalone
  sanitize command.
- LLM governed evidence harvest: `adapters/outbound/llm` is reachable only
  through approved backend services for OCR, extraction, and classification.
  It exposes no LLM command and no command-local AI behavior.
- Export serializer harvest: `adapters/outbound/aeat/export` is consumed by
  `aeat app modelo export` and `aeat app ledger export libros` backend
  services. It does not revive a filing root and does not provide live AEAT
  submission.
- Attachment evidence storage harvest: `domain/attachments` is wrapped by a
  real application service for ledger evidence and evidence bundles. Existing
  plan scope that mentions non-existent evidence packages is corrected during
  this wave.

Every wave follows the same execution order: backend integration through strict
Pydantic command and result contracts, command-collision and shadow-path
deletion, secure bucket and event enforcement, real behavior verification, and
thin CLI exposure only where the approved UX requires a command.

## Implementation

The epic plan is updated with waves W62 through W69. The plan frontmatter links
this ADR and the supporting research document. The apex ADR frontmatter links
this ADR so the CLI redesign cluster is discoverable from the parent decision.

Each wave starts by reading the source package and the governing ADRs, then
creates or updates the application service boundary. Pydantic command and
result models live in the application layer. Domain packages remain pure domain
logic. Adapter packages remain IO boundaries. CLI modules only parse arguments,
call the application service, render through `_emit`, and route errors through
the central command boundary.

Each wave deletes rejected command paths, stale test fixtures, command aliases,
or domain-hosted CLI code that conflicts with the accepted root contract. Tests
exercise real services and real repositories; they do not assert vacuous
behavior or monkeypatch a disconnected interface.

## Rationale

The source inventory shows that the problem is not a lack of backend capability.
The problem is incomplete orchestration: valuable domain and adapter packages
exist without a precise role in the approved CLI workflow. A wave-per-capability
plan makes the work auditable and prevents broad catch-all implementation steps
from hiding offline code.

Keeping the CLI thin protects the separation established by the apex ADR. The
backend owns tax, filing, storage, parsing, verification, extraction, and export
behavior. The CLI exposes the user's workflow without creating a second
implementation of that workflow.

Secure bucket enforcement is repeated because these packages process sensitive
identity, financial, filing, evidence, and derived tax data. A backend feature
that works only through loose files or command-local state is not accepted by
the workflow redesign.

## Consequences

The epic grows by eight implementation waves. The additional waves are
intentional because each capability cluster needs its own backend service owner,
storage contract, deletion audit, and real behavior tests.

The source tree becomes easier to audit: an implemented package is either wired
to an approved workflow, used only as an internal backend dependency, or removed.
There is no tolerated category for orphaned CLI behavior, business logic in
entrypoints, or command vocabulary that implies live AEAT writes.

The plan now captures the remaining unexposed functionality as executable work
instead of narrative inventory.
