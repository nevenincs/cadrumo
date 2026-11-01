---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:6a03a45a9d682a23e9b1f281a343325c4563cf16b614adba8a6daa646af81a67'
related:
  - "[[2026-09-27-export-parity-renta-withholding-sources-adr]]"
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-reference]]"
---
# `export-parity` adr: `suffered-withholding, credit reconciliation and resolution-record schemas` | (**status:** `proposed`)

This record proposes an amendment to the accepted `2026-09-27-export-parity-renta-withholding-sources-adr`. That record fixes the intent of its Steps 2, 4 and 5. This record settles the persisted schemas, which the operator authorized on 2026-11-01 with the design to be approved before any code. The accepted record stays unchanged until this proposal is authorized. The wording to apply then is under "Proposed wording for the accepted record". The scope is plan Phases P03 and P04 (Steps S17, S18, S06, S19 and S20) of `2026-11-01-export-parity-plan`. Evidence is in `2026-11-01-export-parity-suffered-withholding-schemas-reference`.

## Problem Statement

The accepted record chooses a typed per-payer suffered-withholding family, a blocking cross-source reconciliation and an operator resolution record. It does not fix their shapes. Each shape is costly to reverse. The namespace key grammar, the payload schema and the persisted finding reasons have to stay readable for every stored record and calculation revision. The source-kind member and its provider are public registry contracts. Grounding against the official dictionaries also showed that the class-to-casilla mapping cannot be read off the registry as it stands: the 2020 to 2024 role of 0598 names the wrong dictionary field. The accepted Step 5 instruction, to move `aeat_prefilled` onto the new bindings, would also make the informative borrador the winning source for a credit. That is the outcome the accepted record rejected as Option C.

## Considerations

- Official meaning of 0591 to 0609, verified against the bundled 2020 to 2025 dictionaries (reference, "Credit casillas"). 0595 is the cuota resultante, correctly modelled and outside 0609. The 0598 number labels both the inmuebles summary (CRETING) and the credit (RET3). Its 2020 to 2024 role names the summary, and only 2025 names the credit. 0598 is computed from 0153. 0592 to 0594, 0600 and 0601 sum per-entity detail casillas. 0602 is the LIRPF art. 92.8 image-rights ingreso a cuenta.
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
- No Modelo 100 registry edit lands before the Modelo 100 rectification of the earlier plan Step S13 is installed. Bindings and cross-check declarations are placed at the post-rectification baseline (2022), and later years inherit them.
- Payer-side stores never feed this family. The family's resolver reads only its own namespace. Its provider carries no `source_modelo`. The Step 1 payer-side reachability gate stays green.
- Private amounts and payer identifiers are persisted only inside encrypted payloads. Object keys carry only digests. Provenance `source_ref` values use digests, never a plaintext NIF. Logs carry neither amounts nor reason text.
- Every numeric test uses an independent hand-derived oracle and runs through the real repository, resolver, calculation and gate (`2026-06-01-calculation-test-oracle-discipline-adr`).

## Implementation

We will add the suffered-withholding evidence family, a registry-declared credit reconciliation with typed blocking findings, and an operator resolution record, with the schemas below.

### 1. Source kind and provider

- `BindingSourceKind.RETENCION_SOPORTADA = "retencion_soportada"` is added to `src/cadrumo/core/aggregation.py`. It is distinct from `WITHHOLDING` and `RETENCIONES_AGGREGATION`, is not a ledger kind, and is not a member of the counterpart subset.
- The provider model `RetencionSoportadaProvider` is `{ kind = "retencion_soportada", income_class, quantity }`, defined in its own module, `src/cadrumo/domain/calculations/registry/retencion_soportada_bindings.py` (placement is a hypothesis). The module also holds its validator and the class-to-role table.
  - `quantity` is one of `pago_a_cuenta` (retención plus ingreso a cuenta, the credit), `retencion`, `ingreso_a_cuenta`, `ingreso_a_cuenta_repercutido` or `importe_integro`.
  - Credit casillas bind `pago_a_cuenta` only. The other quantities exist for income casillas and cross-checks.
- Registration is one `_filing_grade` row in `binding_provider_registration.py`. It permits the DECIMAL channel and the SUM operation. Terminal origins are `PAYER_CERTIFICATE` and `OPERATOR_INPUT`; plan Step P02.S15 adds `PAYER_CERTIFICATE`. Output is `scalar`, resolver id `retencion_soportada`, stage `mesh`.
- The validator refuses each of the following:
  - a class whose admitted semantic roles do not include the target casilla's role;
  - a binding on a `computed` casilla;
  - `pago_a_cuenta` on a non-credit role;
  - any binding whose target lies outside 0592 to 0606, except income casillas named by a later decision.
- The resolver `RetencionSoportadaSourceResolver` lives in `src/cadrumo/application/aggregation/retencion_soportada_source.py` (placement is a hypothesis). It is enrolled once in the `mesh` stage of `src/cadrumo/application/modelo/calculation_route.py:113-136` and once in `CalculationWithholdingRows` (`src/cadrumo/application/aggregation/service.py:356-377`), so that the report names it when it is absent.

### 2. Closed income-class vocabulary and class-to-role table

`RetencionSoportadaClase` is a core `StrEnum`. The bundled 2024 Renta manual lists the income classes (2024 manual page 1490). RIRPF art. 75 lists the income subject to withholding. Each token admits these semantic roles; the 0598 role is the corrected one in section 7:

| Token | Admitted semantic role | Casilla |
| --- | --- | --- |
| `trabajo` | `irpf_retencion_trabajo` | 0596 |
| `capital_mobiliario` | `irpf_retencion_capital_mobiliario` | 0597 |
| `arrendamiento_inmueble_urbano` (activity or not) | `irpf_retencion_arrendamientos_inmuebles_urbanos` | 0598 |
| `actividad_economica` (excluding urban rentals) | `irpf_retencion_actividades_economicas` | 0599 |
| `ganancia_patrimonial` (including premios) | `irpf_retencion_ganancias_patrimoniales_premios` | 0603 |
| `atribucion_capital_mobiliario` | `irpf_retencion_atribuida_capital_mobiliario` | 0592 |
| `atribucion_capital_inmobiliario` | `irpf_retencion_atribuida_capital_inmobiliario` | 0593 |
| `atribucion_actividad_economica` | `irpf_retencion_atribuida_actividades_economicas` | 0594 |
| `atribucion_ganancia_patrimonial` | `irpf_retencion_atribuida_ganancias_patrimoniales` | 0600 |
| `imputacion_aie_ute` | `irpf_retencion_imputada_aie_ute` | 0601 |
| `imputacion_derechos_imagen` (LIRPF art. 92.8) | `irpf_ingreso_cuenta_art_92_8` | 0602 |

0604 (pagos fraccionados), 0605 (IRNR cuotas) and 0606 (Directiva 2003/48) are not per-payer income classes and are excluded. An unknown token is refused at the model boundary. A record whose class has no consumer in the selected revision raises `unrouted_observation`, which blocks, so a stored certificate is never dropped silently.

### 3. Per-payer record schema (payload v1)

`RetencionSoportadaRecord` carries the following fields:

- `ejercicio`, a `FilingYear`. It is the year the income is imputed to, under the `income-imputation-criterion` decision.
- `payer_tax_id`, a `TaxIdIdentityToken`, and an optional `payer_legal_name`.
- `income_class`.
- `importe_integro_dinerario`, `valoracion_especie`, `retencion`, `ingreso_a_cuenta` and `ingreso_a_cuenta_repercutido`. These are non-negative money values with at most two decimals. A third decimal is refused, not rounded. `ingreso_a_cuenta_repercutido` may not exceed `ingreso_a_cuenta`.
- `origin`, one of `payer_certificate` and `operator_declaration`.
- `evidence_fingerprint`, the sha256 of the certificate bytes held in attachment custody. It is required for `payer_certificate` and optional for `operator_declaration`.
- `replaces_evidence_fingerprint`, optional.
- `captured_at`.

Derived quantities: `pago_a_cuenta = retencion + ingreso_a_cuenta`. Repercusión does not reduce the credit, because LIRPF art. 99.6 makes it decide only inclusion in the base imponible. The write port refuses three kinds of record:

- one whose payer NIF equals the active profile's NIF, because self-withholding is a payer-side fact;
- one whose `ejercicio` lies outside the supported filing years;
- one whose identity differs from the stored row it replaces.

### 4. Namespace

`RETENCION_SOPORTADA_RECORDS_NAMESPACE` is declared in `secure_object_namespaces.py` and enrolled in `namespace_registry.py`:

- key `retencion_soportada_records` and namespace `cadrumo.renta.retencion_soportada.records`;
- owner `cadrumo.application.aggregation`;
- sensitivity `FINANCIAL`, `schema_version` 1;
- scope `PROFILE_LOCAL` and custody `STRUCTURED_CUSTODY`, with the default ciphertext mirror policy;
- key grammar `{ejercicio}:{income_class}:{sha256(payer_tax_id)}` for a payer record, and `absence:{ejercicio}:{income_class}` for an absence attestation.

A payer record holds one row per payer, class and ejercicio. A corrected or replacement certificate overwrites that row under `expected_revision_id`, and the payload records the fingerprint it replaces. The NIF digest uses the existing canonical-token sha256 helper (`percepciones_observations_repository.py:29-37`). The row-identity AAD (`encrypted_columns.py:51`) binds namespace, key digest and schema version. No custom AAD is added. `extract_identifier` re-derives the key from the payload, so a substituted row is refused on load.

### 5. Absent, zero and missing

- **Absent.** The revision declares no `retencion_soportada` binding or cross-check. The resolver returns `None` and reads nothing.
- **Missing.** The family is read and no record and no attestation exist for (ejercicio, class). The bound casilla resolves to nothing, and the existing `unresolved_binding` issue blocks it. A missing value never becomes zero.
- **Proven zero.** Either records exist whose quantity sums to zero (a certificate stating no retención), or an `absence` attestation exists for (ejercicio, class) with a mandatory operator note. That gives a filing-grade 0.00 with an `OPERATOR_INPUT` terminal origin. Hypothesis: an attestation contradicted by a ledger income row of the same class is reported as a finding, following `WithholdingDetailAbsence`.
- **Degraded.** A storage failure is `storage_degradation_resolution` and is never empty.

### 6. Folding the manual 0596 binding and the borrador key contract

- At the 2022 baseline, `renta-certificado-trabajo-retenciones` is deleted and replaced by `renta-retencion-soportada-trabajo` (class `trabajo`, quantity `pago_a_cuenta`) on 0596. Later years inherit it. Bindings with the same pattern are added on 0597 (`capital_mobiliario`) and 0603 (`ganancia_patrimonial`).
- 0598 is not bound to the family. Its value source stays the `renta-retenciones-arrendamientos-urbanos` formula over 0153. `arrendamiento_inmueble_urbano` records become its cross-check. This corrects plan Step S06, because a binding there would collide with the computed-casilla refusal.
- The borrador import and tier share plan Step P02.S15's projected key contract: bound casilla, then its binding id. A snapshot keyed by the deleted id, or by free `casilla.<id>` keys, is refused without migration, under the operator's no-backward-compatibility ruling. The borrador snapshot's content id stops hashing the capture instant (P02.S15).
- `aeat_prefilled` moves onto the family bindings only as the marker that the borrador import projects onto them. Any binding that is the declared value source of a credit reconciliation entry is excluded from the borrador precedence tier, and the exclusion is derived from the declaration (section 7). For those casillas the borrador enters only as a cross-check source. A missing certificate is therefore never filled by the informative prefill. The operator records an `operator_declaration`, and the borrador then corroborates it or blocks it. This amends accepted Step 5.

### 7. Registry declaration of value and cross-check sources

- Each Modelo 100 revision gains a scoped family `credit_reconciliation` at the 2022 baseline. It holds one entry per credit casilla, with `casilla_id`, `value_source` and a list of `cross_checks`.
  - `value_source` is a binding id, or a formula id for 0598.
  - Each cross-check is a typed member: `retencion_soportada { income_class }`, `borrador { binding }`, `filed_observation { modelo, casilla, period }` for 0599 against the filed fourth-quarter Modelo 130 casilla 06 (filing kind per `observation-filing-kind`), or `datos_fiscales { income_class }`.
  - The `datos_fiscales` member is enrolled with plan Step P06.S09 and declared only then.
- Proposed entries:
  - 0596, 0597 and 0603 take their family binding as value source, with the borrador as cross-check;
  - 0598 takes the 0153 formula, cross-checked against `arrendamiento_inmueble_urbano` records and the borrador;
  - 0599 takes the ledger binding of plan Step P02.S05, cross-checked against `actividad_economica` records, the borrador and the filed Modelo 130 casilla 06;
  - 0592 to 0594, 0600, 0601 and 0602 keep their current source, cross-checked against the matching attribution or imputation class.
- The validator refuses each of the following: an unenrolled member; a casilla outside the credit set; a class whose roles exclude the casilla; a value source that is not the casilla's binding or formula; any payer-side modelo (111, 115, 123, 180, 190, 193) as a `filed_observation`.
- The 0598 role and section are corrected at the 2022 baseline to the 2025 values (`irpf_retencion_arrendamientos_inmuebles_urbanos`, the credit block). The 2025 override then becomes redundant. This is part of the Step S13 rectification or of S06, whichever lands first.

### 8. Reconciliation finding

- The reconciliation runs after the mesh and overlay on every calculation of a revision that declares the family. It compares the value-source amount with each present cross-check total by exact `Decimal` equality on two-decimal money, without rounding or tolerance. Per-payer totals are compared where both sides carry payer identity: certificates against datos fiscales, and ledger counterparty against certificate payer. That comparison only informs; the casilla total is what blocks.
- A shared typed fact `SourceDisagreementFact` is added to `CalculationSourceIssue` as an optional `disagreement` field. Older revisions parse with `None`. It is the envelope the `tier-divergence` amendment reuses. It holds:
  - modelo, filing year, period and work unit id;
  - registry revision id and authority generation id;
  - key (`casilla_id` here, binding id for a tier divergence) and value channel;
  - `sources`, an ordered tuple of entries, each giving its role (`value_source`, `cross_check` or a tier name), source family token, resolver id, digest-only `source_ref`, amount, and evidence fingerprint or snapshot id;
  - `selected_role`;
  - `finding_key`, the sha256 of the canonical form of the preceding fields, excluding work unit id and provenance fingerprints.
- New persisted reasons are added, in lockstep, to the `CalculationSourceIssue.reason` Literal, `_DurableSourceIssueReason`, the note catalogue and `dev.locales`:
  - `credit_source_disagreement` joins `GATE_REFUSED_REASONS`. It blocks check, export and local filing.
  - `credit_cross_check_absent` has attention CHECK and does not block. It is emitted once per absent cross-check source and reads "not cross-checked", never agreement.
  - `credit_resolution_stale` has attention CHECK. It is emitted when a resolution exists for the casilla but its `finding_key` no longer matches.
  - `credit_reconciliation_not_screened` covers a Modelo 100 revision persisted before the screen. Verify, export and local filing refuse it with a recalculate remedy. Revisions already `PRESENTADO` are not re-adjudicated.
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
- The gate gains a resolution reader. `blocking_calculation_issues` excludes a `credit_source_disagreement` or `precedence_tier_divergence` issue only when an active record with the same `finding_key` exists.
- The record is keyed to the registry revision, not the calculation revision. A recalculation with unchanged amounts keeps it. Any changed amount, an added or removed source, a different registry revision or a different authority generation changes `finding_key`, so the record stops applying and `credit_resolution_stale` is reported.
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
- Each disagreement blocking with the full fact.
- An absent source reported as not cross-checked.
- A resolution clearing exactly its key and going stale after any amount changes.
- Legacy-revision refusal.
- A teeth fixture whose comparison is weakened to a tolerance, or whose borrador exclusion is removed, failing the gate.

## Rationale

- A separate kind and namespace is the only shape the payment-contract ADR admits. The per-payer key gives the per-payer cross-check that datos fiscales need in P06, at no further schema cost.
- Mapping by semantic role, validated against a closed domain table, makes a wrong registry role a build failure rather than a silent misroute. The 0598 finding shows the misroute is real.
- Crediting the full ingreso a cuenta follows the text of LIRPF art. 99.6.
- Persisting the finding in the revision makes verify and export judge what was calculated. Keeping resolutions in their own encrypted store, matched by a content key, lets a resolution follow unchanged amounts across recalculations and expire on any change. That is the accepted record's "stops applying" commitment.
- Excluding credit value sources from the borrador tier keeps the accepted rejection of prefill-as-primary true. The tier-divergence screen alone would still let the borrador fill a missing certificate.
- Evidence: `2026-11-01-export-parity-suffered-withholding-schemas-reference`.

## Consequences

- Gains:
  - each credit figure rests on per-payer evidence, with its class and origin audited;
  - one disagreement envelope serves this reconciliation and the tier-divergence screen;
  - the 0598 role defect is corrected at the baseline.
- Costs:
  - a new kind, two namespaces, three gate reasons and one advisory, locale text, and a gate signature change in verify, export and filing;
  - operators who keyed 0596 manually must re-enter it as a record;
  - a pure autonomo must attest absence for 0596, 0597 and 0603, or calculation leaves them unresolved and blocks verify and export.
- Reconsider in three cases: if absence attestation friction proves disproportionate (candidate: deriving applicability from typed profile income-source facts); if entity-row designs land for 0592 to 0594, 0600 and 0601 (they would then take the family as value source); if a DGT or TEAC ruling contradicts the reading of art. 99.6 on repercutido ingresos a cuenta.

## Proposed wording for the accepted record

- In Implementation Step 2, replace "Each encrypted per-payer record carries payer NIF, income class, gross amount, withholding, ingreso a cuenta and repercutido, period, evidence fingerprint and origin (payer certificate or operator declaration)." with: "Each encrypted per-payer record carries the fields, namespace and key grammar fixed in `2026-11-01-export-parity-suffered-withholding-schemas-adr`. The credit is retención plus ingreso a cuenta. Repercusión governs only inclusion in the base imponible (LIRPF art. 99.6)."
- In Step 2, after "The class maps to casillas by `semantic_role`.", add: "Casilla 0598 is computed from 0153 and takes urban-rental records as a cross-check only. Attribution and imputation classes cross-check their casillas until entity-row designs exist."
- In Step 4, after "...for 0599 the filed fourth-quarter Modelo 130 casilla 06.", add: "The declaration, finding envelope, persisted reasons and resolution record are those of `2026-11-01-export-parity-suffered-withholding-schemas-adr`. A resolution is keyed to the registry revision and to every source amount, and accepts only the calculated value."
- In Step 5, replace "Move `aeat_prefilled` to the suffered-withholding bindings." with: "Project borrador values onto the suffered-withholding bindings, but exclude every declared credit value source from the borrador precedence tier. For those casillas the borrador is a cross-check only."
