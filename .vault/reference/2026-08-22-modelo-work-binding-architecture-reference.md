---
tags:
  - '#reference'
  - '#modelo-work-binding-architecture'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:13b42826c71a569263f8e2ddc872c2a08cfdcf4447ce02ddadd21fb45fb4abb9'
related:
  - "[[2026-06-14-bindings-interface-hardening-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
---
# `modelo-work-binding-architecture` reference: `CLI, calculation, binding, and secure-storage architecture`

This reference traces the operator-facing modelo lifecycle from CLI parsing through registry selection, binding resolution, calculation, verification, export, and encrypted persistence. It also records the supported shapes and current gaps for repeating records, generalized sheet row sets, and inventory.

## Summary

The CLI is an inbound adapter. Modelo commands parse identifiers and raw tokens, activate the profile session, and delegate to application services. They do not call calculation formulas or persistence primitives directly. A `WorkUnit` pins the active bucket, modelo, filing year, period, and registry revision. Calculation resolves a validated `RegistrySnapshot`, constructs the source mesh, executes the registry engine, and persists an immutable `CalculationRevision`; verification and internal filing advance that lifecycle without changing registry authority.

The ordinary operator sequence is:

1. `aeat app modelo work create --modelo CODE --year YYYY --period TOKEN` creates or reuses the content-addressed work unit after registry and profile checks.
2. `aeat app modelo describe`, `casillas`, `formulas`, `requires`, and `bindings list --missing` expose the selected schema and unresolved sources.
3. `aeat app modelo bindings resolve --modelo CODE --year YYYY --period TOKEN --binding ID=VALUE` previews permitted overrides without mutation.
4. `aeat app modelo work wizard` prompts for the promptable subset, while `work calculate` accepts canonical `--casilla`, `--binding`, `--relation`, and typed `--row` inputs.
5. `work revision`, `observations`, and `review` inspect the frozen calculation result; `work verify` runs registry, provenance, clean-state, and workflow gates; `work file` creates an internal presented record; `modelo export` renders a local AEAT file and never submits it to AEAT.

The principal CLI registration and orchestration sites are `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:296`, `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py:132`, and `src/cadrumo/entrypoints/cli/_modelo_export_cli.py:123`. Input-channel typing is centralized in `src/cadrumo/application/modelo/_calculate_input.py:369`; calculation and source resolution are in `src/cadrumo/application/modelo/_calculation_actions.py:220` and `src/cadrumo/application/aggregation/_source_mesh.py:813`; immutable revision persistence is in `src/cadrumo/application/modelo/_revision_persistence.py:302`.

A binding is not an object attached to a work unit. `DataBindingDefinition` in `src/cadrumo/domain/calculations/registry/_schema.py:656` is a registry-owned declaration of a named source edge: binding id, closed source kind, typed selector, aggregation operation, optional enum, grounding, and prefill policy. The selected `ModeloRevision` determines which bindings exist. A user satisfies one by populating its owning source repository, by supplying a permitted temporary scalar `--binding ID=VALUE`, or by supplying the distinct `--relation RELATION_ID=VALUE` channel. Deterministic ledger and invoice sources refuse caller substitution; selected manual, profile, previous-filing, and carry channels have their own override policies. Date-valued profile facts must come from the profile and cannot be smuggled through the decimal/string override channel.

Binding resolution is typed and provenance-bearing. A `CalculationSourceResolution` can carry decimal bindings, enum bindings, date bindings, row-indexed binding values, relation values, bound casillas, typed detail rows, source record ids, and diagnostics. Precedence is deterministic and source ownership is checked; duplicate row ownership and caller substitution of locked sources fail rather than silently winning. Unhandled source kinds produce explicit diagnostics.

Complex repeating structures are not encoded as one scalar binding or opaque mapping. Registry bindings declare one binding per row field, share a grouping and record type, and use the `rows` aggregation operation. The runtime value is keyed by binding id and one-based row index. Direct CLI rows are strict discriminated models supplied as repeatable arguments such as `--row 'miembro nif=12345678A porcentaje=40 importe=10000'` or `--row 'operador codigo_pais=DE nif_comunitario=DE123456789 razon_social="DE Auto GmbH" clave_operacion=E importe=50000'`. The current direct allowlist covers M184 members, M232 related parties, M347 counterparties, and M349 operators and corrections; the union also includes the supported M210 income grouping. These rows are validated before calculation, frozen in `CalculationRevision.detail_rows`, and participate in deterministic revision identity.

M720 foreign assets illustrate the generalized registry row-binding shape. Asset class, country, currency, identifier, value, and acquisition date are separate bindings sharing `per_foreign_asset`; application logic joins values by row index rather than hardcoding binding ids. M720 is not currently supported by direct `--row`. The broader Google Sheets calculation workflow exports a `Detalle` row set, pulls `(grouping, row_index, binding, value)` cells, and can assemble typed observations. The inspected pull command returns those observations but does not by itself prove persistence into a work-unit calculation revision; this boundary must not be described as an attachment operation.

Secure storage is below the application services. `SecureObjectRepository` encrypts payloads with authenticated encryption and binds ciphertext to namespace, HMAC-derived object-key digest, and schema version. Work units and calculation revisions live in profile-local FINANCIAL namespaces. A work unit contains lifecycle coordinates and pointers, not the complete form. A calculation revision freezes canonical casilla inputs, scalar overrides, row bindings, relation overrides, calculated values, typed observations, evidence, provenance, and detail rows. Binary source documents use encrypted content-addressed attachment storage, while parsed business data belongs in typed domain repositories.

Inventory follows that typed-domain pattern. `InventoryLedger` is a separate encrypted aggregate keyed by activity and year, with valuation method, opening layers, movements, and closing stock. Operators manage it through `aeat app ledger inventory create`, `ledger inventory movement add`, and `ledger inventory valuation preview`. No `BindingSourceKind.INVENTORY` or enrolled inventory resolver was found in the calculation source mesh. Consequently inventory is currently a secure standalone register, not an automatically resolved modelo binding. Connecting it to a modelo requires an architectural addition: registry binding declarations plus an enrolled resolver that projects legally grounded scalars or rows, or deliberate reuse of an existing ledger aggregation where the semantics truly match. It should not be implemented as a generic attach command or opaque binding blob.

The durable boundary is therefore: the registry defines what a filing revision requires; secure source domains own complex reusable facts; the application source mesh resolves those facts into typed binding channels; the registry engine calculates a snapshot; and the encrypted calculation revision preserves the exact inputs, rows, provenance, and results used for replay and audit.
