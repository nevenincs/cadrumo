# Operator action and command-surface contracts

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-092` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
**Scope:** 18 files across `operator_actions`, `operator_output`, and `operator_surface`, totaling 4,319 lines, 170,666 bytes, and 33,293 measured `o200k_base` proxy tokens. All seven bounded-reader pages and assigned ranges were read. The fourth page exceeded the output limit as one combined response; its help-module range was recovered with smaller line-bounded reads. Static inspection only; no application execution or tests were run.

## Capabilities and mechanisms

The action catalogue gives operator-facing preconditions a stable action ID and a canonical target command key, plus declared input bindings. A binding names its source (`request_context`, `verdict_context`, or condition evidence); the condition-evidence form must also name the exact evidence ID. Action declarations and their arguments are strict, frozen records, and catalogue construction checks identities for uniqueness. This makes the catalogue a constrained mapping into the CLI rather than a second place to invent command strings. It includes concrete remedies for profile setup and ledger/Modelo work, including calculate, verify, and file actions. Binding and action declarations (`src/cadrumo/application/operator_actions/catalogue.py`), catalogue uniqueness (`src/cadrumo/application/operator_actions/catalogue.py`), profile setup action (`src/cadrumo/application/operator_actions/catalogue.py`), Modelo lifecycle actions (`src/cadrumo/application/operator_actions/catalogue.py`)

Precondition verdicts carry condition identity, typed facts, evidence provenance, an optional action reference, and an explicit no-recovery outcome. The included profile setup precondition emits a recovery action only when the setup state is incomplete; other paths can produce terminal or no-action verdicts. A separate projection turns verdicts into strict scalar snapshots, preserving canonical decimal representation and avoiding a dependency from the application projection back into the CLI. The action resolver then joins the referenced catalogue entry to exactly one reconciled live leaf and refuses unresolved, duplicate, partial, or wrongly sourced arguments. Required live command inputs must be accounted for before a recovery action can be presented. Verdict record types (`src/cadrumo/application/operator_actions/models.py`), no-action verdict builder and setup state (`src/cadrumo/application/operator_actions/preconditions.py`), immutable precondition snapshot (`src/cadrumo/application/operator_actions/projection.py`), live action resolution (`src/cadrumo/application/operator_surface/action_resolution.py`)

The output boundary centralizes successful operator JSON emission: it validates the registered result shape and can prepend an informational sandbox notice derived from the active bucket. That notice is limited to the sandbox marker and summary inventory; the module does not authenticate or mutate the bucket. A companion text helper keeps the banner format consistent. JSON success emission (`src/cadrumo/application/operator_output/emit.py`), sandbox notice source and conditions (`src/cadrumo/application/operator_output/sandbox_notice.py`)

The operator-surface contract describes two accepted roots (`config` and `app`), their required command families, family purpose and mutability, and backend service ownership. It fixes the modelo workflow vocabulary to calculate → verify → file, and maps a small set of parser aliases back to canonical source kinds. Invalid roots or source kinds produce a registered, localized typed refusal with a precondition verdict. The contract builder is cached so consumers in one process share its immutable declaration. Contract inventories (`src/cadrumo/application/operator_surface/contract.py`), contract construction (`src/cadrumo/application/operator_surface/contract.py`), accepted-root and source-kind checks (`src/cadrumo/application/operator_surface/contract.py`), typed contract refusal (`src/cadrumo/application/operator_surface/errors.py`)

The command ports let an outer adapter project live command metadata without making the application import its CLI framework. They carry parameter shapes, localized help, capability/effect/performance classifications, profile-authentication posture, secret-field shapes, and result/input-schema identities. Policy construction rejects inconsistent claims such as a write route without local-state and profile-custody capabilities, a destructive command without local-state effects, or a filing handoff without filing capability. `cli_argv_for` serializes supplied values in schema order, putting positional arguments before options and adding JSON output mode. Command metadata and secret-shape records (`src/cadrumo/application/operator_surface/command_ports.py`), execution-policy invariants (`src/cadrumo/application/operator_surface/command_ports.py`), argv projection (`src/cadrumo/application/operator_surface/command_ports.py`)

Manifest reconciliation is the completeness check connecting declarations to the live command tree. It rejects duplicate or orphan leaf/schema/policy/exposure rows, ambiguous canonical or alias paths, silent omissions, inconsistent external exposure, and mounted families that either lack a live path or are absent from the contract. Omitted projections require a reason, authority, and provenance in an explicit exclusion record. The reconciliation accumulates disagreements into one refusal so an operator sees a full census. Catalogue resolution additionally requires each action target to have matching result- and input-schema identities and enough argument specifications for every required input. Reconciliation row and exclusion contracts (`src/cadrumo/application/operator_surface/manifest.py`), symmetric mounted-family check (`src/cadrumo/application/operator_surface/manifest.py`), complete inventory join (`src/cadrumo/application/operator_surface/manifest.py`), catalogue-to-live-schema resolution (`src/cadrumo/application/operator_surface/manifest.py`)

## Knowledge, security, and implementation assessment

The knowledge used here is chiefly authored contract data, translation keys, and caller-projected runtime facts. Help builders create localized root/config/app guides and a bare-root landing report from a supplied active-profile label, selection state, and profile count; they do not discover profiles or read storage themselves. The command graph, result schemas, and input schemas likewise arrive through adapter ports. There is no model inference or external legal/reference corpus in this chunk. Help builders and caller-owned landing inputs (`src/cadrumo/application/operator_surface/help.py`), typed landing record (`src/cadrumo/application/operator_surface/help_models.py`)

Concrete controls include frozen strict Pydantic contracts with extra fields forbidden, exact identity joins, explicit provenance for recovery arguments, typed refusals, and policy cross-checks between claimed capabilities and effects. Secret-related command metadata is value-free: it describes field names, byte limits, and handoff/collision rules rather than carrying secret values. These modules do not perform storage, network access, or authentication; those controls must be followed through the adapters and services that consume the ports. Value-free recovery-handoff metadata (`src/cadrumo/application/operator_surface/command_ports.py`), strict operator-surface model configuration (`src/cadrumo/application/operator_surface/models.py`)

One local caller-responsibility boundary deserves verification: `cli_argv_for` silently skips absent names and ignores mapping keys that are not in the schema; it also converts values to strings without itself checking requiredness, JSON type, or choices. The port may intentionally expect validation before invocation, but the consumer must enforce that contract or malformed requests can become incomplete argv. Argument projection loop (`src/cadrumo/application/operator_surface/command_ports.py`)

There is also a maintainability seam between `RootSurface.required_children` and the mounted-family inventory. Reconciliation checks declared families against the live tree symmetrically, but the shown aggregate validators enforce exact root names and unique families without visibly checking each root’s `required_children` tuple against that family set. If both declarations are intended as authoritative requirements, they can drift unless another layer or test keeps them aligned. This is a conditional consistency risk, not evidence of a current runtime failure. Required-child declarations (`src/cadrumo/application/operator_surface/contract.py`), family reconciliation (`src/cadrumo/application/operator_surface/manifest.py`), aggregate model validators (`src/cadrumo/application/operator_surface/models.py`)

The overall separation is strong: domain-authored recovery semantics remain free of CLI imports; adapters own live command discovery; one manifest join makes omissions reviewable; and output notices are centralized. The main follow-up is to trace which outer caller validates mappings before `cli_argv_for`, and whether conformance tests tie required children to mounted families. No assigned tests were present, so the contracts and guards have not been confirmed dynamically in this inspection.

## Dependencies and follow-up

For synthesis, trace the outer command-graph adapter that implements `CommandSurfacePort`, collects `LiveLeafInventoryRow` and the other reconciliation inputs, and applies profile exposure policy. Follow catalogue action profiles into their application precondition producers and the adapter that renders resolvable actions. Confirm the caller-side argument validation before argv construction, and locate any external conformance tests for required-child alignment. Follow the sandbox notice call sites to understand where successful output receives it.

## Complete assigned-file coverage

All 18 assigned files were read in full across pages 1–7, including the explicit split ranges; no portions remain unread.

- operator_actions/__init__.py (`src/cadrumo/application/operator_actions/__init__.py`)
- operator_actions/catalogue.py (`src/cadrumo/application/operator_actions/catalogue.py`)
- operator_actions/models.py (`src/cadrumo/application/operator_actions/models.py`)
- operator_actions/ports.py (`src/cadrumo/application/operator_actions/ports.py`)
- operator_actions/preconditions.py (`src/cadrumo/application/operator_actions/preconditions.py`)
- operator_actions/projection.py (`src/cadrumo/application/operator_actions/projection.py`)
- operator_output/__init__.py (`src/cadrumo/application/operator_output/__init__.py`)
- operator_output/emit.py (`src/cadrumo/application/operator_output/emit.py`)
- operator_output/sandbox_notice.py (`src/cadrumo/application/operator_output/sandbox_notice.py`)
- operator_surface/__init__.py (`src/cadrumo/application/operator_surface/__init__.py`)
- operator_surface/action_resolution.py (`src/cadrumo/application/operator_surface/action_resolution.py`)
- operator_surface/command_ports.py (`src/cadrumo/application/operator_surface/command_ports.py`)
- operator_surface/contract.py (`src/cadrumo/application/operator_surface/contract.py`)
- operator_surface/errors.py (`src/cadrumo/application/operator_surface/errors.py`)
- operator_surface/help.py (`src/cadrumo/application/operator_surface/help.py`)
- operator_surface/help_models.py (`src/cadrumo/application/operator_surface/help_models.py`)
- operator_surface/manifest.py (`src/cadrumo/application/operator_surface/manifest.py`)
- operator_surface/models.py (`src/cadrumo/application/operator_surface/models.py`)
<!-- /preserved:article -->
