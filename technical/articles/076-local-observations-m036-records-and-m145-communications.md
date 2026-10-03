# Local observations, M036 records, and M145 communications

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-076` · **Topic:** [Modelo work and revision lifecycle, part 1](../topics/modelo-work-and-revision-lifecycle-part-1.md)

<!-- preserved:article -->
**Scope:** 14 implementation files in src/cadrumo/application/modelo; 4,564 lines, 191,699 bytes, and 39,550 manifest-measured tokens. All bounded-reader pages 1–8 were inspected in sequence. No application execution or tests were run.

## Capabilities and mechanism

**Lifecycle facts and chronology.** The lifecycle-advisory builder captures facts while the canonical revision and work unit are still in hand. For Modelo 210 it records the selected filing window and legal/source references; for Modelo 184 it projects member NIF, name, percentage, attributed amount, and registry-declared target casilla. Strict projections verify period/model membership and numeric bounds. The shared lifecycle clock gate names each persisted instant an action must follow, covering work-unit/revision creation and prior filing timestamps before calculate, verify, file, amend, rename, or discard writes. It prevents a timestamp that would make the resulting catalogue unreadable on its next load. lifecycle_advisories.py (`src/cadrumo/application/modelo/lifecycle_advisories.py`) and lifecycle_clock_gate.py (`src/cadrumo/application/modelo/lifecycle_clock_gate.py`).

The registered modelo-history operation retains complete canonical event projections, validates bucket membership, uniqueness, and chronological order, and scopes disclosure to one period when the selector identifies a tax period. Censal selectors that are not tax periods remain valid filters and use the whole-profile policy. This is the human CLI/TUI full-history surface; the prior chunk’s timeline operation is a separate metadata-only projection. lifecycle_history_operation.py (`src/cadrumo/application/modelo/lifecycle_history_operation.py`).

**Operator local observations.** An operator can record numeric casilla values into the pending-local observation layer or clear that override. Recording resolves the law-selected registry revision, refuses Modelo 303, printed aliases, unknown IDs, nonnumeric fields, non-Decimal values, and an empty set. It stores source kind operator_manual and a revision stamp, while recording actor, reason, previous effective source kind and replaced values in the override audit. Existing official observations remain below the pending layer; clearing restores the official layer as effective. The observation envelope and lifecycle event are batched together. local_observation_actions.py (`src/cadrumo/application/modelo/local_observation_actions.py`) and local_observation_actions.py (`src/cadrumo/application/modelo/local_observation_actions.py`).

The registered mutation accepts at most 4,096 sorted, unique canonical decimal pairs, exact profile and period, and a record-or-clear shape. It requires a fresh COMMIT admission, checks active profile, completes the worker before cancellation, and verifies the returned projection against the persisted observation layers and terminal receipt. Spreadsheet parsing is a separate small adapter for CSV/TXT/XLSX: it finds aliased two-column headers or falls back to columns A/B, aggregates malformed rows, refuses duplicate identifiers and ambiguous Spanish values such as a lone dot before three digits, and rejects XLSX formulas. It leaves registry membership checks to the observation service. local_observation_operation.py (`src/cadrumo/application/modelo/local_observation_operation.py`), local_observation_spreadsheet.py (`src/cadrumo/application/modelo/local_observation_spreadsheet.py`), and local_observation_spreadsheet.py (`src/cadrumo/application/modelo/local_observation_spreadsheet.py`).

**Modelo 036 recording.** This service records an operator’s assertion that an M036 was already filed through AEAT or in person; it never files the declaration. It validates that profile and bucket agree, derives a content-addressed identity from profile, event kind, date, and optional justificante, requires an initial alta, and treats baja as terminal. An identical retry resolves to the same declaration identity. The stored declaration and its version-1 censo event are written atomically. m036_lifecycle.py (`src/cadrumo/application/modelo/m036_lifecycle.py`).

Registered M036 read paths separate human detail from an agent query. Human list/view and record receipts preserve the justificante and note; the query returns lifecycle dates/kinds and presence flags without raw receipt text or notes. The worker checks registry ownership and exact profile, while the declaration write is tracked through a commit fence that correlates actual repository activity with its terminal effect. Read and write scopes are whole-profile because M036 declarations do not carry tax filing periods. m036_operation.py (`src/cadrumo/application/modelo/m036_operation.py`).

**Unresolved Modelo 123 count rule.** The M123 gate blocks a period holding captured retenciones at calculation, verification, local filing, and export. The source explains that official authority does not currently settle the “number of rentas” unit for cases such as split instalments or income recognized and paid in different quarters, and the engine’s manual casillas ignore captured evidence. Refusing is safer than either silently ignoring evidence or inventing a count rule. The check also runs downstream so evidence captured after calculation cannot slip into a complete-looking filed/exported revision. m123_count_authority_gate.py (`src/cadrumo/application/modelo/m123_count_authority_gate.py`).

**Modelo 145 local communication.** A registry-backed ownership contract permits only communication, payer delivery, and export surfaces, and refuses filing, deadline, live-read, portal, submission, receipt, or amendment links. Five registered commands create, validate, export, mark delivery, and mark local completion. They delegate to the canonical record service. A write gate intercepts the concrete record/event persistence call, publishes UNKNOWN before allowing the worker through its irreversible section, then records the actual effect. Export output remains in encrypted result custody; the bucket event carries the receipt rather than the bytes, whose encoded length and digest are checked against the payload. The period type is limited to communication and variation. m145_communication.py (`src/cadrumo/application/modelo/m145_communication.py`), m145_communication_operation.py (`src/cadrumo/application/modelo/m145_communication_operation.py`), and m145_communication_period.py (`src/cadrumo/application/modelo/m145_communication_period.py`).

## Knowledge, security, and quality

Local observations, M036 records, and M145 communication records are explicitly local assertions or work products. None is an AEAT submission or acceptance. M036’s optional justificante is recorded as supplied metadata, not verified against a receipt store in this lifecycle service. Operator-manual observations may help later calculation prefill but remain nonofficial and cannot satisfy filing-grade readiness. M123 is a deliberate no-action blocker pending a defensible official count authority.

The request and result models use secure hidden-input configuration; M145 creates a particularly sensitive dataset about payer, family circumstances, and tax fields. Its export payload is retained only in the encrypted operation result until the authorized local CLI reads it, and history stores a digest/receipt. Human M036 results include the local note and justificante, while the agent query drops these raw strings. Local-observation audit objects retain replaced casilla values, and spreadsheet diagnostics name malformed row values to make repair possible; callers should keep those details within the protected operator channel.

The spreadsheet readers currently load complete CSV bytes or iterate all workbook rows into memory, with no explicit byte/row cap in these modules. Very large local files could therefore consume substantial memory before the bounded operation result is assembled. This pass did not test cancellation races, profile isolation, M036 sequencing, or M145 write-fence failures.

## Full file coverage

- M210 deadline and M184 member handoff facts: lifecycle_advisories.py (`src/cadrumo/application/modelo/lifecycle_advisories.py`)
- Monotonic lifecycle timestamps: lifecycle_clock_gate.py (`src/cadrumo/application/modelo/lifecycle_clock_gate.py`)
- Registered full Modelo event history: lifecycle_history_operation.py (`src/cadrumo/application/modelo/lifecycle_history_operation.py`)
- Record and clear operator-supplied pending observations: local_observation_actions.py (`src/cadrumo/application/modelo/local_observation_actions.py`)
- Exact-profile secure observation mutation operation: local_observation_operation.py (`src/cadrumo/application/modelo/local_observation_operation.py`)
- CSV/TXT/XLSX observation import: local_observation_spreadsheet.py (`src/cadrumo/application/modelo/local_observation_spreadsheet.py`)
- M036 declaration identity, sequence, persistence and audit event: m036_lifecycle.py (`src/cadrumo/application/modelo/m036_lifecycle.py`)
- M036 persistence and event capabilities: m036_lifecycle_ports.py (`src/cadrumo/application/modelo/m036_lifecycle_ports.py`)
- Registered M036 record/read/query operation family: m036_operation.py (`src/cadrumo/application/modelo/m036_operation.py`)
- Exact-profile M036 operation port bundle: m036_operation_ports.py (`src/cadrumo/application/modelo/m036_operation_ports.py`)
- Cross-stage M123 unresolved count refusal: m123_count_authority_gate.py (`src/cadrumo/application/modelo/m123_count_authority_gate.py`)
- Registry-grounded M145 ownership contract: m145_communication.py (`src/cadrumo/application/modelo/m145_communication.py`)
- Registered M145 create, validate, export and local state transitions: m145_communication_operation.py (`src/cadrumo/application/modelo/m145_communication_operation.py`)
- M145 communication/variation period tokens: m145_communication_period.py (`src/cadrumo/application/modelo/m145_communication_period.py`)
<!-- /preserved:article -->
