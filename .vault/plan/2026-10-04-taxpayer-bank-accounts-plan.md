---
tags:
  - '#plan'
  - '#taxpayer-bank-accounts'
date: '2026-10-04'
tier: L2
related:
  - '[[2026-10-04-taxpayer-bank-accounts-adr]]'
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
  - '[[2026-06-24-m303-refund-fichero-block-adr]]'
  - '[[2026-06-24-m303-refund-election-adr]]'
  - '[[2026-10-04-modelo-360-solicitud-custody-adr]]'
  - '[[2026-06-10-ledger-amount-direction-adr]]'
  - '[[2026-07-01-determinism-replay-residual-adr]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:f8da3e7ca25aa47240664a27b141db41b4afeb05d33d6aef7b146190423ba9e5'
---

# `taxpayer-bank-accounts` plan

Make the taxpayer's own bank accounts ledger entities and bind them to every modelo charge and refund role.

## Description

Approved 2026-10-04. Basis: the operator's explicit authorization given 2026-10-04, "implement support for both … store and link our own iban as part of the ledger setup and bindings to it", plus the operator's standing instruction that modifications are pre-approved and work proceeds without approval gates.

The work makes own bank accounts first-class ledger entities in an encrypted register with role designations, links transactions to them, resolves every consuming modelo's charge and refund account from that register at the export boundary, reconciles the Modelo 360 register with it, closes the account-adjacent 303 refusals and adds the TUI surfaces. Evidence: `2026-10-04-taxpayer-bank-accounts-research` (official rules) and `2026-10-04-taxpayer-bank-accounts-reference` (code map, 303 refusal inventory, ledger defects D1 to D10).

Decision coverage: `2026-10-04-taxpayer-bank-accounts-adr` governs every Phase. `2026-06-21-m303-carry-reconciliation-adr` (DID predicate, payment and prior-domiciliation elections) and `2026-06-24-m303-refund-fichero-block-adr` (encrypted-only account fields, REDEME, Marca SEPA, no-account refusal), both as amended 2026-10-04, govern P03 and P05. `2026-06-24-m303-refund-election-adr` governs P03.S12. `2026-10-04-modelo-360-solicitud-custody-adr` as amended governs P04 and P06.S21. `2026-06-10-ledger-amount-direction-adr` and `2026-07-01-determinism-replay-residual-adr` constrain P02 (direction authority, deterministic ids). No further costly decision is needed inside this scope.

Out of scope, recorded for their owners: the 303 envelope software identity (export-parity work), the autoconsumo [27] result route (open high finding in `2026-09-30-modelo-editor-workbench-audit`), simplified-regime filing evidence, carry ingress and the other class B refusals in the reference; the Modelo 210 party-scoped accounts (`2026-08-16-m210-export-authority-adr`); copying invoice tax facts onto linked transactions (ledger defect D4, which needs its own decision); pending TUI review navigation (D9); non-ES domiciliación for 303 and non-IBAN foreign accounts, which stay refused per the ADR; and the 360/232 página 2 layout marker, which another session owns. Fix in place: reuse the secure-model-document kernel, the existing `RefundAccount`/`ChargeAccount` projections and refusals, and the existing ledger register CLI families; add no parallel mechanism. Use synthetic accounts only (for example ES9121000418450200051332).

## Steps

### Phase `P01` - own-account register and ledger setup

Delivers the ledger-owned own bank account entity, its encrypted register with role designations, the registered ledger operations and the app ledger account CLI.

- [x] `P01.S01` - add the OwnBankAccount, designation and OwnAccountRegister domain types with ordinal ids, IBAN, BIC and bank-block validation and unit tests; `src/cadrumo/domain/transactions/own_accounts.py (new)`.
- [x] `P01.S02` - register the cadrumo.ledger.own_accounts FINANCIAL namespace and the revision-guarded OwnAccountRepository on the secure-model-document kernel, with encrypted round-trip and no-plaintext tests; `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py, src/cadrumo/adapters/persistence/profile/own_accounts.py (new)`.
- [ ] `P01.S03` - add registered ledger operations to add, list, show, update, close and designate own accounts with masked projections and refusal of deleting a referenced account; `src/cadrumo/application/ledger/, src/cadrumo/entrypoints/operation_composition.py`.
- [ ] `P01.S04` - add the app ledger account CLI fragment with IBAN and bank fields read through the secret input channel and locale keys in all four languages; `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py, new account command spec module, src/cadrumo/locales/*/cli.yml`.

### Phase `P02` - transaction account link and import repairs

Links transactions to own accounts at import and manual entry, removes cross-account false duplicates, and repairs the import defects found in the ledger health check.

- [x] `P02.S05` - add optional own_account_id to Transaction and fold it into derive_transaction_id and the import duplicate fingerprint only when present, with id-stability tests for unbound rows; `src/cadrumo/domain/transactions/models.py`.
- [ ] `P02.S06` - bind ledger import to an own account with an account option, OFX ACCTID match or mismatch refusal and unique IBAN auto-binding, through CLI and the TUI request model; `src/cadrumo/application/ledger/actions_import.py, import_operation.py, src/cadrumo/adapters/inbound/financial/providers/ofx.py, src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`.
- [ ] `P02.S07` - let manual add and update set the own account and let ledger list filter by it; `src/cadrumo/application/ledger/add_operation.py, src/cadrumo/entrypoints/cli/_ledger_list.py`.
- [x] `P02.S08` - repair import defects: size guard before detection reads, single read for hash and parse, honest provider tokens, period and year options that filter or are removed, basename-only log; `src/cadrumo/adapters/inbound/financial/, src/cadrumo/application/ledger/actions_import.py`.

### Phase `P03` - modelo account bindings and disposition rules

Resolves charge and refund accounts from the register at the export boundary for every consuming modelo and enforces the grounded domiciliacion and refund rules.

- [ ] `P03.S09` - resolve charge and refund accounts from the register through ModeloExportPorts with per-filing charge-account and refund-account overrides, delete the ModeloIVAProfile account fields, align the refund check to IBAN, and record role and own_account_id in receipts and events; `src/cadrumo/application/modelo/export.py, src/cadrumo/application/filing/producer_snapshot.py, src/cadrumo/domain/deadlines/models.py, profiles.py, src/cadrumo/entrypoints/adapter_composition.py`.
- [x] `P03.S10` - replace the 303-only domiciliacion branch with the declared disposition keys of each modelo and refuse a non-ES charge account with a typed capability refusal; `src/cadrumo/core/result_disposition.py, src/cadrumo/application/modelo/result_disposition_resolution.py`.
- [ ] `P03.S11` - refuse U after the window payment_cutoff_on in Europe/Madrid and add an advisory where no cutoff is declared, with a registered refusal code and locales; `src/cadrumo/application/modelo/export.py, src/cadrumo/core/errors/registry/, src/cadrumo/locales/*/errors.yml`.
- [ ] `P03.S12` - derive D versus X from the selected refund account country and prove 303 U, D, X and Nota 3 DID bytes against the design offsets; `src/cadrumo/application/modelo/result_disposition_resolution.py, src/cadrumo/application/modelo/tests/`.
- [ ] `P03.S13` - feed the Modelo 200 account fields by role from the resolved selection and delete the orphan wizard charge-iban option, the unread RefundAccount.sepa_marca field and stale profile-account prose; `src/cadrumo/application/filing/producer_snapshot_m200.py, export_producer.py, src/cadrumo/application/wizard/commands.py, src/cadrumo/application/modelo/action_errors.py`.

### Phase `P04` - modelo 360 reconciliation and write path

Gives Modelo 360 its grounded DEVOLUCION disposition, reconciles its account with the ledger register, and adds the operator write path.

- [x] `P04.S14` - replace the INGRESO fallback with a fixed DEVOLUCION spec for 360, a refusal for header-declaring modelos without a spec, and an absent disposition elsewhere, allowing absence in receipts and events; `src/cadrumo/core/result_disposition.py, src/cadrumo/application/modelo/result_disposition_resolution.py`.
- [ ] `P04.S15` - replace the embedded 360 refund account with an own-account reference or an embedded representante account and turn a missing account or BIC into a typed refusal; `src/cadrumo/application/filing/producer_snapshot_m360.py, producer_snapshot.py, src/cadrumo/application/modelo/export.py, src/cadrumo/adapters/persistence/profile/modelo_360_solicitud.py`.
- [ ] `P04.S16` - add a registered operation and CLI to declare, list and remove 360 solicitudes; `src/cadrumo/application/modelo/, src/cadrumo/entrypoints/cli/, src/cadrumo/locales/*/cli.yml`.
- [ ] `P04.S28` - ground and fix the remaining 360 pagina 2 defects against DR360 v2.1: whether the C indicator means a complementaria or a continuation page (DR353 reads it as continuation), why a one-operation solicitud refuses on the operation-2 fields, and accepting ISO operation dates rendered as DDMMAAAA, with byte tests through the real export builder; `src/cadrumo/application/filing/producer_snapshot_m360.py, dev/registry/pipeline/ (360 export tree), src/cadrumo/adapters/persistence/profile/tests/test_modelo_360_solicitud_export.py`.

### Phase `P05` - remaining 303 export fixes

Closes the 303 refusals that are account-adjacent but not solved by the register itself.

- [ ] `P05.S17` - default the prior-domiciliation election to KEEP for 303 exports and keep the explicit requirement only where a rectificativa states casilla 111; `src/cadrumo/application/modelo/export.py`.

### Phase `P06` - TUI ledger setup and elections

Puts own-account setup, import binding and per-filing account election in the Textual workbench.

- [ ] `P06.S18` - add the Ledger own-accounts setup screen with masked list, add and edit form, designation and close through injected doors; `src/cadrumo/entrypoints/tui/ledger/`.
- [ ] `P06.S19` - add account pickers prefilled from designations, the cutoff advisory and capability refusals to the Modelo export and review screens; `src/cadrumo/entrypoints/tui/modelo/workbench/`.
- [ ] `P06.S20` - add the own-account picker to the import flow and bind preview and apply to the file content digest; `src/cadrumo/entrypoints/tui/ledger/import_flow.py, src/cadrumo/entrypoints/tui/ledger/models.py`.
- [ ] `P06.S21` - add the 360 solicitud form with the solicitante or representante account choice; `src/cadrumo/entrypoints/tui/modelo/`.

### Phase `P06a` - CLI conformance to backend changes

Bring every CLI command, option, help text, JSON envelope, refusal rendering and generated reference that consumes the changed backend into agreement with it: own-account operations, transaction account binding, import options, per-filing account overrides, disposition and cutoff refusals, and the 360 DEVOLUCION route. Runs after the backend Steps it conforms to are closed.

- [ ] `P06a.S23` - audit and align every CLI family touched by P01 to P05 (ledger account, import, add, list, modelo calculate, verify and export, wizard, 360 solicitud) against the changed backend contracts: options, positional subjects, help text, JSON output schemas and refusal rendering, removing options whose backend was deleted; `src/cadrumo/entrypoints/cli/, src/cadrumo/locales/*/cli.yml`.
- [ ] `P06a.S24` - point operator remedies and the error catalogue for missing charge or refund accounts, non-ES charge accounts, past-cutoff domiciliacion and 360 account refusals at the live ledger account and 360 commands, and pass the operator-surface reconciliation; `src/cadrumo/application/operator_surface/, src/cadrumo/core/errors/registry/, src/cadrumo/entrypoints/cli/operator_surface_reconciliation.py`.
- [ ] `P06a.S25` - prove live CLI registration, refusal, output shape and promised idempotency for every conformed command, assert no IBAN appears in argv, text or JSON output, and regenerate the CLI reference from its owner; `src/cadrumo/entrypoints/cli/tests/, docs/`.

### Phase `P06b` - TUI conformance to backend changes

Bring every Textual screen, projection, modal and staged edit that consumes the changed backend into agreement with it: removed ModeloIVAProfile account fields, resolved charge and refund accounts, typed account, capability and cutoff refusals, the 360 DEVOLUCION disposition and transaction account binding, with masked account rendering throughout. Runs after the backend Steps and P06 screens it conforms to are closed.

- [ ] `P06b.S26` - audit and align every TUI screen and projection consuming the changed backend (Modelo workbench result and export, review, declarations, ledger list and detail, home and overview) with the resolved accounts, removed profile account fields, typed refusals, 360 DEVOLUCION and transaction account binding, rendering accounts masked; `src/cadrumo/entrypoints/tui/`.
- [ ] `P06b.S27` - prove each conformed screen with Textual pilot tests through the real runtime projections, covering success, each typed refusal and masked rendering, and check the rendered frames in the TUI preview; `src/cadrumo/entrypoints/tui/ (owning tests directories)`.

### Phase `P07` - integration proof and references

Proves the whole path on real encrypted storage and regenerates owned references.

- [ ] `P07.S22` - prove 303 U, D, X and Nota 3, 111 U and 360 solicitante and representante exports end to end on real encrypted storage with synthetic accounts, and regenerate the CLI reference; `src/cadrumo/application/modelo/tests/, docs/`.

## Parallelization

Five backend lanes can run at once, followed by two conformance lanes, with disjoint write ownership. Each lane commits by pathspec; shared files are re-read before patching and committed hunk-only.

- Lane A, custody and ledger setup: P01.S01, S02, S03, S04 in order. Owns `src/cadrumo/domain/transactions/own_accounts.py`, `src/cadrumo/adapters/persistence/profile/own_accounts.py`, the namespace entry in `secure_object_namespaces.py`, the new `application/ledger` own-account operation modules and the new ledger account CLI spec module. S01 unblocks Lane B; S02 unblocks Lane D's S09; S03 unblocks P06.S18.
- Lane B, transaction link and import repairs: P02.S08 starts at once; S05 starts after P01.S01; then S06 and S07. Owns `domain/transactions/models.py`, `raw_transaction.py`, `application/ledger/actions_import.py`, `import_operation.py`, `add_operation.py`, `adapters/inbound/financial/**`, the ledger import, add and list CLI specs, and `entrypoints/tui/ledger/models.py` only for the import request field.
- Lane C, disposition core: P03.S10 and P04.S14 start at once; P03.S12 starts after P03.S09 is committed. Owns `core/result_disposition.py`, `core/payment_election.py` and `application/modelo/result_disposition_resolution.py`. S12's call-site hunk in `application/modelo/export.py` is its only cross-lane write and lands after Lane D's in-flight Step commits.
- Lane D, export binding: P03.S09 after P01.S02, then P03.S11, P03.S13, P04.S15, P04.S28 and P05.S17. Owns `application/modelo/export.py`, `application/filing/producer_snapshot*.py`, `application/filing/export_producer.py`, `application/filing/record_field_renderer.py`, `domain/deadlines/models.py`, `domain/deadlines/profiles.py`, `application/wizard/commands.py` and `entrypoints/adapter_composition.py`.
- Lane E, 360 write path and TUI: P04.S16 after P04.S15; P06.S18 after P01.S03; P06.S19 after P03.S09 and S11; P06.S20 after P02.S06; P06.S21 after P04.S16. Owns `entrypoints/tui/**` (except the import request field above) and the new 360 solicitud operation and CLI modules.
- Lane F, CLI conformance: P06a.S23, S24, S25 in order, after P01 through P05 are closed. Owns `entrypoints/cli/**` other than the new spec modules Lanes A, B and E created (which it may then edit), `application/operator_surface/**` and the CLI reference under `docs/`. It can run alongside Lane G.
- Lane G, TUI conformance: P06b.S26 and S27 in order, after P01 through P06 are closed. Owns `entrypoints/tui/**` once Lane E has closed P06.

Shared files are serialized rather than owned: `entrypoints/operation_composition.py` and operation definitions (Lane A first, then Lane E), `core/errors/registry/*` (Lanes C and D), and `src/cadrumo/locales/*/{cli,errors,wizard}.yml` (all lanes, through the `dev.locales` workflow). P07.S22 runs last, after every other Step is closed.

## Verification

- Register: encrypted round trip through the real repository proves no IBAN, BIC or mask in object keys or stored plaintext; revision-guard conflict and designation-to-missing-account cases refuse.
- Transactions: unbound rows keep their existing `derive_transaction_id`; two own accounts with identical movements import as two transactions; OFX `ACCTID` mismatch refuses.
- Export: through the real export path, 303 U, D, X and Nota 3 render `DID00` bytes at positions 12, 23 and 194 matching the 2026 design; 111 U renders its IBAN; missing charge or refund accounts raise `REFUSED_MODELO_CHARGE_ACCOUNT_MISSING` / `REFUSED_MODELO_REFUND_ACCOUNT_MISSING`; a non-ES charge account and a U past `payment_cutoff_on` refuse with their typed codes; 360 records DEVOLUCION and refuses a missing account or BIC with a typed refusal, never `FAIL_MODELO_EXPORT`.
- Privacy: receipts, events, logs and JSON envelopes contain the role and `own_account_id` only; CLI entry never takes an IBAN in argv.
- Gates: focused tests per Step, then `just check-import-boundaries`, `just check-style`, `just check-format` and `just check-types` on touched scopes; locale key parity across es, en, ca and hu; the CLI reference regenerated from its owner.
- The plan is complete when every Step is closed and the integrated review at each Phase close and at plan close passes.
