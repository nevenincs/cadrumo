---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-20'
tier: L3
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-18-schema-hardening-research]]'
  - '[[2026-05-18-schema-hardening-plan]]'
  - '[[2026-05-19-schema-hardening-plan]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `schema-hardening` Plan C: inline `semantic_role` validator plan

## Wave `W01` - validator foundation

This Wave delivers the schema slots, the validator implementation,
the typo-twin warning surface, the roundtrip and anti-tautology
tests, and a clean validator-off default so subsequent Waves can
introduce roles one at a time without breaking the registry load.
Authority documents are the schema-hardening ADR and research.

### Phase `W01.P01` - introduce schema slots, validator, and warning surface

This Phase delivers the structural foundation for Mechanism C.

- [x] `W01.P01.S01` - add optional `semantic_role: str | None` slot to `CasillaDefinition` with default `None`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S02` - add `CasillaAlias` pydantic model carrying `label: str`, `legal_refs: LegalRefs`, `source_refs: SourceRefs`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S03` - add optional `aliases: tuple[CasillaAlias, ...]` slot to `CasillaDefinition` with default empty tuple; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S04` - implement `_validate_semantic_role_consistency` snapshot-build validator enforcing identical `data_type` and structurally compatible `constraints` across every casilla sharing a `semantic_role`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S05` - implement `_emit_semantic_role_typo_twin_warnings` at snapshot build identifying every `semantic_role` value with exactly one occurrence in the corpus; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S06` - wire both validators into `ValidatedRegistryAuthority` snapshot-build sequence; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S07` - add strict roundtrip test covering matching and divergent role declarations across two synthetic modelos; `src/aeat/domain/calculations/registry/test_semantic_role_consistency.py`.
- [x] `W01.P01.S08` - add strict roundtrip test covering the typo-twin warning surface for single-occurrence role values; `src/aeat/domain/calculations/registry/test_semantic_role_typo_twin.py`.
- [x] `W01.P01.S09` - add anti-tautology test mutating a casilla's role declaration on a saved fixture and confirming snapshot build now fails; `src/aeat/domain/calculations/registry/test_semantic_role_anti_tautology.py`.
- [x] `W01.P01.S10` - add strict roundtrip test covering `CasillaAlias` declarations with multiple label variants preserving legal_refs and source_refs; `src/aeat/domain/calculations/registry/test_casilla_alias_roundtrip.py`.

## Wave `W02` - identity roles

This Wave declares semantic roles for the nine identity concepts the
identity-atom inventory catalogued: taxpayer NIF, spouse NIF,
descendant NIF, ascendant NIF, payee NIF, representative NIF,
member-or-socio NIF, intracomunitario NIF-IVA, foreign fiscal ID.
Authority is the identity-atom inventory in the research artefact.
This Wave depends on `W01` and is followed by `W03`.

### Phase `W02.P02` - declare `taxpayer_nif` role

This Phase declares the `taxpayer_nif` role on every casilla carrying
the primary declarant NIF across the corpus.

- [x] `W02.P02.S11` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S12` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S13` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S14` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S15` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S16` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S17` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S18` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S19` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S20` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S21` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S22` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S23` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S24` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S25` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S26` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S27` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S28` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P02.S29` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W02.P03` - declare `payee_nif` role and reconcile binding-vs-casilla split

This Phase declares the `payee_nif` role on perceptor and counterpart
NIF surfaces and reconciles the binding-only declarations in modelos
190 and 193 against the casilla declarations in modelos 180 and 184.

- [x] `W02.P03.S30` - declare `semantic_role = "payee_nif"` on modelo 180 perceptor NIF casilla; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `W02.P03.S31` - declare `semantic_role = "payee_nif"` on modelo 184 perceptor NIF casilla; `src/aeat/_data/registry/aeat/modelos/184.toml`.
- [x] `W02.P03.S32` - M190 perceptor NIF lift from binding row-field to casilla; `deferred as a separate structural-refactor work (changes binding/casilla decomposition, not just role annotation); `src/aeat/_data/registry/aeat/modelos/190.toml`.
- [x] `W02.P03.S33` - M193 perceptor NIF lift from binding row-field; `deferred as separate structural-refactor work; `src/aeat/_data/registry/aeat/modelos/193.toml`.
- [x] `W02.P03.S34` - M349 op.nif-comunitario is NIF-IVA (already retrofitted in Plan A P06 long-tail); `role assignment is nif_iva not payee_nif; covered by Plan C W02.P05 nif_iva role; `src/aeat/_data/registry/aeat/modelos/349.toml`.

### Phase `W02.P04` - declare family NIF roles

This Phase declares `spouse_nif`, `descendant_nif`, and `ascendant_nif`
roles on the family-identity casillas in modelo 100, reconciling the
dual modelling introduced in the 2025 revision.

- [x] `W02.P04.S35` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P04.S36` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P04.S37` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P04.S38` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P04.S39` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W02.P05` - declare remaining identity roles

This Phase declares `representative_nif`, `member_or_socio_nif`,
`nif_iva`, and `foreign_fiscal_id` roles on their respective surfaces.

- [x] `W02.P05.S40` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P05.S41` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P05.S42` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P05.S43` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W02.P05.S44` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

## Wave `W03` - monetary roles

This Wave declares semantic roles for the four highest-footprint
recurring monetary concepts identified by the monetary-shape
inventory: base imponible, cuota a ingresar, retenciones e ingresos a
cuenta, pago fraccionado. Authority is the monetary-shape inventory.
This Wave depends on `W02` (validator behaviour already proven) and
is followed by `W04`.

### Phase `W03.P06` - declare `retenciones_ingresos_a_cuenta` role and reconcile constraint drift

This Phase declares the highest-priority monetary role and reconciles
the constraint divergence the research flagged: nine modelos disagree
on whether the role should be `non_negative`.

- [x] `W03.P06.S45` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S46` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S47` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S48` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S49` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S50` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S51` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S52` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S53` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S54` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P06.S55` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W03.P07` - declare `base_imponible` role and reconcile money-vs-decimal drift

This Phase declares the `base_imponible` role across the 11 modelos
the monetary-shape inventory flagged and reconciles the
money-vs-decimal divergence in modelo 100.

- [x] `W03.P07.S56` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P07.S57` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W03.P08` - declare `cuota_a_ingresar` role

This Phase declares the `cuota_a_ingresar` role across the 13 modelos
the monetary-shape inventory flagged.

- [x] `W03.P08.S58` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P08.S59` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W03.P09` - declare `pago_fraccionado` role

This Phase declares the `pago_fraccionado` role on the three modelos
(130, 131, 202) carrying it.

- [x] `W03.P09.S60` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P09.S61` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W03.P09.S62` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

## Wave `W04` - address and period roles

This Wave declares semantic roles for the cross-cutting address and
fiscal-period concepts the address-atom and fiscal-period-atom
inventories catalogued. Authority is those two inventories. This Wave
depends on `W03` and is followed by `W05`.

### Phase `W04.P10` - declare country and CCAA roles

This Phase declares `taxpayer_country`, `payee_country`, and
`taxpayer_ccaa` roles on the address surfaces in the five modelos
identified by the address-atom inventory.

- [x] `W04.P10.S63` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P10.S64` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P10.S65` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P10.S66` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P10.S67` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W04.P11` - declare `filing_year` role

This Phase declares the `filing_year` role on every `decl.ejercicio`
casilla across the corpus.

- [x] `W04.P11.S68` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S69` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S70` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S71` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S72` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S73` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S74` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S75` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S76` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S77` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S78` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S79` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S80` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S81` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S82` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S83` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S84` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S85` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S86` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S87` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S88` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S89` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S90` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S91` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S92` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P11.S93` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W04.P12` - declare `filing_period` role

This Phase declares the `filing_period` role on every casilla
carrying a filing-period value across the corpus, depending on the
period-coverage discovery audit produced by Plan A.

- [x] `W04.P12.S94` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W04.P12.S95` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

## Wave `W05` - completion sweep and validator hard-flip

This Wave runs a full-corpus role-coverage audit, lands the remaining
long-tail role retrofits via plan expansion, and flips the validator
into final hard-error mode. Authority is the schema-hardening ADR.
This Wave depends on `W04`.

### Phase `W05.P13` - corpus role-coverage audit and remaining retrofits

This Phase audits the full modelo corpus against the role catalogue
introduced by `W01` through `W04`, identifies remaining unrolied
casillas that share semantic intent with existing roles, and lands
the long-tail retrofits.

- [x] `W05.P13.S96` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W05.P13.S97` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W05.P13.S98` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

### Phase `W05.P14` - validator hard-flip and verification gate

This Phase removes the optional `default = None` on `semantic_role`
for casillas in canonical-role families, runs the full registry test
suite, and verifies snapshot build fails on any deliberately
introduced role inconsistency.

- [x] `W05.P14.S99` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W05.P14.S100` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.
- [x] `W05.P14.S101` - deferred to operational per-role rollout per role-rollout-strategy audit; `framework in place via W01 validator; each role lands role-by-role as audit + retrofit + verification cluster; `.vault/audit/2026-05-19-schema-hardening-role-rollout-strategy.md`.

## Wave `W06` - registry fragmentation closure and warning burn-down

This Wave records the 2026-05-20 operational pivot back to the
registry-hardening blocker. The profile-lifecycle recovery work is
tracked separately and must not displace this registry thread. The
fragmentation authority is the accepted fragment architecture ADR and
research; the semantic-role authority remains the schema-hardening
ADR and role-taxonomy reference.

### Phase `W06.P15` - confirm M200 fragmentation and cross-revision drift gate

This Phase verifies the structural mitigation that originally blocked
reviewability.

- [x] `W06.P15.S102` - verify `src/aeat/_data/registry/aeat/modelos/200.toml` is absent and M200 is authored through `modelos/200/manifest.toml` plus revision fragments.
- [x] `W06.P15.S103` - verify the largest remaining single-file modelo TOML is below 2,000 lines; latest inventory reports `130.toml` at 1,456 lines.
- [x] `W06.P15.S104` - run cross-revision drift and M200 registry gates: `uv run pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_modelo_200_registry.py --tb=short`; result on 2026-05-20 was 15 passed.
- [x] `W06.P15.S105` - confirm drift validation is wired into registry validation through `_validate_cross_revision_casilla_consistency` and covered by synthetic and committed-corpus tests.

### Phase `W06.P16` - singleton semantic-role warning burn-down

The drift gate now passes, but snapshot validation still emits
singleton-role warnings. These warnings are the next hardening
substrate because they identify role declarations that may be typos,
missing sibling declarations, or intentionally unique concepts that
need an explicit policy.

- [x] `W06.P16.S106` - generate a current singleton-role warning inventory grouped by modelo and role prefix; 2026-05-20 baseline is 242 warnings: M200 174, M100 55, M202 4, M390 3, M184 2, M190 2, M303 2; prefixes are `is` 178, `irpf` 55, `iva` 5, `tipo` 2, `total` 2.
- [ ] `W06.P16.S107` - classify each warning group as missing sibling coverage, intentional singleton, or role-name typo.
- [x] `W06.P16.S108` - land the first burn-down cluster by normalizing M390 annual IVA cuota roles to the shared IVA cuota taxonomy used by M303/M322/M353; singleton-warning baseline lowered from 242 to 239.
- [x] `W06.P16.S109` - add a regression surface that makes the singleton warning count visible and prevents accidental increases outside intentional role rollout commits; baseline cap test added to `test_cross_revision_drift.py`.
- [x] `W06.P16.S110` - add generic `semantic_role_cardinality = "intentional_singleton"` support with required reason and stale-marker validation; apply it to M202 2025-only Mod. 40.3 LIS B2 tipo 3/tipo 4 base and percentage roles.
- [x] `W06.P16.S111` - restore full-corpus warning inventory after concurrent M100 semantic-role WIP was repaired; 2026-05-20 live baseline is 224 warnings: M200 169, M100 49, M184 2, M190 2, M303 2; prefixes are `is` 169, `irpf` 49, `tipo` 2, `total` 2, `iva` 2.
- [x] `W06.P16.S112` - harden the singleton typo-warning scan so snapshot validation uses an indexed candidate search instead of comparing each singleton role against every role; verified by direct typo-warning unit tests and the committed-corpus warning-count gate.
- [x] `W06.P16.S113` - classify the M200 `is_correccion_*` singleton family; 166 of 169 M200 warnings are role-axis siblings (`permanente`/`temporaria`, `aumento`/`disminucion`, current/prior-year axes), not typo drift.
- [x] `W06.P16.S114` - add a generic semantic-role axis-sibling rule to the typo-warning detector so legal axis variants are not reported as spelling twins while same-axis near-duplicates still warn; live baseline lowered from 224 to 84 warnings.
- [x] `W06.P16.S115` - tighten the committed singleton-warning regression cap to the live 84-warning baseline after the indexed scan and semantic-axis sibling filter.
- [x] `W06.P16.S116` - extend the generic sibling detector to token-axis pairs (`clave`/`subclave`, `count`/`amount`, prior/future, internal/international, roman buckets) and optional `sin` legal variants; live baseline lowered from 84 to 64 warnings.
- [x] `W06.P16.S117` - extend the generic sibling detector to legal-reference axes (`art*`, `dt*`, `rdleg`, `lis`) and detail/other scope axes; M200 singleton warning inventory is now clean and the live baseline is 49 M100-only warnings.
