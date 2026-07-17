---
tags:
  - '#research'
  - '#iva-franquicia-2026-scope'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-iva-franquicia-2026-scope-adr]]"
  - "[[2026-04-27-modelo-303-rule-delta-reference]]"
---

# `iva-franquicia-2026-scope` research: `IVA franquicia 2026 regime scope`

Verify-first scoping pass for issue #350 (P1, needs-design): the EU small-business
VAT exemption scheme (Directiva (UE) 2020/285) and its pending Spanish transposition
— a regimen de franquicia del IVA under which a small taxpayer below a turnover
threshold neither repercute (charges) nor deduce (deducts) IVA and does not file
Modelo 303/390. The pass answers: what exists at HEAD, what the authority actually
says, and how bounded the first slice is.

## Findings

### F1 — Nothing about the franquicia regime is modelled at HEAD

RAG + grep + read across `domain/iva/`, `domain/deadlines/`, the M303 registry, and
`--type vault` returned zero franquicia implementation. Confirmed absences:

- `IVARegime` (`src/aeat/domain/deadlines/_models.py:30`) enumerates
  `{GENERAL, SIMPLIFICADO, RECARGO_EQUIVALENCIA, REAGP, EXENTO}` — no `FRANQUICIA`
  member. `EXENTO` is a different concept (art. 20 activity exemption:
  education/health), not a turnover-based election, and must not be conflated.
- `IvaCategory` (`src/aeat/domain/iva/_schema.py:38`) has 18 members
  (`DOMESTIC_*`, `INTRA_COMMUNITY_*`, `EXPORT_*`, `IMPORT_*`, `RECARGO_EQUIVALENCIA`,
  `REGIMEN_SIMPLIFICADO`) — no franquicia member.
- `TaxpayerProfile` (`_models.py:390`) carries a required `iva_regime: IVARegime`
  but no turnover / volumen-de-operaciones axis. A grep for
  `turnover|volumen_operaciones|annual_turnover` finds no profile field — only
  unrelated registry-fixture text. There is no numeric axis on which a franquicia
  threshold could be evaluated today.
- `ModeloIVAProfile` (`_models.py:298`) carries enrolment booleans
  (`roi_enrolled`, `oss_enrolled`, `sii_enrolled`, `redeme_enrolled`,
  `refund_account`) — the natural home for a future `franquicia_enrolled` flag, but
  no such flag exists.

### F2 — The project already documented franquicia as an explicit out-of-scope watch-list item

`2026-04-27-modelo-303-rule-delta-reference` records the franquicia as a watch-list
item, citing the Directive (`DOUE-L-2020-80356`) and the AEAT 2026 control-plan note
(`BOE-A-2026-5843`), and lists `franquicia` under "out of scoped formula derivation".
This is prior intent: the M303 calc-verify campaign deliberately deferred it. #350 is
the campaign that revisits that deferral.

### F3 — The applicability engine already has the exact lever the first slice needs

`ModeloApplicabilityRule.applicable_iva_regimes`
(`src/aeat/domain/calculations/registry/_applicability.py:287,331`) gates a modelo
NOT_APPLICABLE for any profile whose `iva_regime` is outside the rule's set. Both
Modelo 303 (`:1463`) and Modelo 390 (`:1434`) are gated on
`_IVA_SELF_ASSESSMENT_REGIMES = {GENERAL, SIMPLIFICADO}` (`:620`). A new
`IVARegime.FRANQUICIA` member deliberately excluded from that frozenset makes M303
and M390 resolve to NOT_APPLICABLE automatically, with the rule's
`not_applicable_reason` surfaced to the operator — no formula-graph change, no new
casilla logic. This is the cleanest, lowest-risk model of "a franquiciado does not
file M303/390".

### F4 — SIMPLIFICADO is the working analogue for regime-specific calc gating

The regimen simplificado already carries a regime-specific bypass:
`_raise_if_ledger_preflight_blocks_calculation`
(`src/aeat/application/modelo/_calculation_actions.py`), pinned by
`test_simplificado_ledger_bypass.py` with an anti-tautology GENERAL-regime control.
The enrolment surface is the `--iva-regime` CLI axis + wizard SELECT validator
(`docs/how-to/profile-setup.md:202`), which already lists GENERAL / SIMPLIFICADO /
RECARGO_EQUIVALENCIA / REAGP / EXENTO. A `FRANQUICIA` member plugs into this exact
enrolment path. The profile builder (`domain/deadlines/_profiles.py:325`
`_resolve_iva_regime`) already hydrates the enum from the wizard token.
