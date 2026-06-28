---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P306.S1831'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
---

# `cli-workflow-redesign` `W62.P306.S1831`

Completed the read-only grounding pass for the W62 topic corpus registry harvest before implementation work.

No source files were edited for this step.

## Description

The existing CLI surface already mounts corpus registry commands under `aeat app registry` through `registry.py` importing `_registry_corpus.py`. The mounted command groups are:

- `aeat app registry citations list`
- `aeat app registry citations show`
- `aeat app registry citations verify`
- `aeat app registry manuals list`
- `aeat app registry manuals show`
- `aeat app registry manuals rules`
- `aeat app registry manuals verify`

W62 is therefore not command creation from scratch. The next work is to move corpus/topic projection and payload shaping into strict application registry contracts while keeping the CLI thin.

The topic catalogue is already represented by strict frozen `Topic` and `TopicCatalogue` records loaded from `registry/aeat/topics/*.toml`. The catalogue currently contains 13 topic TOML files. Topic display values are locale-backed through keys such as `topic.<slug>.title` and `topic.<slug>.body`.

The current drift against the ADR boundary is that `_registry_corpus.py` directly calls domain normatives/manuals APIs, shapes JSON/text payloads inside CLI handlers, and imports private manual modules. The public `aeat.domain.manuals` surface already exports `RuleKind` and `ManualVerificationReport`, so the next implementation should consume public domain/application contracts instead of private manual internals.

`aeat.application.registry` already contains Pydantic reports for registry authority, workbook, and parity workflows, but it does not yet provide a topic/corpus projection service.

The ADR constraints confirmed for this wave are:

- The CLI remains thin and emits through `_emit`.
- Output format is controlled by the root `--format`.
- The approved corpus inspection surface is read-only and local.
- No active bucket is required.
- No bucket events are emitted.
- The approved commands are only the `aeat app registry citations ...` and `aeat app registry manuals ...` commands listed above.

The rejected surfaces and behaviors remain outside the accepted design:

- top-level `aeat normatives`
- top-level `aeat manual`
- top-level `aeat registry`
- operator-facing manual fetch
- command-local `--json`
- Rich-only rendering
- aliases or compatibility shims
- `aeat topic`
- `aeat help`

Existing tests already guard the command placement, absence of top-level normatives/manual roots, absence of a parallel corpus surface, and absence of fetch verbs.

## Tests

No tests were run. This step was a read-only grounding pass.
