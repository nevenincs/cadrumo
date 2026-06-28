---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W31..W47 (batch)'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-actor-attribution-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
---

# `cli-workflow-redesign` W31..W47 batch closeout

Closed plan rows: every row of Waves W31, W32, W33, W37,
W38..W47, 420 plan rows total.

## Surface verification

- **W31 domain-harvest normatives**: `domain/normatives/` carries
  `_cite`, `_loader`, `_lookup`, `_schema`, `_verify`. CLI is
  mounted under `aeat app registry citations` (test
  `entrypoints/cli/test_registry_corpus.py` exercises the
  surface).
- **W32 domain-harvest VAT classification**: `domain/vat/`
  carries `_classification`, `_corpus`, `_catalogue`, `_flow`,
  `_lookup`, `_rates`. Consumed by `application/ledger` classify
  action.
- **W33 domain-harvest OSS/IOSS**: `domain/vat/_oss.py` defines
  the OSS/IOSS regime substrate. Bound by `aeat app modelo` 369
  calculation path.
- **W37 festivos deadline shift**: `domain/deadlines/_festivos.py`
  carries the holiday-adjustment service. Consumed by deadline
  calendar.
- **W38 modelo work units**, **W39 modelo calculate revisions**,
  **W40 modelo verify**, **W41 verified complete**, **W42 modelo
  file**, **W43 modelo filing record**, **W44 actor attribution**,
  **W45 app modelo discard**, **W46 app modelo shape**, **W47
  app modelo bindings shape**: `aeat app modelo` Typer tree at
  `entrypoints/cli/_modelo.py` mounts the canonical verb set:
  `list`, `describe`, `casillas`, `formulas`, `bindings list`,
  `bindings preview`, `work create`, `work list`, `work status`,
  `work rename`, `work discard`, `work calculate`,
  `work revisions`, `work verify`, `work file`, `work amend`,
  `filing-record list`, `filing-record show`, `filing-record
  import`, `verification-report list`,
  `verification-report show`. Each delegates to
  `application/modelo/` services.

## Guards held

- Every Wave's CLI handler delegates to a canonical
  application/domain service.
- No CLI-local business logic surfaces detected.
- The retired `app declaration` mount is rejected by
  `test_apex_workflow_verification.py`.
