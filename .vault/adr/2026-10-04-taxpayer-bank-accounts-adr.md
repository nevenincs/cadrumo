---
tags:
  - '#adr'
  - '#taxpayer-bank-accounts'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:97123d0563954cb8168989dea87e6bbf9d5235139e2eb5d6d4569af0b14ac424'
related:
  - "[[2026-10-04-taxpayer-bank-accounts-research]]"
  - "[[2026-10-04-taxpayer-bank-accounts-reference]]"
  - "[[2026-06-24-m303-refund-fichero-block-adr]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - "[[2026-06-24-m303-refund-election-adr]]"
  - "[[2026-10-04-modelo-360-solicitud-custody-adr]]"
  - "[[2026-06-10-ledger-amount-direction-adr]]"
  - '[[2026-07-01-determinism-replay-residual-adr]]'
  - '[[2026-08-16-m210-export-authority-adr]]'
---

# `taxpayer-bank-accounts` adr: `Ledger-owned own bank accounts bound to modelo charge and refund roles` | (**status:** `accepted`)

Accepted 2026-10-04 on the operator's explicit authorization given that day: "implement support for both … store and link our own iban as part of the ledger setup and bindings to it". Under the operator's standing instruction to proceed without approval gates, that authorization also covers the amendments to the three earlier ADRs named under Constraints, which this record applies.

## Problem Statement

No production path can supply the taxpayer's own bank account to a Modelo export. `RefundAccount` and `ChargeAccount` exist and every consumer reads them, but their only holder, `ModeloIVAProfile`, is never filled, the profile-schema home the earlier decision chose was retired, and the one store that can hold an account (the Modelo 360 register) has no writer (`2026-10-04-taxpayer-bank-accounts-reference`). Every 303 domiciliación, devolución and Nota 3 export therefore refuses, 111/115/130/131 domiciliación is refused by a 303-only branch, and 360 records an ungrounded INGRESO disposition. Separately, the ledger has no notion of which of the taxpayer's accounts a transaction belongs to, which lets the import duplicate screen drop real movements across accounts. The operator asked for own accounts to be set up in the ledger and bound to the modelo producers.

## Considerations

- One account shape serves every consuming design: IBAN, optional SWIFT-BIC, optional foreign-bank block; it is used in two roles, debit (domiciliación) and credit (devolución), and 303 puts both roles in one `DID00` slot (`2026-10-04-taxpayer-bank-accounts-research`).
- The holder of a domiciliación account must be the obligado, and 303/100 refunds go to an account "de la que soy titular"; only 360 admits a representative's account (campo 114) (`2026-10-04-taxpayer-bank-accounts-research`).
- Nominating an account to receive a refund does not authorise debiting it; charge and refund remain separate roles (`2026-06-21-m303-carry-reconciliation-adr`, `domain/deadlines/models.py:165-181`).
- Domiciliación closes before the plazo ends, and the registry already stores that cutoff as `payment_cutoff_on`; non-ES SEPA domiciliación is grounded for 111/130/131 since 2024-02-01 but not for the 303 fichero (`2026-10-04-taxpayer-bank-accounts-research`).
- NRC, transferencia and reconocimiento de deuda appear in no fichero design; 390 carries no account; 360 has no Tipo de declaración and is a refund application by design.
- An encrypted singleton register with revision-guarded mutation is the working storage analogue (`adapters/persistence/profile/foreign_assets.py`, the 360 register); new parallel mechanisms are unwanted.
- Private data must not reach logs, receipts, events, command arguments or JSON envelopes (rule 05).

## Considered options

- Profile-schema fields (the `2026-06-24-m303-refund-fichero-block-adr` route): rejected. The schema paths were deliberately retired, a profile axis cannot be referenced by transactions, and it gives one account where designs need per-role and per-filing choice.
- A filing-only account register under application/filing: rejected. It answers export but leaves the ledger without account identity and would duplicate the entity the ledger needs.
- Per-modelo account copies (the dead 200/210 fact sets, the 360 embedded account): rejected as the duplication that already exists.
- A ledger-owned own-account register holding accounts and role designations, referenced by transactions and resolved into the existing `RefundAccount`/`ChargeAccount` projections at export: chosen.

## Constraints

- Custody: own accounts persist only in the registered `FINANCIAL` namespace `cadrumo.ledger.own_accounts` (key `ledger_own_accounts`), `BUCKET_LOCAL`, `STRUCTURED_CUSTODY`, singleton object key `default`, revision-guarded, on the existing bare-document secure-object kernel. No IBAN, BIC or derived natural identifier appears in an object key, a command argument, a log line, a JSON envelope, a receipt or an event. Operator output shows a mask of country code plus last four characters; the full value appears only in the TUI edit form and the exported fichero.
- Identity: an own account has a register-assigned ordinal `own_account_id` (for example `acc-01`), never reused and never derived from the IBAN or any account material, so it is deterministic for golden replay (`2026-07-01-determinism-replay-residual-adr`) and safe in command arguments. Only accounts the taxpayer holds (titular or cotitular, attested on entry) are own accounts. Third-party accounts are not own accounts.
- Roles: charge and refund are distinct designations; a charge account is never inferred from a refund designation or the reverse, though the operator may designate one account for both explicitly.
- Filing-affecting rules (grounded in `2026-10-04-taxpayer-bank-accounts-research`): a charge account must be an ES IBAN until a per-revision grounding of Orden EHA/1658/2009 art. 5 bis is declared in the registry; a non-ES charge account refuses with a typed capability refusal. U refuses when the export date in Europe/Madrid is after the work unit's `payment_cutoff_on`; where the window declares no cutoff, the export carries an advisory finding and does not refuse. U admissibility follows the modelo's declared disposition keys, not a modelo-name branch. A refund to an ES IBAN resolves D; a refund to a non-ES account resolves X on modelos whose keys admit X (303, 100), with Marca SEPA derived as today. A non-SEPA account requires SWIFT-BIC and the full bank block. Accounts whose number is not an IBAN are out of scope and refuse explicitly.
- Disposition vocabulary is unchanged: `ResultDisposition`, `PaymentElection`, `RefundElection`, `PriorDomiciliationElection`. G/V stay capability-refused. NRC, transferencia and reconocimiento de deuda (with aplazamiento or compensación) are presentation-time choices for an I result; they are neither elections nor fichero values.
- Modelo 360 resolves the fixed disposition DEVOLUCION from a declared spec (design section 4, "Devolución solicitada"); it is never rendered because the layout has no slot, but it drives the account gate, receipts and events. The INGRESO fallback is removed: a modelo whose layout declares `filing.result_disposition` without a spec refuses; a modelo whose layout declares none and has no fixed spec records no disposition.
- Affected prior rulings, amended in place by this record's authority: `2026-06-24-m303-refund-fichero-block-adr` (profile-schema carrier and D/X-only DID emission), `2026-06-21-m303-carry-reconciliation-adr` (home of `ChargeAccount`), `2026-10-04-modelo-360-solicitud-custody-adr` (embedded account, open writer, INGRESO fallback). `2026-06-24-m303-refund-election-adr`, `2026-06-10-ledger-amount-direction-adr`, `2026-07-01-determinism-replay-residual-adr` and `2026-08-16-m210-export-authority-adr` stand unchanged.

## Implementation

We will make own bank accounts a ledger entity, store them and their role designations in one encrypted register, link transactions to them, and resolve every modelo's charge and refund account from that register at the export boundary.

- Entity: `OwnBankAccount` in the transactions domain with `own_account_id`, operator `label`, canonical `iban` (existing `core/iban.py` validation), optional `swift_bic`, optional foreign-bank block (name, address, city, country), `currency` (ISO 4217, default EUR), optional `opened_on`/`closed_on`. A closed account cannot be selected for an export dated after `closed_on`, and an account referenced by transactions is closed rather than deleted.
- Register: `OwnAccountRegister` holds the accounts and the designations together, so a designation cannot name a missing account. A designation is (role CHARGE or REFUND, scope ALL or one modelo) to one `own_account_id`, unique per role and scope.
- Resolution, per filing: an explicit per-filing account choice, else the modelo-scoped designation, else the ALL designation, else the existing `REFUSED_MODELO_CHARGE_ACCOUNT_MISSING` / `REFUSED_MODELO_REFUND_ACCOUNT_MISSING` refusals. The resolver reads the register through `ModeloExportPorts` (as the 360 register is read) and produces the existing `RefundAccount`/`ChargeAccount` projections inside the current selection code of `application/modelo/export.py`; `ModeloIVAProfile.refund_account`/`.charge_account` are deleted, since the IVA profile is the wrong home for 111/130/131. Which modelos consume an account follows the revision's layout (`selected_account.*` and the 200 and 360 account keys), not modelo names. The refund account is resolved at the same boundary as the refund election so D versus X can follow it. Receipts and events record the role and the opaque `own_account_id`, never account material.
- Duplicates retired in the same work: the dead Modelo 200 account fact-set fields are fed by role from the resolved selection rather than a second store; Modelo 210's party-scoped ingreso and devolución accounts, each with its own holder, stay governed by `2026-08-16-m210-export-authority-adr` and out of scope; the orphan wizard `--charge-iban` option and the unread `RefundAccount.sepa_marca` field are deleted; stale "configure on the profile" prose is corrected. Modelo 100's second-instalment charge account is a per-filing election added when the 100 export consumes accounts (hypothesis; 100 has no account producer today).
- Transactions: `Transaction` gains optional `own_account_id`. `ledger import` takes the account; when the file carries an account identifier (OFX `ACCTID` today) it must match the chosen account or the import refuses, and a unique IBAN match may bind without the option. An unbound row stays explicitly account-unassigned. When present, `own_account_id` folds into `derive_transaction_id` and the import duplicate fingerprint; when absent neither hash changes, so stored rows keep their ids. Manual add and update can set it, and list can filter by it.
- Modelo 360: `Modelo360SolicitudEntry.refund_account` is replaced in place by an account choice that is either a reference to an own account (holder "A" solicitante, BIC required at selection) or an embedded representative account with holder name (holder "R"). `m360.cuenta.titular_en_calidad_de` derives from the variant. The register has never had a production writer, so no migration is needed. A registered operation with CLI and TUI surfaces writes solicitudes.
- Operator surface: `app ledger account` commands to add, list, show, update, close and designate own accounts, with IBAN and bank fields entered through the bounded secret input channel (`entrypoints/cli/config/secure_input.py`) or an interactive prompt, never argv; `app ledger import` gains the account option; export, quickfile and file gain per-filing `--charge-account` and `--refund-account` overrides by `own_account_id`. The TUI Ledger gains an own-accounts setup screen, and the Modelo export/review screen gains account pickers prefilled from designations. Exact verb spellings follow the existing ledger register families (hypothesis within this commitment).

## Rationale

One ledger entity answers both needs the evidence exposes: the designs need one account shape in two roles with per-filing choice, and the ledger needs account identity for transactions and duplicate screening. Keeping the existing `RefundAccount`/`ChargeAccount` projections and the existing refusals as the export contract confines the change to supplying them, which follows the operator's fix-in-place rule and reuses the storage kernel the 360 and 720 registers already prove. Role designations with per-filing override fit 303's per-period choice and 100's split domiciliación without per-modelo copies. The conservative ES-only charge rule and the cutoff gate follow rule 14: where grounding is incomplete (303 art. 5 bis) the capability stays refused; where the registry already holds grounded data (`payment_cutoff_on`) it is enforced. Recording DEVOLUCION for 360 replaces a fabricated INGRESO with the only disposition the design expresses (`2026-10-04-taxpayer-bank-accounts-research`).

## Consequences

- Gain: 303 U, D, X and Nota 3 exports, 111/115/130/131 domiciliación and 360 solicitudes can be completed from persisted, encrypted data; the 360 missing-account case becomes a typed refusal instead of `FAIL_MODELO_EXPORT`.
- Gain: transactions carry account identity, which removes cross-account false duplicates and opens per-account reconciliation.
- Cost: a new namespace, register, operations and CLI/TUI surfaces; receipts and events gain an account-reference field and must allow an absent disposition.
- Cost: operators of non-ES domiciliación accounts on 303 are refused until art. 5 bis is grounded per revision; accounts without an IBAN are refused until a non-IBAN account shape is decided.
- Reconsider if: a released dataset exists before the transaction-id change lands (then a migration is required); the registry gains per-revision art. 5 bis grounding; a second 360 solicitud per period is needed; or operators need third-party accounts outside 360.
