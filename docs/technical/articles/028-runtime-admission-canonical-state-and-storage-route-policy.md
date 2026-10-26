# Runtime admission, canonical state, and storage-route policy

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-028` · **Topic:** [Application orchestration and diagnostics](../topics/application-orchestration-and-diagnostics.md)

<!-- preserved:article -->
## Scope

This chunk covers five application files (2,422 lines): the canonical operator state projection and its auth/read ports; root storage write-policy decisions; and per-session workbench capture memoization. Static review only; no app execution, runtime requests, storage writes, or model operations were performed. The load admission and installed-state boundary is described from the sources it now lives in. This review does not assess legal correctness or confirm external runtime behavior.

## Load admission and installed state

Cadrumo does not admit a local model load. cadrumo-agent loads every local model and is the only judge of whether one fits the memory free; it refuses a load that does not fit with `model_does_not_fit`, and the agent service maps that refusal to `ModelRunRefusalCode.MODEL_DOES_NOT_FIT`, which the agent provider raises as `LLMContentionError`. That error is never retryable, because the condition decays when the load on the computer changes, not on a timer. It is distinct from `LLMBusyError`, which counts only this process's own on-host runs against the configured concurrency and asks nobody. Load refusal and mapping (`src/cadrumo/adapters/outbound/llm/providers/agent.py`) Error contract (`src/cadrumo/adapters/outbound/llm/errors.py`)

Python asks the local AI server nothing. A role's installed state is the agent service's reading of the `installed` flag of the catalogue the agent serves, carried on the role's lane; an absent flag is unknown and is never rendered as not installed. The local AI program's presence and version come from the components role's read-only quick status, read with a bounded timeout. Model names come from the person's per-role selection in cadrumo-agent's catalogue, never from Cadrumo settings. Only the desktop provisions the program and models: the native component engine installs the program and pulls the models the person selected, and the runtime manager runs the server. Installed state from the agent service (`src/cadrumo_agent_service/adapters/served_catalog_models.py`) Program row (`src/cadrumo/entrypoints/local_reader_operation_composition.py`) Lane judgement (`src/cadrumo/application/local_reader.py`)

The memory the application layer still reads is the installed capacity and the reported figures. A model whose catalogue size exceeds the installed system memory, and the largest NVIDIA card's installed memory when there is one, refuses as a capacity floor that setup cannot change. Free system and device memory are measured and reported by `local-reader.report` but never used to admit or refuse a load. Capacity floor (`src/cadrumo/application/provisioning.py`) Report (`src/cadrumo/application/local_reader_report.py`)

## Canonical state and readiness

`OperatorStateProjection` is a typed read projection shared by operator-facing status surfaces. It combines active-profile health, redacted auth readiness, distinct workspace-store counts, pending deadline obligations, and optional per-modelo readiness. The model-ready result has separate profile, registry, calculation-binding, and conditional ledger-preflight axes; it exposes missing inputs and marks whether per-operation profile requirements were actually assessed. Binding-source and ledger-issue action mappings are checked for exact enum coverage at import, so a newly added source cannot silently fall through without an operator-action axis. Read ports keep workspace/profile persistence behind composition contracts. Projection shape and builder (`src/cadrumo/application/state_projection.py`) Readiness axes and completeness checks (`src/cadrumo/application/state_projection.py`) Read-port contract (`src/cadrumo/application/state_projection_ports.py`)

Readiness can be captured over a stable window. Its observation includes the active profile pointer, a content digest of the profile record, and the pinned registry generation; the request set is also part of the capture domain. The common capture helper retries if those owner observations move during projection. This provides a coherent comparison coordinate, not a signature over the returned readiness data. Readiness capture (`src/cadrumo/application/state_projection.py`) Stable-window capture primitive (`src/cadrumo/application/producer_capture.py`)

One visible degradation is that deadline schedule errors are logged and converted to `pending_obligations=()`, the same value used for a successfully computed schedule with no pending rows. The projection has no accompanying computation-status field, so a consumer can render an empty list without knowing whether the schedule was unavailable. Trace the consumers and consider carrying an explicit unavailable/degraded state. Deadline projection fallback (`src/cadrumo/application/state_projection.py`)

Auth projection distinguishes a caller-supplied state from a route-witnessed auth snapshot: the former cannot borrow current-route credentials for a live backend probe, while the latter is consumed inside the active auth projection span. Invalid provider selectors fail closed; certificate configuration additionally requires an existing effective path. A live backend may lower readiness but is not used to promote incomplete configuration. Auth projection and route handling (`src/cadrumo/application/state_projection_auth.py`) Projection entry paths (`src/cadrumo/application/state_projection.py`)

## Write policy and memoized work

The root write-policy query allows bootstrap-root and non-profile-bound routes, allows guarded mutations only on an active-bucket route, and returns typed refusals for root-fallback and explicit database URL routes. It reclassifies stale default settings against a live active-profile pointer, while respecting explicitly set database configuration. Unknown route values raise instead of falling through to allow. The CLI is expected to consult this before opening profile storage; that caller ordering is described here but is not exercised in this static pass. Write-route decision (`src/cadrumo/application/storage_write_policy.py`)

Workbench memoization belongs to one authenticated session and keys the reusable calendar/agenda work by profile content, work-unit and filing revisions, date, authority generation, and AEAT evidence revision. Key/value swaps and close are locked; concurrent same-key builds may duplicate work, but only a complete pair is stored. The composition owner must close the memory on sign-out, handover, or expiry, as its contract describes. Session memo key and lifecycle (`src/cadrumo/application/workbench_capture_memory.py`)

## Coverage appendix

- state_projection.py (1,494 lines) (`src/cadrumo/application/state_projection.py`)
- state_projection_auth.py (438 lines) (`src/cadrumo/application/state_projection_auth.py`)
- state_projection_ports.py (86 lines) (`src/cadrumo/application/state_projection_ports.py`)
- storage_write_policy.py (294 lines) (`src/cadrumo/application/storage_write_policy.py`)
- workbench_capture_memory.py (110 lines) (`src/cadrumo/application/workbench_capture_memory.py`)
<!-- /preserved:article -->
