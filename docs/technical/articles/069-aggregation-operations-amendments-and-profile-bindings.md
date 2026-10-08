# Aggregation operations, amendments, and profile bindings

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-069` · **Topic:** [Modelo work and revision lifecycle, part 1](../topics/modelo-work-and-revision-lifecycle-part-1.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 14 modules, 5,037 physical lines, 218,421 bytes, and 44,680 measured `o200k_base` proxy tokens across eight bounded pages. It includes error contracts, registered aggregation and audit operations, externally evidenced amendment workflows, profile binding resolution, and two verification advisories. The source was inspected statically; no application code or tests were run and no source was changed. The token count is a measured proxy, not a claim about model context limits.

## Product capabilities

The Modelo error layer gives lifecycle, calculation, filing, amendment, workflow, and edit refusals stable typed identities. Rich exceptions can carry a locale-neutral precondition verdict separately from rendered text; workflow errors keep the full run result private and expose primitive abort context plus its terminal verdict. Edit refusals are converted to one registered error family without copying submitted addresses, facts, or evidence into the generic operation error. Precondition carrier (`src/cadrumo/application/modelo/action_errors.py`) Workflow refusal boundary (`src/cadrumo/application/modelo/action_errors.py`) Edit refusal projection (`src/cadrumo/application/modelo/action_errors.py`)

`modelo.aggregate` is a registered, exact-profile operation for supported non-invoice withholding, counterpart, and foreign-asset aggregates. Its hidden, strict request DTO excludes caller-supplied retención rows; those are read from the storage used by calculations. The public result is a bounded summary with per-clave counts and totals, absent source families, and generation metadata, not raw perceptor records. An optional payment-evidence request is limited to Modelos 111 and 123 and cannot be mixed with other providers. The executor validates the active profile, resolves cadence and provider data, checks a transaction-catalogue revision around a targeted ledger read, and delegates capture to the canonical withholding service. A revision mismatch refuses before effect; storage ambiguity is reflected honestly in operation effect state. Result projection checks the terminal receipt, refusal/effect shape, and a 16 KB serialized-result cap. Aggregate request and bounds (`src/cadrumo/application/modelo/aggregate_operation.py`) Receipt-checked result projection (`src/cadrumo/application/modelo/aggregate_operation.py`) Operation access scope (`src/cadrumo/application/modelo/aggregate_operation.py`) Public evidence DTO (`src/cadrumo/application/modelo/aggregate_public.py`)

The amendment service starts only from a current filing record linked to a latest AEAT-confirmed external-evidence baseline. It uses the current in-force revision as the correction source, validates canonical override casillas, enforces period-appropriate amendment kinds and the pre-rectificativa liability-direction rule, requires M303 rectificativa motive evidence where applicable, and requires explicit detail rows for models where those rows constitute the declaration. It rejects no-op or duplicate amendment revisions, preserves or rebuilds casilla provenance, validates M303 filing-instance evidence, and captures a fresh ledger anchor when contributing transaction IDs exist. The resulting local filing envelope is pending external confirmation and has no external-attestation marker. Catalogue revisions, filing/work-unit pointers, observation writes, and the amendment bucket event are committed in one secured unit of work. Amendment action (`src/cadrumo/application/modelo/amendment_actions.py`) Fresh ledger anchor (`src/cadrumo/application/modelo/amendment_actions.py`) Atomic side effects (`src/cadrumo/application/modelo/amendment_actions.py`) Public pending amendment shape (`src/cadrumo/application/modelo/amendment_projection.py`)

A separate amendment-context read operation returns the exact filing, work unit, calculation snapshot, casilla rows, permitted amendment kinds, and M303 motive applicability for a guided correction. Its validator binds all these pieces to the same profile, unit, revision, period, and casilla identity. Amendment context contract (`src/cadrumo/application/modelo/amendment_context_operation.py`) Registered context read (`src/cadrumo/application/modelo/amendment_context_operation.py`)

The audit operation family separates three purposes. Human view/check returns the full canonical bundle or verification report; the agent query omits finding prose, bundle notes, and arbitrary source-record addresses while retaining hashes, object types, sizes, and pass/fail metadata; and an explicit CLI-only export writes the existing ZIP output and returns a receipt. The read path uses the existing evidence service and adds no payload-record loader. Export uses a commit fence and tracks whether writing was not attempted, confirmed, or uncertain. Agent query shape (`src/cadrumo/application/modelo/audit_operation.py`) Fenced human export (`src/cadrumo/application/modelo/audit_operation.py`) Purpose-specific access (`src/cadrumo/application/modelo/audit_operation.py`)

Binding support has two related outcomes. The readiness query reports which registry profile-sourced bindings can be resolved from the active profile, choosing a period from the revision when no period is supplied and conservatively treating missing profile or authority state as unresolved. Calculation binding assembly maintains a precedence stack in which profile values are lowest, then source mesh, borrador, and caller overrides; it rejects values on the wrong decimal/enum/boolean channel and derives declaration metadata from filing-year, period, and declaration-kind semantic roles. Profile binding readiness (`src/cadrumo/application/modelo/binding_readiness.py`) Source-tier assembly (`src/cadrumo/application/modelo/binding_resolution.py`) Channel and metadata contracts (`src/cadrumo/application/modelo/binding_resolution.py`)

Modelo 100 borrador values are consumed only when an explicit snapshot ID is selected and the registry marks each binding as AEAT-prefilled. The resolver checks model/year/period and profile axes, snapshot lifecycle and revision-carry validity, rejects non-eligible bindings, and leaves caller-owned bindings untouched. Decimal values pass a finite European-number parser; enum values use their declared channel. The sourced binding IDs and snapshot fingerprint are retained as provenance. Persistence degradation becomes a diagnostic resolution rather than silently passing an invented value. Explicit snapshot resolution (`src/cadrumo/application/modelo/borrador_binding.py`) Source-mesh adapter (`src/cadrumo/application/modelo/borrador_binding.py`)

The Art. 20 and Art. 52 collectors provide non-blocking warnings for possible omitted or exceeded Renta deductions based on semantic casilla roles and dated governed facts. They do not decide entitlement from incomplete profile evidence. Art. 20 advisory (`src/cadrumo/application/modelo/art20_advisory.py`) Art. 52 advisory (`src/cadrumo/application/modelo/art52_advisory.py`)

## Security, quality, and limits

Strong controls include exact profile and active-bucket checks, hidden-input DTOs, closed provider/model combinations, bounded output schemas, typed refusal codes, receipt/result identity matching, and explicit operation effects around irreversible work. The aggregation public projection avoids perceptor identity even when protected request and storage records contain it. Audit purpose and frontend scopes differ deliberately: an MCP query gets only the redacted integrity view, while raw human bundle details and ZIP export are CLI-scoped. The amendment flow's compare-and-swap catalogue revisions and co-commit reduce split-brain records and missing history events.

Some trust boundaries remain outside this chunk. The aggregate carries per-clave totals and generation details that are still sensitive filing data; access policy is profile-scoped, but downstream transport authorization and retention are not fully proven here. The audit ZIP operation accepts an explicit output `Path` and delegates writing/verification to `EvidenceBundleService`; path confinement, overwrite behavior, and cleanup require review in that service. Borrador source provenance has no terminal-origin declaration because the source is treated as captured AEAT prefill rather than a provider-backed live fact, so its trust depends on snapshot custody and revision-carry checks.

The Art. 52 advisory dates its sublimit at `revision.valid_to` and falls back to today's Madrid date when the selected revision has no end date. For an open-ended revision used on a non-current filing year, correctness therefore depends on how the caller/revision coordinates constrain that date; verify historical and future-year behavior. Art. 52 date selection (`src/cadrumo/application/modelo/art52_advisory.py`) Borrador eligibility and missing binding readiness are fail-closed in different ways: an ineligible explicitly selected snapshot raises a refusal, while a missing authority/profile in the readiness query becomes an empty resolved set. Confirm the UI distinguishes “not resolved” from an actual absent user fact. Readiness fallback (`src/cadrumo/application/modelo/binding_readiness.py`)

Static inspection does not establish current statutory correctness, encrypted repository implementation, access-policy enforcement by every frontend, transaction isolation, or the user-visible recovery path after operation interruption. Follow-up synthesis should connect these operations to their registered public schemas and adapters, inspect the EvidenceBundleService path fence, and verify the M303 amendment evidence/reconciliation history end to end.

## Coverage appendix

All 14 assigned files were read fully across eight bounded pages; no unread ranges remain.

- modelo/action_errors.py (`src/cadrumo/application/modelo/action_errors.py`) — 1–573
- modelo/aggregate_operation.py (`src/cadrumo/application/modelo/aggregate_operation.py`) — 1–881
- modelo/aggregate_public.py (`src/cadrumo/application/modelo/aggregate_public.py`) — 1–215
- modelo/amendment_action_ports.py (`src/cadrumo/application/modelo/amendment_action_ports.py`) — 1–50
- modelo/amendment_actions.py (`src/cadrumo/application/modelo/amendment_actions.py`) — 1–999
- modelo/amendment_context_operation.py (`src/cadrumo/application/modelo/amendment_context_operation.py`) — 1–256
- modelo/amendment_projection.py (`src/cadrumo/application/modelo/amendment_projection.py`) — 1–50
- modelo/art20_advisory.py (`src/cadrumo/application/modelo/art20_advisory.py`) — 1–89
- modelo/art52_advisory.py (`src/cadrumo/application/modelo/art52_advisory.py`) — 1–145
- modelo/audit_operation.py (`src/cadrumo/application/modelo/audit_operation.py`) — 1–585
- modelo/audit_operation_ports.py (`src/cadrumo/application/modelo/audit_operation_ports.py`) — 1–27
- modelo/binding_readiness.py (`src/cadrumo/application/modelo/binding_readiness.py`) — 1–246
- modelo/binding_resolution.py (`src/cadrumo/application/modelo/binding_resolution.py`) — 1–460
- modelo/borrador_binding.py (`src/cadrumo/application/modelo/borrador_binding.py`) — 1–461
<!-- /preserved:article -->
