# Workflow results, snapshots, and history disclosure

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-110` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
## Scope and method

This chunk contains five workflow application modules totaling 1,546 lines, 64,551 bytes, and 13,269 measured proxy tokens. I read all assigned lines across the three bounded helper pages. The code defines persisted workflow-result contracts, serializable snapshots, profile-bound run-history reads, and the operator workflow-state envelope. This is static analysis; storage adapters, access-policy hosts, and frontend behavior were not exercised.

## Recorded workflow results and disclosure

`run_models.py` uses strict frozen Pydantic contracts and closed workflow-stage/detail variants to constrain persisted results. A result is terminal (`DONE` or `ABORTED`), carries ordered steps, and validates consistency among final stage, abort reason, failed preconditions, and refusal details. Typed deadline contexts distinguish binding, overdue, and informational cases; their validators restrict which dates may appear for each shape. Site-health facts retain stable alert/status codes and numeric status, retry, count, and time fields while excluding source URLs, marker text, HTML, and evidence prose. Obligation and recovery facts likewise favor stable IDs, legal references, amounts, and dates over raw recovery instructions. run_models.py (`src/cadrumo/application/workflow/run_models.py`) run_models.py (`src/cadrumo/application/workflow/run_models.py`) run_models.py (`src/cadrumo/application/workflow/run_models.py`) run_models.py (`src/cadrumo/application/workflow/run_models.py`) run_models.py (`src/cadrumo/application/workflow/run_models.py`) run_models.py (`src/cadrumo/application/workflow/run_models.py`) run_models.py (`src/cadrumo/application/workflow/run_models.py`)

`compute_run_id` hashes a composite of taxpayer ID, model, period identity, and start time, then keeps a 16-character lowercase hexadecimal prefix. That avoids placing the tax ID directly in the identifier, while the input composition makes IDs deterministic for the same run facts. run_models.py (`src/cadrumo/application/workflow/run_models.py`)

`run_projection.py` is a serialization boundary for read results. It snapshots obligations, typed step details, site-health facts, and a terminal run; reconstruction routes detail variants through Pydantic adapters so model-specific constraints are rechecked. It projects only the terminal step, verifies terminal/abort consistency, and checks that summary period, obligation period, and alert run ID agree. This reduces the chance that a persisted canonical record is flattened into an unchecked or inconsistent public shape. run_projection.py (`src/cadrumo/application/workflow/run_projection.py`) run_projection.py (`src/cadrumo/application/workflow/run_projection.py`) run_projection.py (`src/cadrumo/application/workflow/run_projection.py`) run_projection.py (`src/cadrumo/application/workflow/run_projection.py`)

## Run-history operations and profile boundary

The application exposes two read operations: exact-run lookup and run inventory. Requests are credential-free but require a profile UUID; exact lookup validates the 16-character run ID and can carry an expected period. Executors receive explicit profile-bound ports, verify the requested profile matches both operation context and factory result, load by exact run ID, and check stored identity and period consistency before projecting. The list path validates each canonical record before creating a public inventory projection. run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_ports.py (`src/cadrumo/application/workflow/run_read_ports.py`) run_read_ports.py (`src/cadrumo/application/workflow/run_read_ports.py`)

Receipt projectors require the expected operation definition and subject, success, no side effect, and no refusal detail before exposing the public result. The exact-run registration binds a request with an explicit expected period to selected-period access; omitting the period requires whole-profile access. Run inventory always requires period-independent admission, which is appropriate for disclosing a complete cross-period list. On initial submission/start, the resolver rechecks the exact run in current profile storage; admission replay verifies the stored admission scope and does not retarget a request to a newly selected profile or run. Result subjects are run-specific for exact reads and profile-specific for inventory. run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`)

The `WorkflowRunReader` protocol exposes exact load and newest-first listing, while its factory is keyed by an immutable bucket ID and promises no fallback bucket. That makes the storage choice explicit at the interface boundary. Whether a concrete adapter enforces bucket isolation and encrypted-at-rest handling is outside this chunk. run_read_ports.py (`src/cadrumo/application/workflow/run_read_ports.py`) run_read_ports.py (`src/cadrumo/application/workflow/run_read_ports.py`)

## Operator workflow state and assessment

`WorkflowState` documents an encrypted single-envelope persistence model and defines auth state, invoice and ledger review annotations, bucket events, and update time. Its convenience method resolves the active profile within a bundled authority operation; active bucket selection follows the shared selector/capsule logic and returns no bucket for a selector without a current capsule. The type warns callers not to report every unresolved profile as “missing”: locked and genuinely absent records must remain distinguishable through the richer resolver. The encryption and committed-capsule behavior are architectural documentation here, not demonstrated by the model itself. state_models.py (`src/cadrumo/application/workflow/state_models.py`) state_models.py (`src/cadrumo/application/workflow/state_models.py`) state_models.py (`src/cadrumo/application/workflow/state_models.py`) state_models.py (`src/cadrumo/application/workflow/state_models.py`)

The strongest properties are strict typed terminal records, cross-field consistency checks, a privacy-conscious snapshot boundary, exact identity checks, and period-aware authorization for read operations. Follow-up review should inspect the production access-registration and persistence adapters to confirm their policy bindings and bucket enforcement, and check whether the 16-character derived identifier meets the project’s correlation and collision requirements. This chunk contains no tests or live storage implementation, so those deployment properties remain unverified.

## Complete assigned-file coverage

- run_models.py (`src/cadrumo/application/workflow/run_models.py`) — lines 1–690
- run_projection.py (`src/cadrumo/application/workflow/run_projection.py`) — lines 1–356
- run_read_operation.py (`src/cadrumo/application/workflow/run_read_operation.py`) — lines 1–367
- run_read_ports.py (`src/cadrumo/application/workflow/run_read_ports.py`) — lines 1–37
- state_models.py (`src/cadrumo/application/workflow/state_models.py`) — lines 1–96
<!-- /preserved:article -->
