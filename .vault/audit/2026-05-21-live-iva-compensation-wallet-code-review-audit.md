---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` Code Review

LIVIVA-CR-001 | MEDIUM | Blocked-decision export and verification guards are not repository-injectable
`src/aeat/application/modelo/_actions.py:1907` checks blocked IVA wallet decisions during verification, and `src/aeat/application/modelo/_export.py:383` checks them before export. Both call the default `IvaWalletDecisionRepository` through `_persisted_blocked_iva_compensation_decision_for_work_unit`, while `calculate_modelo_revision` already accepts an injected decision repository for secure SQL-backed workflows. A caller that injects work-unit/calculation/event repositories backed by a non-default `SecureObjectRepository` cannot inject the matching IVA wallet decision repository into verify/export, so those paths may miss a blocked decision stored in the same non-default backend. Production default settings remain covered, but the service contract is inconsistent and weakens testability for the new safety gate.

Recommended fix: add `iva_compensation_decision_repository` injection to `verify_modelo_revision` and `export_modelo_revision`, thread it through the CLI only as the default, and add a real secure SQL-backed regression test that stores a blocked decision in the injected repository and proves verify/export refuse it.

LIVIVA-CR-002 | HIGH | Persona review found Modelo 303 readiness/calculation can diverge from ledger preflight
The W04 persona dry-run recorded `WALLET-048`: `ledger preflight --period 2026Q1` reported `ready false` for an incomplete business ledger row, while `modelo readiness --modelo 303 --revision-id 2009-y-siguientes --year 2026 --period 1T` reported `ready True` and calculation emitted a zero-valued draft. This is not introduced by the W03.P04 code, but it is directly in the broader IVA calculation-hardening scope and should be treated as the next safety implementation item before marking the wallet/operator wave complete.

Recommended fix: make Modelo readiness and ledger-backed calculation consult the ledger preflight/readiness result for ledger-owned Modelo 303 bindings, and refuse or clearly block calculation when relevant ledger evidence is incomplete.

LIVIVA-CR-003 | INFO | W04.F05 repository-injection follow-up review passed
Reviewed the W04.F05 delta for blocked IVA wallet decision authority, mutation ordering, and test quality. `verify_modelo_revision`, `file_modelo_revision`, and `export_modelo_revision` all consult the injected `IvaWalletDecisionRepository` before granting verification, mutating filing state, or writing export artifacts. The new tests use real encrypted SQL-backed repositories, store the blocked decision outside the default application database, assert the default lookup is empty, and then prove verify/file/export refuse through the injected repository. No critical, high, or medium issues remain for W04.F05.

LIVIVA-CR-004 | INFO | W04.F03 live wallet CLI safety-surfacing review passed
Reviewed the W04.F03 delta for operator-facing no-submit claims. The CLI help now states the fail-closed policy at the `iva-wallet` group, `pull`, and `capture-history` surfaces. Successful text output now includes explicit safety metrics before wallet values, and the tests exercise help rendering plus output-line construction without enabling live AEAT access. The change does not weaken the underlying adapter guard: wallet execute POSTs and non-own-name representation gates remain blocked in `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`. No critical, high, or medium issues remain for W04.F03.

LIVIVA-CR-005 | INFO | W04.F04 carry-forward and authority-surface review passed
Reviewed the W04.F04 delta for calculation ownership, privacy, and CLI usefulness. The CLI does not calculate carry-forward amounts itself; `list_iva_compensation_history` calls the existing `build_iva_compensation_carry_forward_report` engine and only renders the returned lots. Persisted authority decisions are read from the encrypted decision repository and redacted with `taxpayer_ref`; tests assert the raw NIF is not present in the application report JSON. The CLI now exposes source period, age, expiry review state, remaining amount, selected authority, divergence, blocked/stale flags, and authority-source details. No critical, high, or medium issues remain for W04.F04.

LIVIVA-CR-006 | INFO | W04.F02 ledger diagnostic-surface review passed
Reviewed the W04.F02 delta for calculation ownership and operator usefulness. The status command reuses the existing ledger preflight service for readiness issues and only renders stored transaction facts alongside each issue; it does not duplicate IVA aggregation logic. The added CLI regression creates a real transaction through `aeat app ledger add` and proves `ledger status --period` exposes classification, category, taxable base, IVA rate, IVA amount, reason, and detail for blocked rows. No critical, high, or medium issues remain for W04.F02.

LIVIVA-CR-007 | INFO | W04.F06 external-constants centralisation review passed
Reviewed the W04.F06 delta for security, live-mutation risk, and test quality. The change does not add any AEAT navigation or submission path. It only moves read-only guard/parser route identifiers behind `external_constants.toml`: CSV verifier host pinning, declarations final-URL shape, cotejo CSV matching, and IRPF detail-year matching. The new AST guard checks executable string constants in the live auth/Sede/wallet/CSV modules while allowing docstrings, so it is a structural centralisation guard rather than a mirrored business-logic test. No critical, high, or medium issues remain for W04.F06.

LIVIVA-CR-008 | INFO | W04.F07 older Modelo 303 submitted-file extraction review passed
Reviewed the W04.F07 delta for extraction correctness, privacy, and test quality. The parser change is local-only and does not contact AEAT. It narrows the fallback by filing year so 2022 Modelo 303 page-03 records read casilla `71` from the official 2022 position, while 2023+ records retain the existing position. The regression grounds the 2022 position in the bundled official AEAT workbook and uses a redacted synthetic record, avoiding private captured values and avoiding a pure mirror of the production mapping. No critical, high, or medium issues remain for W04.F07.

LIVIVA-CR-009 | INFO | W04.F08 empty-wallet fail-closed review passed
Reviewed the W04.F08 delta for live-mutation safety, false-zero evidence risk, and test quality. The change does not introduce a new AEAT operation; it narrows acceptance after the already-guarded wallet read query. A no-table page that still exposes AEAT's executable `ejecutar` control now fails closed instead of becoming `total_pending=0`, and the post-query navigation path raises `external_shape_changed` for the same ambiguous shape. The new regression is structural: it varies the wallet HTML shape and asserts parser refusal/acceptance without hard-coding any private wallet amount or duplicating tax arithmetic. No critical, high, or medium issues remain for W04.F08.

LIVIVA-CR-010 | INFO | W04.F09 plan safety-wording review passed
Reviewed the W04.F09 vault-plan wording change for safety drift. The update does not loosen the live AEAT mutation boundary: it keeps filing, payment, confirmation, represented-taxpayer data, and operator-choice form submissions prohibited, while documenting the already-implemented guarded `CarteraCuotas` read-query POST as the single named exception. This removes stale absolute no-form wording that conflicted with the current CLI and guard policy. No critical, high, or medium issues remain for W04.F09.
