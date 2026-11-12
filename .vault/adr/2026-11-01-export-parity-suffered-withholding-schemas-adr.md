---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:df08b259fed24c9d99957656e88183263ff58cdb546d0552d1310ede3bbfcf67'
related:
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-reference]]"
  - '[[2026-11-01-export-parity-withholding-legal-readings-research]]'
---
# `export-parity` adr: `suffered-withholding, credit reconciliation and resolution-record schemas` | (**status:** `accepted`)

Accepted 2026-11-01 on the operator's rulings and the primary-source grounding recorded below.

## Operator rulings 2026-11-01

- The repercutido ingreso a cuenta reading is a regulated question, to be grounded in the norms and implemented as the norms say. `2026-11-01-export-parity-withholding-legal-readings-research`, Q5, grounds it, and section 3 records the result.
- The remaining recommendations of this record were accepted.
- On the absence-attestation question the operator answered "I do not know" and delegated the decision. It was decided on the merits by the orchestrator as fail-closed applicability (section 5) and is reversible by a later ruling.
- The payer-year timing constraint on the datos fiscales cross-check (section 8) follows from DGT V4965-16 as read in the research.

This record's own opening paragraph describes the amendment as proposed. With this acceptance, the wording under "Proposed wording for the accepted record" is authorized to be applied to `2026-09-27-export-parity-renta-withholding-sources-adr` by its owning Step.

This record proposes an amendment to the accepted `2026-09-27-export-parity-renta-withholding-sources-adr`. That record fixes the intent of its Steps 2, 4 and 5. This record settles the persisted schemas, which the operator authorized on 2026-11-01 with the design to be approved before any code. The accepted record stays unchanged until this proposal is authorized. The wording to apply then is under "Proposed wording for the accepted record". The scope is plan Phases P03 and P04 (Steps S17, S18, S29, S06, S19 and S20) of `2026-11-01-export-parity-plan`. Evidence is in `2026-11-01-export-parity-suffered-withholding-schemas-reference`.

## Problem Statement

The accepted record chooses a typed per-payer suffered-withholding family, a blocking cross-source reconciliation and an operator resolution record. It does not fix their shapes. Each shape is costly to reverse. The namespace key grammar, the payload schema and the persisted finding reasons have to stay readable for every stored record and calculation revision. The source-kind member and its provider are public registry contracts. Grounding against the official dictionaries also showed that the class-to-casilla mapping cannot be read off the registry as it stands: the role of 0598 in the editions before the newest dictionary names the wrong dictionary field. The accepted Step 5 instruction, to move `aeat_prefilled` onto the new bindings, would also make the informative borrador the winning source for a credit. That is the outcome the accepted record rejected as Option C.

## Considerations

- Official meaning of 0591 to 0609, verified against the bundled dictionaries of every edition (reference, "Credit casillas"). 0595 is the cuota resultante, correctly modelled and outside 0609. The 0598 number labels both the inmuebles summary (CRETING) and the credit (RET3). Its role in the earlier editions names the summary, and only the newest edition names the credit. 0598 is computed from 0153. 0592 to 0594, 0600 and 0601 sum per-entity detail casillas. 0602 is the LIRPF art. 92.8 image-rights ingreso a cuenta.
- LIRPF art. 99.1 treats retención and ingreso a cuenta alike as pagos a cuenta. Art. 99.6 presumes the ingreso a cuenta made, and lets repercusión decide only its inclusion in the base imponible. RIRPF art. 108.3 makes the payer certificate the evidence (reference, "Law").
- The payer-side stores and source kinds (`WITHHOLDING`, `RETENCIONES_AGGREGATION`) must never feed a credit casilla (`2026-09-21-retenciones-workflow-observation-payment-contract-adr`).
- Every new kind is one `BindingSourceKind` member with one registration row, validator and resolver (`2026-06-26-binding-source-kind-taxonomy-unification-adr`; reference, "Source kind").
- The persisted-issue Literal, the gate sets and the gate itself read only the revision (reference, "Durable findings"). The concurrent taxonomy amendment with topic `tier-divergence` defers its finding envelope to this record and its resolution to plan Step S20.
- Advisory capability grade blocks verify and export, under the concurrent `binding-capability-grade` draft. Filing kind on captured observations is decided under the concurrent `observation-filing-kind` draft. The year to which activity income and withholding are imputed is decided under the concurrent `income-imputation-criterion` draft. This record depends on those decisions and does not make them.

## Considered options

- Reuse the payer-side `WITHHOLDING` kind and its store with a "suffered" flag. Rejected. It merges the two sides in one store and one resolver, which the payment-contract ADR forbids. A misset flag would credit withholding the taxpayer practised on others.
- One generic `manual_input` binding per credit casilla with an attachment fingerprint. Rejected. It keeps no per-payer identity and no income class, so it cannot be reconciled per payer or cross-checked by class against datos fiscales.
- Map classes to casillas by casilla number in code. Rejected. Numbers belong to the registry revision, and the delta-keyed standard requires mapping by semantic role.
- Persist the reconciliation outcome outside the calculation revision. Rejected. Verify and export would then have to recompute against live stores, and could disagree with what was calculated.
- Keep the resolution record inside the calculation revision only. Rejected. A resolution made after calculation would force a recalculation, and a revoked resolution could not be honoured.
- Chosen: a distinct suffered-withholding kind and encrypted per-payer store, mapped to casillas by a domain class-to-role table that the registry is validated against. The reconciliation is persisted in the revision as typed findings. A separate encrypted resolution store is read by the gate.

## Constraints

- Obligations. Names, persisted tokens and key grammars below are binding once accepted. Module and function placements marked "hypothesis" may change within the boundary rules.
- No Modelo 100 registry edit lands before the Modelo 100 rectification of the earlier plan Step S13 is installed. Bindings and cross-check declarations are placed at the post-rectification storage baseline, and later editions inherit them.
- Payer-side stores never feed this family. The family's resolver reads only its own namespace. Its provider carries no `source_modelo`. The Step 1 payer-side reachability gate stays green.
- Private amounts and payer identifiers are persisted only inside encrypted payloads. A payer identity that leaves the payload, in an object key, a `source_ref`, a finding or a resolution key, is a keyed HMAC digest under a profile-held key, never a plaintext NIF and never an unkeyed hash, because the NIF space is enumerable (`src/cadrumo/core/keyed_digest.py:1-8`). Logs carry neither amounts nor reason text.
- No casilla number, number range or modelo number appears in a validator, resolver or gate of this family. Credit targets, admitted classes and admitted cross-check sources derive from semantic roles and typed registry classifications.
- The borrador never wins outright on a credit casilla. The borrador participation marker of section 6 lands with or before any move of `aeat_prefilled` onto a family binding, in the same Step (P03.S06) or an earlier one, so no published generation has a credit value source in the borrador precedence tier.
- Every numeric test uses an independent hand-derived oracle and runs through the real repository, resolver, calculation and gate (`2026-06-01-calculation-test-oracle-discipline-adr`).

## Implementation

We will add the suffered-withholding evidence family, a registry-declared credit reconciliation with typed blocking findings, and an operator resolution record, with the schemas below.

### 1. Source kind and provider

- `BindingSourceKind.RETENCION_SOPORTADA = "retencion_soportada"` is added to `src/cadrumo/core/aggregation.py`. It is distinct from `WITHHOLDING` and `RETENCIONES_AGGREGATION`, is not a ledger kind, and is not a member of the counterpart subset.
- The provider model `RetencionSoportadaProvider` is `{ kind = "retencion_soportada", income_class, quantity }`, defined in its own module, `src/cadrumo/domain/calculations/registry/retencion_soportada_bindings.py` (placement is a hypothesis). The module also holds its validator and the class-to-role table.
  - `quantity` is one of `pago_a_cuenta` (retención plus ingreso a cuenta, the credit), `retencion`, `ingreso_a_cuenta`, `ingreso_a_cuenta_repercutido` or `importe_integro`, and, under `2026-11-11-export-parity-work-income-sourcing-adr`, `importe_integro_dinerario`, `valoracion_especie`, `reducciones_aplicables` or `gastos_deducibles`.
  - Credit casillas bind `pago_a_cuenta` only. The other quantities exist for income casillas and cross-checks.
- Registration is one `_filing_grade` row in `binding_provider_registration.py`. It permits the DECIMAL channel and the SUM operation. Terminal origins are `PAYER_CERTIFICATE` and `OPERATOR_INPUT`; plan Step P02.S15 adds `PAYER_CERTIFICATE`. Output is `scalar`, resolver id `retencion_soportada`, stage `mesh`.
- The credit set of a revision is derived, never listed: it is the operand casillas of the formula targeting the casilla whose semantic role is `irpf_total_pagos_cuenta` (0609 today, `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:4214-4218`), the same derivation the payer-side gate uses (`dev/registry/tests/test_modelo_100_credit_casillas_exclude_payer_side_sources.py:56-60`).
- The validator refuses each of the following:
  - a class whose admitted semantic roles do not include the target casilla's role;
  - a binding on a `computed` casilla;
  - `pago_a_cuenta` on a casilla outside the derived credit set, or on a role no class admits as a credit role;
  - any other quantity on a target whose role no class admits as an income or cross-check role; the income roles are the (class, quantity) table of `2026-11-11-export-parity-work-income-sourcing-adr`, section 3.
- The resolver `RetencionSoportadaSourceResolver` lives in `src/cadrumo/application/aggregation/retencion_soportada_source.py` (placement is a hypothesis). It is enrolled once in the `mesh` stage of `src/cadrumo/application/modelo/calculation_route.py:113-136` and once in `CalculationWithholdingRows` (`src/cadrumo/application/aggregation/service.py:356-377`), so that the report names it when it is absent.

### 2. Closed income-class vocabulary and class-to-role table

`RetencionSoportadaClase` is a core `StrEnum`. The bundled 2024 Renta manual lists the income classes (2024 manual page 1490). RIRPF art. 75 lists the income subject to withholding. Each token admits these semantic roles; the 0598 role is the corrected one in section 7:

| Token | Admitted semantic role | Casilla |
| --- | --- | --- |
| `trabajo` | `irpf_retencion_trabajo` | 0596 |
| `capital_mobiliario` | `irpf_retencion_capital_mobiliario` | 0597 |
| `arrendamiento_inmueble_urbano` (not an activity) | `irpf_retencion_arrendamientos_inmuebles_urbanos` | 0598 |
| `arrendamiento_inmueble_urbano_actividad` (constituting an activity) | `irpf_retencion_arrendamientos_inmuebles_urbanos` | 0598 |
| `actividad_economica` (excluding urban rentals) | `irpf_retencion_actividades_economicas` | 0599 |
| `ganancia_patrimonial` (including premios) | `irpf_retencion_ganancias_patrimoniales_premios` | 0603 |
| `atribucion_capital_mobiliario` | `irpf_retencion_atribuida_capital_mobiliario` | 0592 |
| `atribucion_capital_inmobiliario` | `irpf_retencion_atribuida_capital_inmobiliario` | 0593 |
| `atribucion_actividad_economica` | `irpf_retencion_atribuida_actividades_economicas` | 0594 |
| `atribucion_ganancia_patrimonial` | `irpf_retencion_atribuida_ganancias_patrimoniales` | 0600 |
| `imputacion_aie_ute` | `irpf_retencion_imputada_aie_ute` | 0601 |
| `imputacion_derechos_imagen` (LIRPF art. 92.8) | `irpf_ingreso_cuenta_art_92_8` | 0602 |

The two urban-rental tokens follow the manual, which places urban rentals "constituya o no actividad económica" in their own class and excludes them from the activity class (`src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md:58477-58479`, page 1490). They are separate tokens because 0598 is computed from two different sources (section 7).

0604 (pagos fraccionados), 0605 (IRNR cuotas) and 0606 (Directiva 2003/48) are not per-payer income classes and are excluded. An unknown token is refused at the model boundary.

A record is never dropped silently, under two rules that section 5 shares:

- In a revision that declares any member of the family (a binding or a cross-check), the resolver reads every record of the ejercicio. A record whose class has no consumer in that revision raises `unrouted_observation`, which blocks.
- A revision that declares no member of the family reads nothing (section 5, "Absent"). Records for an ejercicio whose pinned Modelo 100 revision declares no member are refused at the write port, so no record is stored that no revision would ever read or report.

### 3. Per-payer record schema (payload v1)

`RetencionSoportadaRecord` carries the following fields:

- `ejercicio`, a `FilingYear`. It is the year the income is imputed to, under the `income-imputation-criterion` decision.
- `payer_tax_id`, a `TaxIdIdentityToken`, and an optional `payer_legal_name`.
- `payer_ref`, the keyed digest of the canonical payer token defined in section 4. The write port computes it, so the application resolver can use it as `source_ref` without holding the key.
- `income_class`.
- `importe_integro_dinerario`, `valoracion_especie`, `retencion`, `ingreso_a_cuenta` and `ingreso_a_cuenta_repercutido`. These are non-negative money values with at most two decimals. A third decimal is refused, not rounded. `ingreso_a_cuenta_repercutido` may not exceed `ingreso_a_cuenta`.
- `reducciones_aplicables` and `gastos_deducibles` (payload v2): required for class `trabajo` and absent for every other class, as fixed in `2026-11-11-export-parity-work-income-sourcing-adr`.
- `origin`, one of `payer_certificate` and `operator_declaration`.
- `evidence_fingerprint`, the sha256 of the certificate bytes held in attachment custody. It is required for `payer_certificate` and optional for `operator_declaration`.
- `replaces_evidence_fingerprint`, optional.
- `captured_at`.

Derived quantities: `pago_a_cuenta = retencion + ingreso_a_cuenta`. The credit is the full ingreso a cuenta whether or not it is repercutido (explicit text, read together; `2026-11-01-export-parity-withholding-legal-readings-research`, Q5). LIRPF art. 99.6 presumes the ingreso a cuenta made and has the contribuyente include in the base imponible the valuation of the retribución en especie and the ingreso a cuenta "salvo que le hubiera sido repercutido"; art. 43.2 repeats it for the valuation; art. 79.e deducts "los ingresos a cuenta" from the cuota líquida with no repercusión condition, and art. 99.1 counts them as pagos a cuenta. Repercusión therefore removes the ingreso a cuenta from the income only. DGT V1974-21 (binding) confirms the base side with a worked example (valuation 10, ingreso a cuenta 2, rendimiento íntegro en especie 12 when not repercutido) and DGT V1122-11 confirms that the payer's 190 and certificate carry separate "ingresos a cuenta efectuados" and "repercutidos" fields. Consequences for the schema:

- `pago_a_cuenta = retencion + ingreso_a_cuenta`, in full.
- Modelo 100 casilla 0007 (Importe íntegro) = 0004 (Valoración) + 0005 (Ingresos a cuenta) - 0006 (Ing. a cuenta repercutidos). Casilla 0596 carries the full 0005.
- Activity income in kind has no separate casilla: its valuation plus any unrepercutido ingreso a cuenta enters ingresos íntegros, and the ingreso a cuenta is credited through 0599.
- Valuation of the ingreso a cuenta: work income at the rate times the art. 43.1 valuation (RIRPF art. 102), capital mobiliario at the rate times acquisition cost or payer cost plus 20 per cent (art. 103), activity income at the rate times market value (art. 104). The valuation never includes the ingreso a cuenta.
- A repercutido amount above the ingreso a cuenta is refused (already enforced above).

The write port refuses three kinds of record:

- one whose payer NIF equals the active profile's NIF, because self-withholding is a payer-side fact;
- one whose `ejercicio` lies outside the supported filing years, or whose pinned Modelo 100 revision declares no member of the family (section 2);
- one whose identity differs from the stored row it replaces.

### 4. Namespace

`RETENCION_SOPORTADA_RECORDS_NAMESPACE` is declared in `secure_object_namespaces.py` and enrolled in `namespace_registry.py`:

- key `retencion_soportada_records` and namespace `cadrumo.renta.retencion_soportada.records`;
- owner `cadrumo.application.aggregation`;
- sensitivity `FINANCIAL`, `schema_version` 2 (a v1 payload parses with the v2 fields absent);
- scope `PROFILE_LOCAL` and custody `STRUCTURED_CUSTODY`, with the default ciphertext mirror policy;
- key grammar `{ejercicio}:{income_class}:{payer_ref}` for a payer record, and `absence:{ejercicio}:{income_class}` for an absence attestation.

A payer record holds one row per payer, class and ejercicio. A corrected or replacement certificate overwrites that row under `expected_revision_id`, and the payload records the fingerprint it replaces.

`payer_ref` is an HMAC-SHA256 keyed digest (`src/cadrumo/core/keyed_digest.py:66-78`) of the canonical tax-identity token. Its key is the active bucket session's HKDF sub-key (`get_active_hmac_subkey`, `src/cadrumo/adapters/persistence/storage/master_key/active_session.py:168-190`) under a context label dedicated to this family, which is the same keyed-lookup derivation the storage layer uses for its own lookup digests (`src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py:73-86`, `:240`). The natural key is then digested again into the `object_key` column, as for every namespace. The unkeyed sha256 helper of the payer-side store (`percepciones_observations_repository.py:29-37`) is not reused, because an unkeyed NIF digest is recoverable by enumeration and the natural key can surface in identity-mismatch errors. The exact label and the adapter that computes `payer_ref` are hypotheses.

The row-identity AAD (`encrypted_columns.py:51`) binds namespace, key digest and schema version. No custom AAD is added. `extract_identifier` re-derives the key from the payload, `payer_ref` included, so a substituted row is refused on load.

### 5. Absent, zero and missing

- **Absent.** The revision declares no `retencion_soportada` binding or cross-check. The resolver returns `None` and reads nothing. No stored record can fall here unreported, because the write port refuses records for such an ejercicio (section 2).
- **Applicability (fail-closed; decided 2026-11-01 on the merits, delegated by the operator, reversible).** Whether a class needs payer records or an attestation comes from the profile's declared income categories for the ejercicio:
  - a class that is declared, or whose declaration is unknown, requires either payer records or an explicit typed absence attestation before its credit casillas resolve;
  - a class positively declared absent resolves to proven zero without an attestation;
  - the attestation is an operator assertion with its own provenance (`OPERATOR_INPUT`, mandatory note). It is never filing evidence of a payer's statement and never counted as a payer certificate.
- **Missing.** The family is read, the class is applicable under the rule above, and no record and no attestation exist for (ejercicio, class). The bound casilla resolves to nothing, and the existing `unresolved_binding` issue blocks it. A missing value never becomes zero.
- **Proven zero.** Either records exist whose quantity sums to zero (a certificate stating no retención), or an `absence` attestation exists for (ejercicio, class) with a mandatory operator note, created by the operation of plan Step P03.S29. That gives a filing-grade 0.00 with an `OPERATOR_INPUT` terminal origin. Hypothesis: an attestation contradicted by a ledger income row of the same class is reported as a finding, following `WithholdingDetailAbsence`. An absence attestation proves a zero credit only; it never zeroes an income binding (`2026-11-11-export-parity-work-income-sourcing-adr`, section 5).
- **Degraded.** A storage failure is `storage_degradation_resolution` and is never empty.

### 6. Folding the manual 0596 binding and the borrador key contract

- At the storage baseline, `renta-certificado-trabajo-retenciones` is deleted and replaced by `renta-retencion-soportada-trabajo` (class `trabajo`, quantity `pago_a_cuenta`) on 0596. Later editions inherit it. Bindings with the same pattern are added on 0597 (`capital_mobiliario`) and 0603 (`ganancia_patrimonial`).
- 0598 stays computed, so it takes no binding of its own; a binding there would collide with the computed-casilla refusal. Its formula gains a family binding operand for the activity-rental component (section 7).
- The borrador import and tier share plan Step P02.S15's projected key contract: bound casilla, then its binding id. A snapshot keyed by the deleted id, or by free `casilla.<id>` keys, is refused without migration, under the operator's no-backward-compatibility ruling. The borrador snapshot's content id stops hashing the capture instant (P02.S15).
- `aeat_prefilled` today means two things: the binding may appear in a borrador snapshot (`src/cadrumo/application/modelo/borrador_binding.py:185-195`), and the binding joins the borrador precedence tier (`:440-441`). This record separates them.
  - `aeat_prefilled` keeps only the first meaning: snapshot admission.
  - A new closed binding field, `borrador_participation`, carries the second. Its members are `precedence` (the borrador tier may supply the value, the current behaviour and the default) and `cross_check_only` (the borrador value is projected for comparison and never enters the ladder). It is meaningful only where `aeat_prefilled` is true, and the build refuses it elsewhere.
  - The build refuses a binding that is the declared `value_source` of a credit reconciliation entry (section 7) unless it is `cross_check_only`. The marker is declared, and the declaration is checked against it, so the tier never has to infer participation from another family.
  - The borrador tier admits only `precedence` bindings. For `cross_check_only` bindings the borrador enters only as the `borrador` cross-check of section 7. A missing certificate is therefore never filled by the informative prefill. The operator records an `operator_declaration`, and the borrador then corroborates it or blocks it.
- Ordering. P03.S06 lands the marker, the tier change and the build rule with or before any move of `aeat_prefilled` onto a family binding. No intermediate change, publication or runtime adoption may carry `aeat_prefilled` on a credit value source without `cross_check_only`. A teeth test refuses a fixture that does.
- This amends accepted Step 5.

### 7. Registry declaration of value and cross-check sources

- Each Modelo 100 revision gains a scoped family `credit_reconciliation` at the storage baseline. It holds one entry per credit casilla, with `casilla_id`, `value_source` and a list of `cross_checks`.
  - `value_source` is a binding id, or a formula id for 0598.
  - Each cross-check is a typed member: `retencion_soportada { income_class }`, `borrador { binding }`, `ledger { binding }`, `filed_observation { modelo, casilla, period }` for 0599 against the filed fourth-quarter Modelo 130 casilla 06 (filing kind per `observation-filing-kind`), or `datos_fiscales { income_class }`. A cross-check may name the formula operand it compares against instead of the whole casilla.
  - The `filed_observation` entry for 0599 is enrolled with plan Step P05.S30 under the imputation criterion, and the `datos_fiscales` member with P06.S09; each is declared only then.
- Proposed entries:
  - 0596, 0597 and 0603 take their family binding as value source, with the borrador as cross-check;
  - 0598 takes the `renta-retenciones-arrendamientos-urbanos` formula, rewritten as below;
  - 0599 takes the ledger binding of plan Step P02.S05, cross-checked against `actividad_economica` records and the borrador, and from P05.S30 against the filed Modelo 130 casilla 06;
  - 0592 to 0594, 0600, 0601 and 0602 keep their current source, cross-checked against the matching attribution or imputation class.
- 0598 and activity rentals. The manual puts urban-rental withholding in 0598 whether or not the rental is an activity, and excludes it from 0599 (`source.pdf.extracted.md:58477-58479`). Today 0598 copies 0153 only (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/formulas/0001-declarations.toml:383-390`), and 0153 is the per-inmueble withholding of the capital inmobiliario section (`2020/casillas/0001-declarations.toml:1154-1158`), so activity-rental withholding has no home. The design:
  - The formula becomes the 0153 total plus the binding `renta-retencion-soportada-arrendamiento-actividad` (class `arrendamiento_inmueble_urbano_actividad`, quantity `pago_a_cuenta`). That binding is `cross_check_only` for the borrador. The exact formula operation is a hypothesis.
  - Cross-checks: `arrendamiento_inmueble_urbano` records against the 0153 operand only; the borrador against the 0598 total; and, where the ledger identifies them, ledger activity-rental withholding against the activity component. A certificate for an activity rental therefore never disagrees with 0153, so activity-rental withholding is not falsely blocked.
  - The 0599 ledger selector excludes rows whose `tipo_actividad` is `A01_ARRENDADORES_BIENES_INMUEBLES` (`src/cadrumo/core/tipos_actividad.py:73`). Their withholding is reported as a non-blocking finding that points to the 0598 activity component, so it is neither absorbed into 0599 nor lost.
  - Gap, stated rather than closed. `A01` means "arrendadores de bienes inmuebles" and does not separate urban from rústico, so a rústico-rental activity row is also excluded from 0599 and reported, and whether it belongs in 0599 is not decided here. `tipo_actividad` is optional on a transaction (`src/cadrumo/domain/transactions/models.py:606`), so an untagged row cannot be identified. Where the profile or ledger shows any `A01` activity for the ejercicio, an untagged withholding-bearing activity row leaves 0599 unresolved with a finding naming the missing tag. Where none is shown, untagged rows are treated as non-rental; that is a hypothesis to confirm against the profile's activity facts in P02.S05.
- The validator refuses each of the following, all derived from the registry:
  - an unenrolled member;
  - a casilla outside the derived credit set (section 1);
  - a class whose roles exclude the casilla;
  - a value source that is not the casilla's binding or formula;
  - a declared value source that is not `cross_check_only` for the borrador (section 6);
  - a `filed_observation` or `ledger` member whose source is not classified as suffered-side.
- Suffered-side classification. The payer-side ADR forbids withholding-agent returns as credit sources, but a semantic role alone cannot express that: Modelo 130 casilla 06 and the payer-side returns' withholding casillas share the role `retenciones_ingresos_a_cuenta` (for example `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-declarations.toml:70-73` and the same role in the Modelo 111, 115, 123, 180, 190 and 193 casilla files). The registry therefore gains a closed casilla classification, `withholding_side`, with members `suffered` and `practised`. A `filed_observation` source must be declared `suffered`; an undeclared or `practised` source is refused, so the rule fails closed without a list of modelos. A `ledger` or provider source is refused when its registration's terminal origin is `PERCEPTOR_OBSERVATION` (`src/cadrumo/domain/calculations/registry/binding_terminal_origin.py:69`), the payer-side origin of `WITHHOLDING` and `RETENCIONES_AGGREGATION`. The existing payer-side gate keeps its own fixture list; moving it onto this classification is not part of this record.
- The 0598 role and section are corrected at the storage baseline to the newest edition's values (`irpf_retencion_arrendamientos_inmuebles_urbanos`, the credit block). The newest edition's override then becomes redundant. This is part of the earlier plan's Step S13 rectification or of P03.S06, whichever lands first.

### 8. Reconciliation finding

- The reconciliation runs after the mesh and overlay on every calculation of a revision that declares the family. It compares the value-source amount with each present cross-check total by exact `Decimal` equality on two-decimal money, without rounding or tolerance. Per-payer totals are compared where both sides carry payer identity: certificates against datos fiscales, and ledger counterparty against certificate payer. That comparison only informs; the casilla total is what blocks.

  Timing constraint on the payer-side comparison (DGT V4965-16, binding; `2026-11-01-export-parity-withholding-legal-readings-research`, Q1 and contradictions note). Payers report withholding in the year of payment, so their certificate and the datos fiscales carry the payment year, while a devengo taxpayer credits withholding in the imputation year. For a devengo taxpayer the 0599 comparison against a certificate or `datos_fiscales { income_class }` therefore compares by the payer's payment year, using the itemised payment dates of the ledger rows. A difference fully explained by itemised accrual-versus-payment timing is not a divergence and raises no `credit_source_disagreement`. A residual difference after that itemisation still blocks, and a cobros y pagos taxpayer compares directly, since imputation and payment coincide.
- One shared typed fact, `SourceDisagreementFact`, is added to `CalculationSourceIssue` as an optional `disagreement` field. Older revisions parse with `None`. It is the one type for both this reconciliation and the `tier-divergence` screen; the persisted reason (`credit_source_disagreement` or `precedence_tier_divergence`) is the only discriminator. One type gives one resolution record, one finding-key derivation and one renderer. It holds:
  - modelo, filing year, period and work unit id;
  - registry revision id and `inputs_digest`, the content digest of the registry declarations the comparison read (the `credit_reconciliation` entry here, the binding declaration for a tier divergence). It does not hold the authority generation, which changes on every publication (`src/cadrumo/domain/calculations/registry/authority.py:90-122`);
  - key (`casilla_id` here, binding, relation or casilla key for a tier divergence), value channel, and `reached_casillas`, the exported casillas the key reaches;
  - `sources`, an ordered tuple of entries, each giving its role (`value_source`, `cross_check` or a tier name), source family token, resolver id, keyed-digest `source_ref` (section 4), typed `value`, and evidence fingerprint or snapshot id;
  - `selected_role`;
  - `finding_key`, the sha256 of the canonical form of the preceding fields, excluding work unit id, evidence fingerprints and snapshot ids.
- `value` is a closed discriminated union, never narrowed to an amount: `Decimal` (money, decimal, integer), enum token, date, boolean, text, relation value, and, for a row channel, the ordered tuple of row values. Equality per member is the tier-divergence record's item 2. Credit reconciliation produces only `Decimal` values; the other members exist for the tier screen.
- Row channels. A tier divergence on a row binding carries the whole row set of each tier as one `value`, and names the differing row indices. Row-source-identity claims and row casilla values stay exclusive and never produce this fact (tier-divergence record, item 2).
- New persisted reasons are added, in lockstep, to the `CalculationSourceIssue.reason` Literal, `_DurableSourceIssueReason`, the note catalogue and `dev.locales`:
  - `credit_source_disagreement` joins `GATE_REFUSED_REASONS`, and so `gate_refuses`. It blocks check, export and local filing, and the form shows the same verdict.
  - `credit_cross_check_absent` has attention CHECK and does not block. It is emitted once per absent cross-check source and reads "not cross-checked", never agreement.
  - `credit_resolution_stale` has attention CHECK. It is emitted when a resolution exists for the casilla but its `finding_key` no longer matches.
- Unscreened revisions get no reason of their own. The reconciliation enrols in the shared calculation screen stamp of `2026-11-01-export-parity-binding-capability-grade-adr`, adding the `credit_reconciliation` declarations to its digest and raising its contract version. A revision persisted before the screen, or whose declarations have since changed, refuses at verify, export and local filing with the one shared reason `calculation_screen_outdated` and a recalculate remedy. Revisions already `PRESENTADO` are not re-adjudicated. No modelo name appears in the stamp or its reason.
- Calculation and preview persist the BORRADOR revision with the value-source amount and show every finding. Verify, the CLI handoff and the calculation report render them from the persisted revision through the shared catalogue.

### 9. Operator resolution record

- `MODELO_CREDIT_RESOLUTION_NAMESPACE` is defined as follows:
  - key `modelo_credit_resolutions` and namespace `cadrumo.modelo.credit_resolution.records`;
  - owner `cadrumo.application.modelo`;
  - sensitivity `FINANCIAL`, because it restates amounts, and `schema_version` 1;
  - scope `PROFILE_LOCAL` and custody `STRUCTURED_CUSTODY`;
  - key grammar `credit-resolution:{modelo}:{filing_year}:{period}:{finding_key}`.
- The payload `CreditResolutionRecord` holds:
  - the full `SourceDisagreementFact` it answers;
  - `accepted_role`, which is always the persisted `selected_role`, because a resolution accepts the calculated value and never selects another;
  - `reason`, required, non-blank and bounded;
  - `resolved_at` and `resolved_by_session`;
  - `state`, `active` or `revoked`.
- The gate gains a resolution reader, and it enters at the one predicate. `gate_refuses` (`src/cadrumo/application/modelo/calculation_note_gate.py:40-49`) takes the issue and a resolution view instead of a bare reason, and refuses a `credit_source_disagreement` or `precedence_tier_divergence` issue unless an active record with the same `finding_key` exists. `blocking_calculation_issues` (`:51-63`) and the form's `withholds_filing` (`src/cadrumo/application/modelo/work_form_notes.py:18`, `:123-124`) both call it, so the form never shows as fileable what verify refuses, or the reverse.
- The record is keyed to the registry revision id and the content digest of the keyed inputs, not to the calculation revision and not to the authority generation. A recalculation with unchanged amounts keeps it, and so does a publication that leaves the revision's `credit_reconciliation` entry and every keyed value unchanged. Any changed amount, an added or removed source, a different registry revision or a changed declaration changes `finding_key`, so the record stops applying and `credit_resolution_stale` is reported.
- A registered operation creates the record (naming is a hypothesis, settled in the plan). Its input is the 16-hex finding id shown in verify, which is the prefix of `finding_key`, and the reason. The id is matched against the work unit's current persisted findings, following the `FindingResolution` blocker-id pattern (`src/cadrumo/application/ledger/confirmation_gate.py:193-230`). Revocation is a revision-guarded state change.
- Verify, the CLI handoff and the calculation report list every applied resolution with its casilla, sources, amounts and reason.

### 10. Replay of stored revisions

New reasons, kinds and the optional `disagreement` field are additive, so every stored revision parses. No reason, kind or binding id is renamed. A revision persisted under an authority generation that still declares `renta-certificado-trabajo-retenciones` replays under that pinned generation. Recalculating under the new generation re-sources it from the family. Tests pin the Literal and the application mirror as one set.

### Tests (S17 to S20)

- Encrypted round trip, including the AAD row-substitution refusal.
- Refusal of an unknown class, of a third decimal, of repercutido above ingreso a cuenta, and of a self-NIF payer.
- Absent, missing and proven zero.
- Multi-payer sum to the right casilla.
- The mixed persona, with payer-side rows leaving every credit unchanged.
- Agreement producing no finding.
- A devengo taxpayer whose 0599 differs from the datos fiscales total only by itemised accrual-versus-payment timing raising no finding, and a residual difference still blocking.
- Applicability: a declared or unknown class without records or attestation blocking, a class declared absent resolving to proven zero, and an attestation never rendered as payer evidence.
- Credit equal to retención plus the full ingreso a cuenta for a repercutido item, with income equal to casilla 0004 + 0005 - 0006.
- Each disagreement blocking with the full fact.
- An absent source reported as not cross-checked.
- A resolution clearing exactly its key and going stale after any amount changes.
- A resolution surviving an authority publication that changes no keyed declaration or value.
- The form's `withholds_filing` agreeing with the gate for an open, a resolved and a stale finding.
- Legacy-revision refusal through `calculation_screen_outdated`.
- 0598: an activity-rental certificate raising 0598 without disagreeing with 0153; an `A01` ledger row excluded from 0599 and reported; an untagged row in a profile with an `A01` activity leaving 0599 unresolved.
- Validator refusals on isolated fixtures: a credit target outside the derived credit set, a `practised` or undeclared `filed_observation` source, and a credit value source without `cross_check_only`.
- `payer_ref` stable for one profile, different across profiles, and never equal to the unkeyed sha256 of the NIF.
- A teeth fixture whose comparison is weakened to a tolerance, whose borrador exclusion is removed, or which carries `aeat_prefilled` on a credit value source without the participation marker, failing the gate.

### Dependencies needing an operator ruling

- The `credit_source_disagreement` reason and the `gate_refuses` signature change are shared with every modelo through the gate, the form and the tier-divergence screen. Plan Step P01.S28 coordinates the affected sessions before P04.S19 and P04.S20 land, with its scope ruled by the operator (P01.S27). No product scope is added.
- The two former open questions are decided (repercutido in section 3, absence applicability in section 5), so neither gates P03.S17 or P03.S29 any longer.

## Rationale

- A separate kind and namespace is the only shape the payment-contract ADR admits. The per-payer key gives the per-payer cross-check that datos fiscales need in P06, at no further schema cost.
- Mapping by semantic role, validated against a closed domain table, makes a wrong registry role a build failure rather than a silent misroute. The 0598 finding shows the misroute is real.
- Crediting the full ingreso a cuenta follows the text of LIRPF arts. 79.e and 99.6, as grounded in the legal-readings research.
- Fail-closed applicability never lets a missing payer record read as zero, and a profile that positively declares a class absent spares the operator an attestation.
- Persisting the finding in the revision makes verify and export judge what was calculated. Keeping resolutions in their own encrypted store, matched by a content key, lets a resolution follow unchanged amounts across recalculations and expire on any change. That is the accepted record's "stops applying" commitment.
- Excluding credit value sources from the borrador tier keeps the accepted rejection of prefill-as-primary true. The tier-divergence screen alone would still let the borrador fill a missing certificate. A separate declared marker, rather than an exclusion inferred from another family, keeps snapshot admission and tier participation as two typed facts that the build can check against each other.
- Keying resolutions to the inputs' content rather than the authority generation is what makes "unchanged amounts keep the resolution" true across publications.
- Evidence: `2026-11-01-export-parity-suffered-withholding-schemas-reference`.

## Consequences

- Gains:
  - each credit figure rests on per-payer evidence, with its class and origin audited;
  - one disagreement envelope serves this reconciliation and the tier-divergence screen;
  - the 0598 role defect is corrected at the baseline.
- Costs:
  - a new kind, two namespaces, one blocking reason and two advisories, a borrador participation field and a `withholding_side` classification, locale text, and a `gate_refuses` signature change shared by the gate and the form;
  - operators who keyed 0596 manually must re-enter it as a record;
  - under the fail-closed applicability rule, a taxpayer whose profile declares a class, or has not declared it, must supply records or an attestation for it, or calculation leaves the casilla unresolved and blocks verify and export; a class positively declared absent costs nothing.
- Reconsider in three cases: if a later ruling prefers profile-only applicability without attestations (the fail-closed rule is reversible); if entity-row designs land for 0592 to 0594, 0600 and 0601 (they would then take the family as value source); if a DGT or TEAC ruling contradicts the reading of art. 99.6 on repercutido ingresos a cuenta.

## Proposed wording for the accepted record

- In Implementation Step 2, replace "Each encrypted per-payer record carries payer NIF, income class, gross amount, withholding, ingreso a cuenta and repercutido, period, evidence fingerprint and origin (payer certificate or operator declaration)." with: "Each encrypted per-payer record carries the fields, namespace and key grammar fixed in `2026-11-01-export-parity-suffered-withholding-schemas-adr`. The credit is retención plus ingreso a cuenta. Repercusión governs only inclusion in the base imponible (LIRPF art. 99.6)."
- In Step 2, after "The class maps to casillas by `semantic_role`.", add: "Casilla 0598 is computed from 0153 plus activity-rental certificate records; non-activity urban-rental records cross-check the 0153 part only, and activity rentals are excluded from 0599. Attribution and imputation classes cross-check their casillas until entity-row designs exist."
- In Step 4, after "...for 0599 the filed fourth-quarter Modelo 130 casilla 06.", add: "The declaration, finding envelope, persisted reasons and resolution record are those of `2026-11-01-export-parity-suffered-withholding-schemas-adr`. A resolution is keyed to the registry revision id and a content digest of every keyed declaration and source value, not to the authority generation, and accepts only the calculated value."
- In Step 5, replace "Move `aeat_prefilled` to the suffered-withholding bindings." with: "Admit the suffered-withholding bindings to the borrador snapshot with `aeat_prefilled`, and mark every declared credit value source `borrador_participation = cross_check_only`, landed with or before that move. For those casillas the borrador is a cross-check only and never enters the precedence tier."

## Open questions for the operator

None. The repercutido reading is grounded in the norms (section 3), and absence applicability is decided as fail-closed (section 5) and reversible by a later ruling. The research notes that the datos fiscales timing observation was to be verified when P06.S09 declares the cross-check; section 8 now states the constraint it must satisfy.

## Amendment 2026-11-03

Basis: the operator's rulings of 2026-11-03 on the P03 phase-close review findings of `2026-11-01-export-parity-plan`. The accepted text above is kept as written; where this section differs from it, this section governs sections 1, 3, 4 and 5.

### Terminal origins (sections 1 and 5)

Section 1 says "Terminal origins are `PAYER_CERTIFICATE` and `OPERATOR_INPUT`". It is read as three origins: `PAYER_CERTIFICATE`, `OPERATOR_INPUT` and `PROFILE_FIELD`. The provider registration admits all three.

`PROFILE_FIELD` applies only to a proven zero derived from a declared profile fact, with no payer record and no attestation:

- a class whose income the profile's declared income categories positively exclude (the applicability rule of section 5);
- the urban-rental-as-activity class when the IAE groups of the declared activities show no urban-rental activity.

It is never the origin of a non-zero value. The origin of the other proven zeros of section 5 is unchanged: a payer record is `PAYER_CERTIFICATE` (or `OPERATOR_INPUT` for an `operator_declaration`), and an absence attestation is `OPERATOR_INPUT`. The "Proven zero" bullet of section 5 therefore has three sources: records whose quantity sums to zero, an absence attestation, and an income class the profile declares absent. The code already stamps these origins.

### Certificate evidence in attachment custody (sections 3 and 4)

- The certificate import takes the certificate file. The request carries `source_path` and `source_directory` (the submitting frontend's directory), and the command line takes `--certificate-file`. The worker admits the file through the ledger evidence admission rule (a missing, unreadable, empty or unsupported file is refused), reads its bytes and keeps them through the existing attachment store and attachment service. No new store, attachment kind or persisted schema is added: the manifest kind is `OTHER` and its metadata names the role `retencion_soportada_certificate`.
- The sha256 of the stored bytes is the record's `evidence_fingerprint`.
- `evidence_fingerprint` stays on the request, because the desktop sends it. It names bytes custody already holds, so a second payer can cite a certificate stored by an earlier import. Given together with a file, it is only an integrity cross-check: a value that is not the file's sha256 is refused and nothing is kept.
- The write port refuses a fourth kind of record: one whose `evidence_fingerprint` names bytes that custody does not hold, or holds in a state that no longer hashes to that address (reason `certificate_not_in_custody`). The check applies to every record that carries a fingerprint, an `operator_declaration` included. The three refusals of section 3 stay.
- The import adds the reasons `certificate_file_unreadable` and `certificate_fingerprint_mismatch`. The `certificate_fingerprint_required` text now names the file option.
- Every refusal that does not depend on custody is settled before the bytes are kept, so a refused record leaves nothing behind. If the bytes were kept and a competing write then moves the row, the refusal reports the partial effect, and the record operation's capability profile permits it. The bytes stay in custody; the same file imported again reuses them. A replaced certificate's bytes also stay: they are the evidence of the earlier reading.
- The payload schema, the namespace and the key grammar of section 4 are unchanged.

This is an approved public contract change: the request fields, the refusal reasons, the effect profile of the record operation and the operation contract manifest. The desktop files that depend on the old contract are `native/desktop/frontend/src/shell/ledgerSetup.ts` (the request and refusal-reason types), `native/desktop/frontend/src/components/ledger/setup/WithholdingPane.tsx` (the form sends a typed fingerprint and offers no file), `native/desktop/frontend/src/dev/ledgerWithholdingFixture.ts` and `native/desktop/frontend/tests/scenarios/ledger-setup.spec.ts`. They are not edited by this change.

### Same-evidence correction (section 4)

A replacement whose evidence equals the stored row's evidence overwrites the row under `expected_revision_id`. Its `replaces_evidence_fingerprint` is that same fingerprint, which shows the record as a correction against the same evidence. `RetencionSoportadaRecord` no longer refuses equal fingerprints. A replacement made against a different file is unchanged: it records the fingerprint it replaces, and a replaced fingerprint that is not the stored one is still an identity mismatch.
