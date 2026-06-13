---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-w51-modelo-145-deferral-baseline-exec]]'
---



# `cli-workflow-redesign` adr: `Modelo 145 local payer communication reopening` | (**status:** `accepted`)

## Approval Gate

This ADR is persisted for user approval. It has no implementation authority
until the user explicitly approves the decision in the active execution thread.

## Problem Statement

Modelo 145 was deferred by the W51/R22 baseline because the prior foundation
scope risked treating it like a filing-modelo implementation. Current official
research confirms that Modelo 145 is a withholding-data communication to the
payer, retained by the payer, and not presented to AEAT by the taxpayer through
an electronic filing lifecycle.

The project needs a successor decision that reopens Modelo 145 without reviving
stale W51 implementation rows, without weakening the no-live-submission charter,
and without affecting the separate Modelo 036/037 decisions.

## Considerations

AEAT G603 describes Modelo 145 as a communication to the payer or a variation
of previously communicated data. It does not require presentation before the
tax administration, and the payer retains a copy available to the tax
administration.

AEAT's Modelo 145 obligations page states that the model's characteristics do
not allow electronic procedures and that the interested person processes it
before the payer of remuneration.

The current legal/source foundation should use the current AEAT and BOE
authority for Modelo 145, including the 2011 approving resolution and later
amendments. The 2008 resolution may be retained only as derogated historical
context.

The existing 2026-05-12 Modelo 145 foundation ADR correctly identified Modelo
145 as non-filing, but its local workflow language must be narrowed. Completion
means local communication/export/retention status, not AEAT presentation.

The W51/R22 deferral records no shipped Modelo 145 implementation: no
`registry/aeat/modelos/145.toml`, backend service, CLI service, shim, stub,
fake support, or test surface. That deferral remains valid unless this ADR is
approved.

## Constraints

Modelo 145 may be reopened only as a local non-filing payer communication.

This ADR supersedes the W51/R22 deferral for Modelo 145 only after user
approval. It does not supersede, amend, or reopen Modelo 036 or Modelo 037
scope.

Modelo 145 MUST NOT implement or imply AEAT live submission, AEAT electronic
tramite, tax-agency presentation, payment, amendment, declaration read,
document submission, receipt acquisition, or portal write/read behavior.

Modelo 145 MUST NOT expose filing, deadline, live-read, or application-link
surfaces. It must not add `filing_schedules`, `deadline_windows`,
`live_cross_references`, AEAT portal read/write links, or `filing`
application-link surfaces.

Modelo 145 MUST NOT use `file` vocabulary for operator commands, service
methods, state names, event names, help text, or compatibility aliases.
Completion vocabulary must be communication-specific, such as create, validate,
export, mark delivered to payer, and mark locally completed.

Modelo 145 MUST NOT introduce shims, stubs, fake support, placeholder services,
deprecated spellings, compatibility aliases, or CLI-local business logic.

## Implementation

Implementation may begin only after this ADR is approved.

First, add official corpus-backed sources and legal/source catalogue entries
for the AEAT G603 procedure page, the AEAT Modelo 145 obligations page, the
current Modelo 145 form PDF, the `dr145v20.pdf` record design, the current BOE
authority, and any relevant amendments. Derogated historical authority may be
recorded only as historical context.

Second, add `registry/aeat/modelos/145.toml` as a non-filing registry
foundation. The registry entry must model Modelo 145 as a local payer
communication, not as an AEAT filing. It must use the official form and record
design as source-backed authority for fields and export layout.

Third, prefer explicit schema vocabulary for non-filing communication before
overloading filing constructs. Acceptable vocabulary includes
`payer_communication`, `communication`, payer delivery, retention, or equivalent
domain terms. If current registry schema cannot express that cleanly, extend
the schema narrowly before shipping Modelo 145 behavior.

Fourth, add a backend-owned service for real local behavior: create the
communication, validate it against registry-backed rules, export it, mark it
delivered to the payer, and mark it locally completed. The service must own
persistence, bucket events, validation, error contracts, and audit output.

Fifth, expose thin CLI commands only after backend behavior exists. The CLI
must delegate to the backend service, use centralized output and error
boundaries, and use communication vocabulary that cannot be read as AEAT
submission.

Tests must exercise real behavior: source integrity, registry loading, record
layout export against the official record design, local workflow state
transitions, payer-delivery/completion events, and negative assertions that no
filing, deadline, live-read, shim, stub, fake support, or compatibility alias
surface exists for Modelo 145.

## Rationale

Reopening Modelo 145 is justified because current official sources support a
local payer-communication workflow. The model has structured data, validation,
export, retention, and completion needs that fit the registry-backed
architecture.

The reopened scope is intentionally narrow because AEAT facts do not support an
AEAT filing lifecycle for Modelo 145. Using communication vocabulary avoids
encoding false legal semantics into commands, events, registry surfaces, and
tests.

Keeping Modelo 036/037 unaffected prevents a Modelo 145-specific decision from
reopening census-model work with different legal and workflow constraints.

## Consequences

After approval, Modelo 145 becomes eligible for implementation as a first-class
local payer communication. The W51/R22 Modelo 145 deferral is superseded only
for this narrowed scope.

Before approval, no code, registry, source-catalogue, test, service, or CLI
work is authorized by this ADR.

The implementation may require a small registry schema extension before
`registry/aeat/modelos/145.toml` can be represented cleanly.

Any future attempt to add AEAT electronic processing, filing vocabulary,
deadlines, live reads, shims, stubs, fake support, or compatibility aliases for
Modelo 145 requires a separate ADR and cannot be inferred from this decision.
