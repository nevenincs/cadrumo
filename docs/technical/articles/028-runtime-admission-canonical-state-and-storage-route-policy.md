# Runtime admission, canonical state, and storage-route policy

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-028` · **Topic:** [Application orchestration and diagnostics](../topics/application-orchestration-and-diagnostics.md)

<!-- preserved:article -->
## Scope

This chunk covers six application files (2,924 lines): local AI server reads and memory admission; the canonical operator state projection and its auth/read ports; root storage write-policy decisions; and per-session workbench capture memoization. Static review only; no app execution, runtime requests, storage writes, or model operations were performed. This review does not assess legal correctness or confirm external runtime behavior.

## Runtime lifecycle and resource boundaries

The runtime reads distinguish installed models on disk from resident models in memory, and preserve an unreadable inventory (`None`) separately from a measured-empty one. Short-timeout GET probes cover resident state and installed inventory at the address the local AI component record names; only unreachable results are cached, for a short configured interval, while successful reads remain live. Exact model matching treats an absent tag as `:latest`, because a different tag is a different download and a different memory claim. Runtime probe and model identity rules (`src/cadrumo/application/provisioning_runtime.py`) Inventory projection (`src/cadrumo/application/provisioning_runtime.py`)

This module only asks the server what it holds and judges whether a load would fit now. It pulls, loads, unloads and removes nothing: the native component engine, driven for the local AI by the desktop alone, installs the program and pulls the models the person selected, and the runtime manager runs the server. Model names come from the person's per-role selection in cadrumo-agent's catalogue, never from Cadrumo settings. Module boundary (`src/cadrumo/application/provisioning_runtime.py`)

Admission uses free memory in the binding arena, never total capacity. For a known accelerator it considers the best individual device; for a measured no-accelerator machine it uses free system memory. Unknown free capacity refuses by default, with a deliberate override that applies only to an unmeasurable state, not to a measured shortfall. On a shortfall, runtime resident data is used to estimate what Cadrumo might unload and what remains attributable to peers. A data-completeness gap deserves follow-up: resident byte fields are optional, `_attributed_resident_bytes` treats each missing size as zero, and the shortfall remainder is then labeled peer-process use. A readable resident list with unreadable sizes can therefore undercount Cadrumo's own footprint and misstate the cause. Require complete size measurements before making that attribution, or label the cause unverified. Admission and attribution (`src/cadrumo/application/provisioning_runtime.py`) Shortfall attribution (`src/cadrumo/application/provisioning_runtime.py`)

## Canonical state and readiness

`OperatorStateProjection` is a typed read projection shared by operator-facing status surfaces. It combines active-profile health, redacted auth readiness, distinct workspace-store counts, pending deadline obligations, and optional per-modelo readiness. The model-ready result has separate profile, registry, calculation-binding, and conditional ledger-preflight axes; it exposes missing inputs and marks whether per-operation profile requirements were actually assessed. Binding-source and ledger-issue action mappings are checked for exact enum coverage at import, so a newly added source cannot silently fall through without an operator-action axis. Read ports keep workspace/profile persistence behind composition contracts. Projection shape and builder (`src/cadrumo/application/state_projection.py`) Readiness axes and completeness checks (`src/cadrumo/application/state_projection.py`) Read-port contract (`src/cadrumo/application/state_projection_ports.py`)

Readiness can be captured over a stable window. Its observation includes the active profile pointer, a content digest of the profile record, and the pinned registry generation; the request set is also part of the capture domain. The common capture helper retries if those owner observations move during projection. This provides a coherent comparison coordinate, not a signature over the returned readiness data. Readiness capture (`src/cadrumo/application/state_projection.py`) Stable-window capture primitive (`src/cadrumo/application/producer_capture.py`)

One visible degradation is that deadline schedule errors are logged and converted to `pending_obligations=()`, the same value used for a successfully computed schedule with no pending rows. The projection has no accompanying computation-status field, so a consumer can render an empty list without knowing whether the schedule was unavailable. Trace the consumers and consider carrying an explicit unavailable/degraded state. Deadline projection fallback (`src/cadrumo/application/state_projection.py`)

Auth projection distinguishes a caller-supplied state from a route-witnessed auth snapshot: the former cannot borrow current-route credentials for a live backend probe, while the latter is consumed inside the active auth projection span. Invalid provider selectors fail closed; certificate configuration additionally requires an existing effective path. A live backend may lower readiness but is not used to promote incomplete configuration. Auth projection and route handling (`src/cadrumo/application/state_projection_auth.py`) Projection entry paths (`src/cadrumo/application/state_projection.py`)

## Write policy and memoized work

The root write-policy query allows bootstrap-root and non-profile-bound routes, allows guarded mutations only on an active-bucket route, and returns typed refusals for root-fallback and explicit database URL routes. It reclassifies stale default settings against a live active-profile pointer, while respecting explicitly set database configuration. Unknown route values raise instead of falling through to allow. The CLI is expected to consult this before opening profile storage; that caller ordering is described here but is not exercised in this static pass. Write-route decision (`src/cadrumo/application/storage_write_policy.py`)

Workbench memoization belongs to one authenticated session and keys the reusable calendar/agenda work by profile content, work-unit and filing revisions, date, authority generation, and AEAT evidence revision. Key/value swaps and close are locked; concurrent same-key builds may duplicate work, but only a complete pair is stored. The composition owner must close the memory on sign-out, handover, or expiry, as its contract describes. Session memo key and lifecycle (`src/cadrumo/application/workbench_capture_memory.py`)

## Coverage appendix

- provisioning_runtime.py (505 lines) (`src/cadrumo/application/provisioning_runtime.py`)
- state_projection.py (1,493 lines) (`src/cadrumo/application/state_projection.py`)
- state_projection_auth.py (438 lines) (`src/cadrumo/application/state_projection_auth.py`)
- state_projection_ports.py (86 lines) (`src/cadrumo/application/state_projection_ports.py`)
- storage_write_policy.py (294 lines) (`src/cadrumo/application/storage_write_policy.py`)
- workbench_capture_memory.py (108 lines) (`src/cadrumo/application/workbench_capture_memory.py`)
<!-- /preserved:article -->
