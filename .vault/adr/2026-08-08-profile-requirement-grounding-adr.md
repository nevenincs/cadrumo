---
tags:
  - '#adr'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:9c0ea75ccf84a38132be58b9afda955a02845a508811ba29a9271e482aabd792'
related:
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - '[[2026-08-08-profile-requirement-grounding-reference]]'
  - '[[2026-08-09-profile-requirement-grounding-audit]]'
---
# `profile-requirement-grounding` adr: `unify the profile-requirement schema across the blocking gate, preflight, and readiness surfaces` | (**status:** `accepted`)

## Problem Statement

Three operator-facing surfaces (the blocking readiness gate on calculate/verify/export, `config profile preflight`, `app modelo readiness`) all report "which profile fields are missing" for a filing context, but every surface can only name the raw dotted schema path (e.g. `identity.tax_id`). An operator running the CLI has no way to see a human label, the legal basis, or which modelo(s) actually need a given field. `2026-08-08-profile-requirement-grounding-reference` documents that the richer data (`description`, `legal_refs`, per-operation `model_selectors`) already exists on the schema object in scope at the point each report row is built, and is simply discarded.

## Considerations

- The requirement row (`ProfilePreflightRequirement`) is shared by all three consumers, so one enrichment fixes all three surfaces at once (`2026-08-08-profile-requirement-grounding-reference`, "Three consumers of the same requirement set").
- `build_profile_grounding_index` already computes the registry-binding-derived union (`legal_refs`/`source_refs`/`modelos` per profile key) and is proven safe/cheap by its existing wizard-only consumer, `application/wizard/_legal_zone.py` (`2026-08-08-profile-requirement-grounding-reference`, "The reusable grounding-union source").
- Locale strings for the blocking-gate message must be authored through the `dev.locales` CLI in all four catalogues (en/es/ca/hu), per this project's locale-catalogue mandate.
- `ProfileKey` and `_DEADLINE_RELEVANT_FIELDS` are separate, disconnected mechanisms describing overlapping facts; reconciling or retiring them is a real but distinct question from enriching the canonical requirement row, and needs its own field-by-field parity check before any retirement (`2026-08-08-profile-requirement-grounding-reference`, "Two other, disconnected profile-requirement mechanisms").

## Considered options

- **Enrich the existing `ProfilePreflightRequirement` row (chosen).** Add `label`, `legal_refs`, `modelos` fields populated from data already in scope plus the existing grounding index. No new schema, no new authority, minimal surface area; all three consumers inherit the fix from one shared model.
- **Invent a new unified "operation requirement" schema from scratch.** Rejected: this project already has a working per-operation schema (`ProfileSchemaDefinition`/`model_selectors`); a parallel new schema would be exactly the kind of duplicate authority this codebase's own architecture rules forbid, and would orphan the existing three consumers instead of fixing them.
- **Fix only the blocking-gate message, leave `preflight`/`readiness` JSON alone.** Rejected: the user-visible complaint applies to all three surfaces equally, and they already share one row type, so a partial fix would immediately re-diverge them.

## Constraints

- No new registry or schema authority may be introduced (`aeat-architecture-boundaries`, `no-legacy-compatibility`); the enrichment must read from `ProfileFieldDefinition` and `build_profile_grounding_index`, both already canonical.
- Locale changes must go through `dev.locales set/scaffold` in all four catalogues; hand-editing the YAML catalogues is forbidden.
- `ProfilePreflightMissingPayload` and `ModeloReadinessMissingRequirementPayload` are registered `OutputSchema` JSON contracts; adding fields is additive/backward compatible, but the CLI's documented-command-conformance and JSON-schema-conformance gates must stay green.
- Reconciling `ProfileKey` / `_DEADLINE_RELEVANT_FIELDS` against the canonical schema is deferred to a follow-up Step with its own parity investigation; it is not a precondition for this enrichment.

## Implementation

Add `label: str`, `legal_refs: tuple[str, ...]`, and `modelos: tuple[str, ...]` to `ProfilePreflightRequirement`. Populate them in `ProfilePreflightService.report()` from the `field` object already in scope (`field.description`, `field.legal_refs`) unioned with `build_profile_grounding_index(authority)[selector]` when present. Mirror the three new fields onto `ProfilePreflightMissingPayload` and `ModeloReadinessMissingRequirementPayload`, and update the `application.modelo.errors.profile_readiness_missing` locale template (all four catalogues) to render label + legal ref instead of the bare selector path. Add roundtrip/anti-tautology coverage for the enriched row per this project's quality-gate rules, and a grounded regression proving the blocking-gate message text changes for a known missing field.

## Rationale

The enrichment is the minimum change that closes the gap for all three surfaces at once, using only data this codebase already computes and already trusts (the wizard's `_legal_zone.py` proves the grounding union is safe). It carries no new schema-duplication risk and stays inside this project's "one canonical mechanism per concept" discipline. See `2026-08-08-profile-requirement-grounding-reference` for the full evidence trail.

## Consequences

Operators get a labeled "why" on every incomplete-profile signal instead of a bare dotted path, across the blocking refusal, `preflight`, and `readiness` surfaces uniformly. Two qualifications the original text of this section omitted, corrected here after the 2026-08-09 code review measured the gap against the shipped tree:

**Legal grounding is not uniform across the three surfaces.** `preflight` and `readiness` union each row's `legal_refs` with the registry-binding-derived grounding index (`build_profile_grounding_index`); the blocking refusal deliberately does not (a scope decision, not a performance necessity - see the follow-up plan phase `P06`), so it carries only a field's own schema-declared `legal_refs`. Several fields this enrichment covers, including the two universal baseline fields, declare none in the schema. The blocking refusal therefore ships label-only for those fields today; it is not a uniform "labeled, legally-grounded" experience across all three surfaces, and closing that gap is tracked rather than assumed.

**`legal_refs` and `modelos` are the cross-modelo registry union, by design, not the caller's target modelo.** A row's grounding names every modelo whose registry `source = "profile"` binding consumes that field, not only the modelo the operator happened to be checking. A Modelo 303 `preflight` can therefore cite a Modelo 100 ministerial order as part of a missing field's legal basis. This is intentional - the earlier design (folding the call's target modelo into the same field) conflated "which modelo triggered this check" with "which modelos structurally require this fact", which is exactly the kind of inference the amendment below forbids for the per-operation axis. The `modelos` field is shipped on every surface specifically so the operator can see which modelo(s) the cited grounding actually belongs to; it is not a discriminator hidden from the operator, but it is also not filtered to the target, and an operator scanning only the prose message rather than the structured row could misread a cross-modelo citation as target-specific.

The change touches a shared model consumed in three places plus four locale catalogues (in the end, the catalogues needed no edit - see `P02.S06`), so it needs care not to regress any of the three consumers' existing JSON-schema conformance gates. It does not resolve the separate `ProfileKey`/`_DEADLINE_RELEVANT_FIELDS` redundancy, nor the three further surfaces (`config profile status`, the wizard status surface, overview diagnostics) that read the separate `ProfileKey`-derived mechanism and still emit raw dotted paths; both remain open as follow-up investigations the standing goal ("operators can see why a profile is incomplete, everywhere the CLI says so") still asks for.

## Amendment (2026-08-09): the per-operation axis is empty, and the surface grants readiness without checking

**Status of this amendment:** accepted. It corrects a factual premise in the Problem Statement above; the enrichment decision itself stands and P01 remains correct as landed.

### What the original decision got wrong

The Problem Statement asserts that per-operation `model_selectors` "already exists on the schema object in scope at the point each report row is built, and is simply discarded". Measured against the shipped schema by loading it through `load_user_profile_schema()`: **161 fields, 15 required, 143 `model_selectors` values, and exactly 0 beginning with `modelo_`.** The one selector containing the substring is `withholding.modelo_111_no_retenciones_periods`, a field path rather than an operation token. The data does not exist and never did. The reference document carries the same claim, inherited from the same reading.

`ProfilePreflightService.report()` builds its target as `f"modelo_{modelo.strip()}"` (`_preflight.py:164`) and keeps a field only when a selector `startswith` that prefix (`:168-172`). With zero such selectors the schema-required branch is unreachable for every modelo.

### The consequence is worse than dead code

`report()` returns `ready=not missing`. Because the schema-required branch never contributes, `ready` is decided solely by the export-layout header requirements and the IRNR conditional rules. The 15 schema-required fields — including `identity.tax_id` — never reach the per-modelo report at all.

Driven against a real `UserProfileRecord` declaring **no facts whatsoever**, `report(modelo="303", ...)` returns `ready=True` with `missing=()`. The surface grants readiness for a profile that declares nothing, having checked nothing. That is a silent grant of completeness over an unassessed state, which is precisely the failure mode `no-silent-under-declaration` governs — here on profile completeness rather than on a tax figure. An operator reading `ready` gets the one answer they cannot act on.

The codebase already records the behaviour without naming it a defect: `application/user_profile/tests/test_services.py:172` is `test_preflight_returns_ready_when_no_modelo_selectors_match`. The test encodes the current state as the contract, so it would keep passing through any fix.

### Decision

**The per-operation axis is retained as the intended canonical mechanism, but it MUST NOT report readiness it did not establish.** Three rulings:

1. **The unevaluated case must stop reading as ready.** When the per-modelo branch matches no field for a modelo, the report must not present that as a clean bill of health. It surfaces as an explicit not-assessed signal on the report, and the CLI renders it as a notice. A boolean that means "nothing was checked" and a boolean that means "everything passed" must not be the same boolean.

2. **The axis is populated from grounded evidence, never by inference.** Which profile fact a given modelo requires is a tax question, so each `modelo_<code>` token must be grounded the way any regulatory value is — against the modelo's official form and its registry `source = "profile"` bindings. `build_profile_grounding_index` already computes the binding-derived union of profile keys per modelo and is the honest starting inventory. **Populating the axis by guessing which fields "look" required is forbidden**; an ungrounded token is an invented requirement that will refuse a lawful filing.

3. **`_FILING_BASELINE_PROFILE_PATHS` is not retired by this amendment.** The literal tuple at `_profile_readiness_gate.py:60` remains the operative blocking authority until the axis is populated and proven. Retiring it additionally requires a conditional-requirement grammar on `ProfileFieldDefinition` — `required_when` exists today only on `ProfileKey` (`domain/contribuyente/_keys.py:51-52`) — and the Modelo-100 `activities.description` exemption has no schema expression without it. **That grammar is a separate decision and must not be smuggled in as part of this work.**

### Rejected alternative

Deleting the per-modelo branch and striking the capability claim was considered and rejected. It is the smaller, more immediately honest change, and it would leave the tree with no false claim. But it removes the only mechanism that could ever express "operation X requires facts Y", leaving a two-element hand-written tuple as the sole authority for every modelo — which moves further from the standing goal that every call refuse citing the exact missing fact. Ruling 1 delivers the honesty that deletion would buy, without discarding the mechanism.

### What this amendment does not resolve

The ten-mechanism, four-namespace split recorded in `2026-08-09-profile-requirement-grounding-per-operation-axis-and-silent-defaults-audit` is untouched here, as is the `ProfileKey` / `_DEADLINE_RELEVANT_FIELDS` reconciliation the original decision already deferred. That deferral currently has **no detector**, so the divergence can widen unobserved; a parity gate is the tractable first move and is opened as a row rather than left as prose.

This amendment rules on code, and a ruling is not self-executing. Its implementing rows are opened in the same action in `2026-08-08-profile-requirement-grounding-plan` (phase `P05`). Until those close, HEAD carries the rejected behaviour while this record reads as in force — the gap this project has been burned by before.

## Amendment (2026-08-09b): conditional requirements stay UNSCOPED, and the `required` conjunct is load-bearing

**Status:** accepted. Settled jointly by the two agents working this campaign after the axis was populated.

### The question

Once the axis carried grounded `modelo_<code>` tokens, only **1 of 32** sat on a `required = true` field (`identity.tax_id` → `modelo_100`). The other 31 are inert for preflight selection, because the per-modelo walk is `field.required AND selectors match the modelo`. That invites an obvious-looking fix: extend the walk to conditionally-required fields so the other tokens "work".

### Decision: do not. Conditionals remain unscoped, and the `required` conjunct must not be loosened.

### The reason is an invariant, not a count

Stated first and deliberately without numbers, because the evidence below is a fact about today's data and **this is not**:

> `ProfilePreflightService._selectors_match_modelo` treats an empty selector tuple as matching **no** modelo, not as a wildcard. Scoping conditional requirements to the axis would therefore make "untokenised" mean **never checked** rather than "checked everywhere". The failure mode of an authoring gap inverts from over-asking to silent omission. **This holds regardless of how many paths are tokenised at any given moment.**

Verified in source and behaviourally: `()` → `False`; `("modelo_100",)` vs `modelo_100` → `True`; `("modelo_303",)` vs `modelo_100` → `False`.

The distinction matters because this decision **explicitly permits** tokenising a conditionally-required field for grounding and display — the same basis on which the 31 inert tokens are correct. So the measurement below is expected to change, legitimately. A reader who finds it outdated must not conclude the reasoning lapsed with it.

### Evidence of blast radius, as measured on 2026-08-09 (not the reason)

Driving the real resolvers over value sets that trigger each rule, **4 conditionally-ADDED paths exist and all 4 carry no `modelo_` token**:

- `taxpayer_type.country_of_fiscal_residence`
- `taxpayer_type.representante_fiscal_nif`
- `taxpayer_type.representante_fiscal_nombre` (via `conditional_profile_required_paths`)
- `attribution_entity_socios.<row>.country_of_residence` (via `atribucion_socio_missing_country_paths`, row-scoped)

The two representante-fiscal fields are what a non-EU/EEA-resident IRNR filer is legally required to declare. Under the rejected alternative they would silently never be asked for.

**`iva.regime` is deliberately excluded from that count.** It is the INVERSE shape: `required = true` in the schema and conditionally *relaxed* by `iva_regime_required`, not conditionally added. It travels the required-field path, not the conditional one, so counting it here would overstate the figure. An earlier exchange between the two agents circulated "5" by including it; **4 is the correct count of conditionally-added paths**, recorded because a wrong number in an ADR outlives the conversation that produced it.

### Why a completeness gate does not rescue the alternative

A gate over the 53 binding-derived pairs was considered as a precondition and rejected on a structural argument rather than a data one: a gate makes *today's* state safe, but with empty-means-no-match the **default for every newly-added conditional field is "fires for nothing"**. The next author who adds a representante-fiscal-shaped requirement and omits the tokens gets silence — permanently — unless the gate also fails on new untokenised conditionals, i.e. unless it becomes a standing authoring obligation.

Under this decision the default runs the safe way: an untokenised conditional **over-asks**.

### What this means for the inert tokens

They are **correct as they stand** — real grounding, verified against live registry bindings, populating `legal_refs` and `modelos` on requirement rows, inert for *selection* by design rather than oversight.

**The `required` conjunct is load-bearing precisely BECAUSE the selector predicate treats empty as no-match**, and those two facts live two functions apart. A reader who notices inert tokens will reach for the conjunct — the nearer of the two — and will not see the semantics that make loosening it unsafe. Naming that adjacency is the main purpose of this amendment; the verdict is secondary.

### The axis is not the primary safety net

Worth stating so it is not over-credited: the per-modelo walk currently selects one field for one modelo. Requirement enforcement today is carried by the **unscoped** validation path and the **unscoped** conditional path, both of which run regardless of modelo. The per-operation axis is additive precision on top of those.


### The same predicate governs the REQUIRED path, so `assessed = True` is not a completeness claim

`_selectors_match_modelo` is the same predicate on both paths, so empty-means-no-match applies to `required = true` fields too: **an untokenised required field is skipped by the per-modelo walk for every modelo.** Measured on 2026-08-09: 15 required fields, **1 tokenised**.

The consequence is on `per_operation_requirements_assessed`, and it runs opposite to the intuition. `assessed = False` is honest — it reports that nothing was examined, which is the whole reason the flag exists. **`assessed = True` is the weaker signal**: it reads as "the required fields for this modelo were checked" when it means "the *tokenised* required fields were", currently one field out of fifteen.

Driving `report()` for modelo 100 with only `identity.tax_id` declared returns `assessed = True`, `ready = True`, `missing = ()` — while `iva.regime` is `required = true`, genuinely required for that record, and unreported.

**So `assessed = True` is a claim about the axis, never about the modelo's requirements.** It does not mean the profile is complete for that modelo; the unscoped validation path is what establishes that, and it runs elsewhere. A consumer that renders `assessed = True` as reassurance would be making a completeness claim this field cannot support.

One caution on sizing this, because the obvious count is wrong: a naive tally says fourteen required fields go unreported. It is **one**. `missing_required_field_paths` is row-aware, so the ten `attribution_*` and two `usage_ratios` columns correctly do not count for a filer who declared no such rows. The real gap is `iva.regime` — smaller than the naive figure and a cleaner example, being a field a real filer must actually declare rather than an artefact of counting repeatable columns.


#### The gap sat exactly on the boundary of this document's own taxonomy

Worth stating because it generalises past this field. The one genuinely-unreported requirement is `iva.regime` — **the same field excluded from the conditional count above as "the inverse shape"**.

It fell between the two categories this amendment defines. Excluded from the conditional path *correctly*, because it is conditionally relaxed rather than conditionally added. Invisible on the required path because it carries no token. Both agents examined it closely — one to argue the exclusion, one to accept it — and neither asked what the **other** path did with it.

So a field that fits neither bucket cleanly is precisely where a gap survives a review that checks each bucket carefully. A taxonomy makes each category auditable and simultaneously creates a seam between them, and the seam is not visible from inside either category. When this document's distinction is used again, the question to ask is not "is this correctly classified" but "what does the path I just classified it OUT of do with it".

#### On renaming the flag: the window has closed, and the sentence is now the remedy

A narrower name was proposed — `per_operation_requirements_assessed = True` invites the completeness reading, and a rename would protect a reader who never opens this record, where a sentence only protects one who does. The reasoning is sound.

Measured before recommending it: the field already carries **21 references across 9 modules**, including the CLI payloads, the readiness command, profile inspect and the state projection. It was cheap to rename while it had two consumers; it no longer does. A rename is now a deliberate sweep with its own atomic commit, not an opportunistic fix, and it would collide with in-flight work across most of those modules.

So the sentence above is the remedy of record. If a rename is still wanted later, this note is the argument for it and the cost estimate — and the reason the opportunity was missed is worth keeping: the naming risk was identified one exchange after the field had already been wired through to the operator surface.


### Honest limits

An initial attempt to size the blast radius by parsing `schema.toml` returned zero and was **discarded as a broken probe rather than reported** — the conditional set is assembled in code, not declared in TOML, so a schema walk cannot see it. Recorded because a zero from a broken instrument is exactly the number that gets repeated later as though it meant something.

