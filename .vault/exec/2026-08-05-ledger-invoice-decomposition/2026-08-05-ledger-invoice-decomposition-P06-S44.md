---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:bb7f6b652ce0d6caf07deb8f80fa33e0e1a3cc6ee2e4c4d5a78044d428322ff2'
step_id: 'S44'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Key the counterparty tax-id requirement to the three cases article 6.1.d enumerates, and in those same cases require a structurally-valid NIF-IVA rather than any tax id, so an intra-community supply stops accepting a domestic number

## Scope

- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/domain/invoices/_validators.py`

## Description

- Widen `Invoice.counterparty_tax_id` from a required `str` to `str | None`, default `None`.
- Add `_SIMPLIFICADA_MANDATORY_TAX_ID_CATEGORIES` (`INTRA_COMMUNITY_SUPPLY`, `DOMESTIC_REVERSE_CHARGE`) naming the two RD 1619/2012 art. 6.1.d cases readable from an invoice's own `IvaCategory`; document case 3.º (issuer established in TAI) as a declared, unmodelled gap since the record carries no issuer-establishment field.
- Add a requiredness validator: `ORDINARIA`/`RECTIFICATIVA` keep the tax id mandatory unconditionally (unchanged); `SIMPLIFICADA` requires it only when the declared `iva_category` is in the mandatory set.
- Keep full NIF/IVA-number checksum validation active whenever the field IS present, regardless of class.
- Update `derive_invoice_id` and `_derive_invoice_id_when_complete` to accept `counterparty_tax_id: str | None`, hashing `counterparty_tax_id or ""`; default the key to `None` before the completeness check so omitting it entirely (not just passing `None`) still derives an `invoice_id`.
- Absorb two downstream ripples the optional field creates (see Notes on the S41 record): `application/invoices/_source_resolver.py`'s M347/M349 projection now skips an invoice with no tax id; `entrypoints/cli/_ledger_catalogue_invoice_payloads.py`'s `CatalogueInvoiceRecordPayload.counterparty_tax_id` widened to match, its validator skipping `None`.
- Follow-up commit, after the plan Step's own text was revised mid-implementation to also require a structurally-valid NIF-IVA in the mandatory cases: add `assert_non_domestic_country_code` to `_validators.py` and a model validator refusing `counterparty_country == "ES"` on an `INTRA_COMMUNITY_SUPPLY` invoice, closing a live defect where a domestic country + a valid Spanish CIF passed every existing check on that category.

## Outcome

Landed as commit `1751ce04cf` (combined with P06.S41-S43, S45; see the S41 record's Notes for why), plus a follow-up commit `539ae9c9ad` for the country-consistency fix below.

A factura simplificada (an ordinary retail ticket) can now be recorded without a counterparty tax id, unless the declared IVA category is an exempt intra-community supply or a domestic reverse-charge operation — the two art. 6.1.d cases this record's data can name. An ordinaria or rectificativa is unaffected: the tax id stays mandatory exactly as before this Step. Separately, an `INTRA_COMMUNITY_SUPPLY` invoice can no longer name Spain as its own destination, closing the "domestic number" defect the revised Step text named.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_invoice_simplificada.py -n 0 -q --no-header
8 passed in 2.43s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_invoice_intracommunity_destination.py -n 0 -q --no-header
5 passed in 0.70s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation src/cadrumo/application/invoices src/cadrumo/application/ledger src/cadrumo/entrypoints/cli src/cadrumo/domain/iva src/cadrumo/domain/transactions -n auto -q --no-header
2743 passed in 64.42s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation src/cadrumo/application/invoices src/cadrumo/application/ledger src/cadrumo/entrypoints/cli src/cadrumo/domain/iva src/cadrumo/domain/transactions src/cadrumo/application/modelo -n auto -q --no-header
4282 passed, 1 failed (unrelated, see Notes) in 160.30s
```

Two mutation-proofs, both restoring `_models.py` byte-exact afterwards (SHA-256 verified):

- Emptying `_SIMPLIFICADA_MANDATORY_TAX_ID_CATEGORIES` to `frozenset()` reddens exactly `test_a_simplificada_still_requires_the_tax_id_for_an_exempt_intracommunity_supply` and `test_a_simplificada_still_requires_the_tax_id_when_the_destinatario_self_assesses` (2 failed, 6 passed in the file), nothing else.
- Removing the `assert_non_domestic_country_code(self.counterparty_country)` call from `_validate_intracommunity_destination_country` reddens exactly `test_an_intracommunity_supply_naming_spain_is_refused` and `test_the_guard_fires_even_when_the_category_alone_would_not_require_a_tax_id` (2 failed, 177 passed across the whole `domain/invoices` suite), nothing else.

**Near-miss caught by the broad regression run.** The first version of the country guard used a full EU-membership check (`assert_eu_member_state_code`), which broke two existing, unrelated tests: `test_invoice_catalogue_source_resolver_accepts_xi_goods_for_m349` (Northern Ireland's `XI` is a legitimate M349 goods destination under the Windsor Framework despite not being one of the 27 Member States) and `test_invoice_catalogue_source_resolver_rejects_gb_ordinary_goods_for_m349` (a non-EU destination like `GB` is a declared fact the M349-specific resolver judges, not a construction-time refusal). Narrowed to refuse only `counterparty_country == "ES"` specifically, which is the literal defect the revised Step text names ("stops accepting a domestic number") and leaves both carve-outs intact.

## Notes

See the S41 record for the shared commit rationale and the peer-commit interaction on `application/aggregation`.

**Case 3.º of art. 6.1.d (domestic operation, issuer established in the territorio de aplicación del impuesto) is a declared gap, not a guessed default.** `Invoice` carries no field naming where its issuer is established, so this case cannot be read from the record. Case 3.º is close to universal for a Spanish-established taxpayer's domestic operations, so leaving it unenforced is a real, if narrow, under-enforcement risk for a domestic simplificada with no declared IVA category or a domestic-rated category outside the two modelled cases. Flagged for the team lead rather than resolved unilaterally: closing it would require either a new issuer-establishment axis on `Invoice` or keying the requirement on domestic-vs-foreign `counterparty_country`, and the second reading conflates the ISSUER's establishment (what the law actually asks) with the counterparty's residency (a different fact the invoice does carry). The shared task list's item #41 ("the tax-id requirement keys on country, not on the IVA category art. 6.1.d actually names") is addressed by the country-consistency fix above for the intra-community case specifically; the case 3.º gap itself remains open.

**Update, same day, operator-requested:** the case 3.º gap was closed in a follow-up commit `b721701389`, at the user's explicit request. The fact turned out not to need a new field at all: `TaxpayerProfile.fiscal_residency` (`FiscalResidency`, TRLIRNR art. 2) already carries it. `application/invoices/_issuer_establishment.py` derives `issuer_established_in_tai(profile)` from it (`RESIDENT_IRPF`/undeclared -> established, `NON_RESIDENT_IRNR` -> not, with the non-resident-with-permanent-establecimiento-permanente carve-out named rather than modelled, since this codebase has no such axis) and composes `simplificada_requires_tax_id_for_domestic_issuer(invoice, profile)`. Deliberately kept ADVISORY-weight and NOT wired into a construction-time or verify-time refusal -- an ordinary domestic ticket with no identified customer is common, legitimate practice, and this is the least certain of the three art. 6.1.d cases the codebase can evaluate. Wiring the actual `Notice` emission remains P06.S46's scope (wiring decomposition-adjacent advisories to a real consumer); this follow-up ships the predicate + tests only, ready for that wiring.

**One unrelated pre-existing test failure observed in the broad 4283-test run**, confirmed NOT caused by this Step: `test_preclassified_candidate_outside_period_blocks_binding_resolution` in `application/aggregation/tests/test_iva_ledger.py` fails in isolation too, and `application/aggregation/_iva_ledger.py` carries live uncommitted peer WIP (`git status` shows it modified, unrelated to any commit in this record) at the time of this run.

**Second update, same day, design settled -- stated plainly so a later reader does not go looking for a field that was correctly never added.** Case 3.º does NOT live on `Invoice` and is not going to: the condition is on the party "obligado a la expedición de la factura", which for an ISSUED invoice is this app's own taxpayer (a profile-level fact, `TaxpayerProfile.fiscal_residency`) and for a RECEIVED invoice is the counterparty/supplier (a genuinely per-invoice fact this app has no field for, and does not need one for -- see below). `simplificada_requires_tax_id_for_domestic_issuer` is therefore scoped to `invoice.kind is InvoiceKind.ISSUED` only; there is no parallel RECEIVED-side mechanism, because on a RECEIVED invoice `counterparty_tax_id` names the SUPPLIER's own identification (already governed unconditionally by art. 6.1.d's opening clause, independent of the three cases), not a "was our own NIF present" question the app has any field to answer.

**Third update, code review, HIGH-1 fixed (commit `8efa8b7f3c`).** Independent review of `1751ce04cf`/`539ae9c9ad` found the SIMPLIFICADA tax-id relief at `_models.py` never read `self.kind`: it applied on a RECEIVED invoice too, where `counterparty_tax_id` names the ISSUER (the supplier), not the destinatario art. 6.1.d's three cases govern. A RECEIVED SIMPLIFICADA with no supplier NIF constructed successfully before the fix -- all five original simplificada tests hard-coded `kind=ISSUED` and never caught it. The validator now requires `invoice_class is SIMPLIFICADA and kind is ISSUED` before relieving the tax id; a RECEIVED invoice keeps it unconditionally mandatory. Added the missing RECEIVED-side test pair (no supplier NIF refused; supplier NIF present accepted). Landed via the apply-cached gated drive: `_models.py` carried a concurrent agent's uncommitted WIP (an art. 4.4.a SIMPLIFICADA-intracommunity eligibility guard) at the time; staged only this fix's hunks against a HEAD-anchored copy, verified zero `4.4.a` markers in the staged diff, then re-applied the identical fix to the working tree so it was not left stale relative to the index.

**Fourth update, tracked-work gap.** `simplificada_requires_tax_id_for_domestic_issuer` has zero production consumers -- exported and tested, never called outside its own tests -- the fourth instance of this shape this campaign has found (`decompose_invoice`/`partition_invoices`, `route_invoice_retenciones`, `classify_invoice_line_for_iva`, now this). Checked every existing invoice consumer (`create_catalogue_invoice`/`build_catalogue_invoice`, the CLI queries/projection modules, the catalogue payloads) for `TaxpayerProfile` access: none load it, and `create_catalogue_invoice` does not even accept `invoice_class` or an optional tax id yet, so there is no cheap wiring point today. Reported to the team lead; the consumer must land as tracked plan work (proposed: widen P06.S46's scope, or a sibling Step naming S46 as prerequisite) before this predicate is treated as done, not as a note left to rot.
