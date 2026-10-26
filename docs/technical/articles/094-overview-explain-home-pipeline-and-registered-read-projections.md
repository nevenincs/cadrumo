# Overview explain, Home, pipeline, and registered read projections

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-094` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
**Scope:** 16 files under `src/cadrumo/application/overview`, totaling 3,520 lines, 141,556 bytes, and 29,461 measured `o200k_base` proxy tokens. All six bounded-reader pages and assigned ranges were read. Static inspection only; no application execution or tests were run. Any deadline or filing-rule descriptions below report the code’s declared behavior; they are not independent legal validation.

## Capabilities and mechanisms

`overview explain` separates “does this modelo apply to this taxpayer?” from “what deadline schedule is registered?” It derives a three-state applicability verdict from the registry-backed taxpayer model, returns the rule rationale and opaque legal-reference keys, lists the scalar profile facts used, and independently attaches scheduling rationale where a filing window exists. A known modelo with no windows keeps its applicability answer; an unmodeled recognized obligation is distinguished from an identifier typo. The optional old-deadline annotation is also separate from applicability. The fact projection includes the profile’s `tax_id`, making identity-sensitive handling of this read model relevant at the output boundary. Explain contract and profile facts (`src/cadrumo/application/overview/explain.py`), facts including tax_id (`src/cadrumo/application/overview/explain.py`), registry-backed explain flow (`src/cadrumo/application/overview/explain.py`)

The Home records form a frontend-neutral snapshot for account/custody posture, ranked next actions, resumable declarations, ledger readiness, agenda, and message attention. Each zone carries availability (`available`, `locked`, `stale`, `never_captured`, or `unavailable`) and must represent its observed time and refusal reason consistently. Validators prevent unavailable zones from claiming empty rows or zero counts, limit action and agenda previews to three, and forbid agenda AEAT-submission claims when its evidence zone is not observable. Composition ranks/deduplicates actions, sorts declarations, and chronologically projects the agenda without performing reads. Home availability and session contracts (`src/cadrumo/application/overview/home.py`), availability-aware Home projection (`src/cadrumo/application/overview/home.py`), pure Home composition (`src/cadrumo/application/overview/home.py`)

Next-action declarations share the stable operator action catalogue and include only values the producer already knows. A producer omits an action when required input must come from the operator; resolution against the live command schema belongs to the surface adapter. Overview status guidance is state-dependent: it recommends creating a profile, reviewing existing ledger work, resuming existing Modelo work, or importing transactions as appropriate, while unsupported Modelo 210 work creation diverts to description. Action declaration boundary (`src/cadrumo/application/overview/next_actions.py`), status next-step selection (`src/cadrumo/application/overview/next_actions.py`)

The period pipeline report combines reused ledger counters with one readiness row per loaded work unit. It classifies units as not started, calculated, incomplete, verified, filed, or blocked from the current calculation revision and latest verification report. Its `ready` flag requires a nonempty set of modelo rows, all verified/filed, plus a ledger with no pending review or readiness issues. The registered `overview.pipeline` operation binds reads to the exact active profile, period, bucket ports, and pinned authority; it checks revision coordinates against the corresponding work unit, performs a journaled read capture, and exposes a separate validated result projection. Ledger counters are intentionally whole-profile, so access resolution requires whole-profile consent. Pipeline readiness contract and aggregation (`src/cadrumo/application/overview/pipeline_health.py`), pipeline operation capture and scope checks (`src/cadrumo/application/overview/pipeline_operation.py`), pipeline access registration (`src/cadrumo/application/overview/pipeline_operation.py`)

The common `overview.read` seam exposes six typed read kinds: status, calendar, agenda, backlog, explain, and prepare. Requests reject fields that belong to another command and require the relevant period, date window, Modelo, and bounded agenda horizon. Canonical report variants are copied into strict closed snapshots; calendar event snapshots omit authenticated identity, Decimal fields use public canonical scalar forms, and each readback revalidates the domain model. The result projector releases only an exact-profile successful no-effect receipt. Typed request and query constraints (`src/cadrumo/application/overview/read_request.py`), closed payload variants (`src/cadrumo/application/overview/read_payload.py`), canonical projections (`src/cadrumo/application/overview/read_projection.py`), exact-profile read execution (`src/cadrumo/application/overview/read_operation.py`), receipt-checked release (`src/cadrumo/application/overview/read_result.py`)

## Knowledge, security, and implementation assessment

These services combine the pinned calculation/deadline registry with profile and local-workflow read models; registered operations receive loaded data through narrow read ports. They do not add AEAT access or mutation capability. A stored read remains tied to its request and exact profile, while the output projection rechecks identity, definition, successful terminal condition, and no-effect status. Read-only port contract (`src/cadrumo/application/overview/read_ports.py`), terminal receipt checks (`src/cadrumo/application/overview/read_result.py`)

Strong controls include strict frozen DTOs; cross-field consistency for availability, session identity, action ranks, natural filing addresses, and projected period/year pairs; profile and active-bucket equality checks; and hidden-input configurations for captured operation results. The calendar survey permits public pointers to locked or setup-incomplete profiles but validates that its active calendar belongs to the requested profile. Profile facts are bounded scalar values and translated separately from the immutable projection. Home consistency checks (`src/cadrumo/application/overview/home.py`), survey profile identity (`src/cadrumo/application/overview/read_projection.py`), read subject and receipt binding (`src/cadrumo/application/overview/read_operation.py`)

The clearest privacy question is `overview explain`: `_extract_profile_facts` includes `tax_id`, and the explain snapshot projects those facts into the authorized result. This may be intentional for auditability, but the consuming CLI, logs, and any frontend sharing path should be checked for appropriate profile authorization and redaction. The assigned code shows profile-bound operation access but no field-level masking of that fact. Static evidence does not establish that the value is logged or exposed to an unauthorized actor.

One conditional contract risk lies in the pure pipeline report builder: it accepts `work_units` as already matching the requested bucket/year/period and does not re-filter them. The registered operation’s caller does filter by exact period and bucket, so current registered flow has a check; direct future callers must preserve that precondition. Builder’s caller-owned scope contract (`src/cadrumo/application/overview/pipeline_health.py`), registered period filter (`src/cadrumo/application/overview/pipeline_operation.py`)

The architecture keeps domain calculation separate from transport: read builders compose canonical facts, snapshots revalidate their canonical forms, and registered operations bind persistence/authority and profile scope. Follow-up should verify the outer frontend’s rendering and log policy for explain profile facts, and check tests for forged cross-profile snapshots, hidden identity handling, and exact pipeline scoping. No tests assigned to this chunk were run; current legal currency and runtime enforcement remain outside this static review.

## Dependencies and follow-up

Synthesis should connect the read operation’s ports to the concrete profile-scoped storage adapters, the operation registry and encrypted result-capture path, the canonical `OperatorStateProjection`, and the CLI/TUI renderers. Check how all-profile calendar survey pointers are authorized, whether `tax_id` is masked where appropriate, and whether every direct `build_pipeline_health_report` caller enforces its documented scope. Trace registry provenance for applicability, deadlines, and the dated filing advisory.

## Complete assigned-file coverage

All 16 assigned files were read fully across pages 1–6; no portions remain unread.

- overview/explain.py (`src/cadrumo/application/overview/explain.py`)
- overview/home.py (`src/cadrumo/application/overview/home.py`)
- overview/next_actions.py (`src/cadrumo/application/overview/next_actions.py`)
- overview/pipeline_health.py (`src/cadrumo/application/overview/pipeline_health.py`)
- overview/pipeline_operation.py (`src/cadrumo/application/overview/pipeline_operation.py`)
- overview/pipeline_projection.py (`src/cadrumo/application/overview/pipeline_projection.py`)
- overview/pipeline_read_ports.py (`src/cadrumo/application/overview/pipeline_read_ports.py`)
- overview/read_calendar_item_projection.py (`src/cadrumo/application/overview/read_calendar_item_projection.py`)
- overview/read_calendar_projection.py (`src/cadrumo/application/overview/read_calendar_projection.py`)
- overview/read_operation.py (`src/cadrumo/application/overview/read_operation.py`)
- overview/read_payload.py (`src/cadrumo/application/overview/read_payload.py`)
- overview/read_ports.py (`src/cadrumo/application/overview/read_ports.py`)
- overview/read_projection.py (`src/cadrumo/application/overview/read_projection.py`)
- overview/read_request.py (`src/cadrumo/application/overview/read_request.py`)
- overview/read_result.py (`src/cadrumo/application/overview/read_result.py`)
- overview/status_report.py (`src/cadrumo/application/overview/status_report.py`)
<!-- /preserved:article -->
