---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W53,W55,W56,W58,W63..W69'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]"
---

# `cli-workflow-redesign` W53/W55/W56/W58/W63..W69 batch closeout

Closed plan rows: 204 across these waves.

## Per-wave surface evidence

- **W53 app overview shape**: `aeat app overview status` mounted in
  `entrypoints/cli/_overview.py`. The handler renders an
  `OverviewCalendar` through the `application/overview` service.
- **W55 app registry boundary**: `entrypoints/cli/registry.py`
  mounts `inspect`, `verify`, `audit-oracles`,
  `verify-filed-state`, `workbooks verify` against
  `application/registry` and `domain/calculations/registry`.
- **W56 app review queue execution**:
  `entrypoints/cli/_review.py` mounts `queue` against
  `application/review` services; cross-domain readonly review
  surface is canonical.
- **W58 workflow engine harvest**: `application/workflow/_engine`
  carries the `WorkflowEngine` with test coverage in
  `test_engine.py`. Bound through workflow-state repository.
- **W63 declaracion verification parser harvest**:
  `adapters/inbound/declaracion/` with `_detect`, `_parser`,
  `_parsers`, `_schema`, plus parser-boundary tests.
- **W64 justificante filing record harvest**:
  `adapters/inbound/justificante/` with `_extract`, `_parser`,
  `_parsers` and extract/parse tests; consumed by `aeat app
  modelo filing-record import`.
- **W65 submission preflight and status harvest**:
  `domain/submission/` carries `_engine`, `_preflight`,
  `_models`, `_protocols`, `_repository`. The access-gate
  module enforces submission refusal per the live-AEAT charter.
- **W66 sanitizer intake service harvest**:
  `adapters/inbound/sanitizer/` carries `_pipeline`,
  `_determinism`, `_dynamic`, `_metadata`, `_records`,
  `_streams`, `_structtree`. Consumed internally by `aeat app
  ledger import`.
- **W67 llm governed evidence harvest**:
  `adapters/outbound/llm/` carries `_client`, `_models`,
  `_pricing`, `_prompts`, `_providers`, `_cache`. Available as
  internal adapter; no user-facing root.
- **W68 export serializer boundary harvest**:
  `application/export/_tabular.py` with test_tabular.
- **W69 attachment evidence storage harvest**:
  `application/attachments/` package present; consumed by
  `aeat app ledger attach`.

## Guards held

- No CLI-local business logic at any of the listed surfaces.
- Backend services remain the single sanctioned write path.
- Each Wave's bound module is present and tested; the CLI
  thin-adapter pattern continues to hold.
