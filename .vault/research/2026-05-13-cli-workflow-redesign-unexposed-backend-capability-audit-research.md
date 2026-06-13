---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---



# `cli-workflow-redesign` research: `unexposed-backend-capability-audit`

This research audits implemented backend and adapter packages that remain outside
the CLI workflow redesign epic as explicit execution waves. The audit compares
the current source tree against the apex CLI decision and the epic plan so each
unexposed capability receives a concrete disposition: wire through an approved
`aeat app` or `aeat config` domain, keep internal to a backend workflow, or
delete the rejected operator surface.

## Audit Surface

The source audit covered `src/aeat/application`, `src/aeat/domain`,
`src/aeat/adapters/inbound`, `src/aeat/adapters/outbound`, the active
`src/aeat/entrypoints/cli` tree, and the plan document
`.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`.

The active CLI tree contains the approved root topology only:
`src/aeat/entrypoints/cli/_config.py`, `src/aeat/entrypoints/cli/_app.py`,
`src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/entrypoints/cli/_modelo.py`,
`src/aeat/entrypoints/cli/_overview.py`, `src/aeat/entrypoints/cli/_live.py`,
`src/aeat/entrypoints/cli/registry.py`, and the review helpers mounted beneath
approved app domains. Retired packages such as root financial, filing, browser,
data, and deadlines packages are absent from `src/aeat/entrypoints/cli`.

The epic plan already carries waves for profile, bucket, ledger, modelo,
overview, live reads, registry, review, evidence bundles, workflow engine, and
workflow resumption. It does not yet carry explicit execution waves for every
source package that still has implementation value but lacks a precise CLI
workflow placement.

## Findings

`src/aeat/application/topics/__init__.py` implements a strict `TopicCatalogue`
and `Topic` Pydantic model over `registry/aeat/topics`. The module docstring
still describes `aeat app registry citations`, which is an approved destination,
but the epic plan lacks a wave that harvests topic catalogue data into registry
citations and manual help. The rejected `topic` and help-root language must not
return as operator commands.

`src/aeat/application/verification/_verify.py` implements registry-backed
declaracion verification. It parses observed declaration values through
`DeclaracionObservation`, loads a validated registry snapshot, computes expected
values, classifies discrepancies, and returns a typed `VerificationVerdict`.
This is calculation and filing-record backend behavior, not CLI behavior. The
epic plan has modelo verify and reconcile waves, but it does not isolate this
specific verification parser bridge as a wave with real integration tests.

`src/aeat/adapters/inbound/declaracion/__init__.py` exposes strict declaration
PDF parsing through `parse_declaracion` and `parse_declaracion_bytes`. This
capability must feed modelo verification, filing-record import, and external
filing reconciliation. It must not recreate a root declaration or filing CLI.

`src/aeat/domain/justificante/__init__.py` and
`src/aeat/adapters/inbound/justificante/__init__.py` expose a domain record,
repository, error vocabulary, parser backend enum, and `parse_justificante`.
This is a filing-record import and reconciliation substrate. It needs a wave
that binds official justificante evidence into
`aeat app modelo filing-record import` and `aeat app modelo reconcile` through
secure bucket storage and bucket events.

`src/aeat/domain/submission/_engine.py` is a read-only submission record loader
and preflight engine. The module explicitly forbids AEAT remote writes and
write-shaped portal walks. Its durable value is internal
`aeat app modelo verify` and `aeat app modelo file` preflight plus historical
submitted-status reading for filing records. The plan needs an execution wave
that preserves this internal
preflight value while deleting any command vocabulary that implies live submit.

`src/aeat/adapters/inbound/sanitizer/__init__.py` exposes PDF token replacement,
metadata scrubbing, deterministic save flags, and typed sanitizer errors. This
is implemented intake hygiene for real AEAT artefacts. The epic currently names
it as an internal capability, but lacks a wave that wires it to ledger attach,
modelo import, borrador import, and justificante import without creating a
standalone sanitize command.

`src/aeat/adapters/outbound/llm/__init__.py` exposes a full LLM client, cache,
prompt registry, usage recorder, provider errors, and provider model types. The
CLI design has no approved LLM root. This package requires an explicit
governance wave: no command-local AI, no profile data leaves secure storage
without a backend policy, and OCR or classification use is invoked only through
strict typed backend services with evidence provenance, confidence scoring,
redaction, usage records, central errors, and bucket events.

`src/aeat/adapters/outbound/aeat/export/__init__.py` exposes export-boundary
preflight contracts, format errors, `Preflight`, `LiveSubmitForbiddenError`, and
domain submission protocols. The source package is named export but its
operator role in the redesigned UX is `aeat app modelo export` and
`aeat app ledger export libros`; the live-submit prohibition remains absolute.
The plan needs a wave that binds serializer behavior to modelo revision exports
and BOE libro exports without reviving a root filing surface.

`src/aeat/domain/attachments/__init__.py` exposes a content-addressed
attachment domain for transaction evidence. Existing plan waves mention
`src/aeat/application/evidence`, which does not exist. The implementation wave
must either create a real application service over `domain/attachments` or
rename the plan scope to the actual ledger evidence application package once it
exists. The CLI remains thin: `aeat app ledger attach` and evidence bundle
commands delegate to backend services only.

## Gap Map

The following new waves are required:

- Topic corpus harvest: `application/topics` flows into registry citations and
  manuals.
- Declaracion verification parser harvest: `application/verification` and
  `adapters/inbound/declaracion` flow into modelo verify, reconcile, and
  filing-record import.
- Justificante import harvest: `domain/justificante` and
  `adapters/inbound/justificante` flow into filing-record import and reconcile.
- Submission preflight and status harvest: `domain/submission` flows into
  internal verify/file preflight and filed/submitted status records.
- Sanitizer intake harvest: `adapters/inbound/sanitizer` flows into ledger and
  modelo intake paths.
- LLM governed evidence harvest: `adapters/outbound/llm` is reachable only
  through approved backend OCR, extraction, and classification services.
- Export serializer harvest: `adapters/outbound/aeat/export` flows into modelo
  revision exports and ledger BOE libro exports.
- Attachment evidence storage harvest: `domain/attachments` receives a real
  application service boundary for ledger evidence and evidence bundles.

## Design Invariants

Every new wave preserves the root contract: `aeat config` and `aeat app` are the
only operator roots. CLI handlers contain no business logic and call centralized,
standardized, tested Pydantic backend services with central logging, central
errors, and `_emit` output. Every persisted mutation is scoped to the active
profile bucket and emits a bucket event. Live AEAT submission remains forbidden.
Rejected operator surfaces are deleted rather than preserved.
