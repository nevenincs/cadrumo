---
tags:
  - '#adr'
  - '#profile-requirement-grounding'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:28d48bdc24c79feeaa79147ea86985a58948a9d9823b146c20b62f0f91f2a119'
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

**Status:** accepted. Settled jointly by the two agents working this campaign after the axis was populated; both positions and the measurements behind them are recorded below.

### The question

Once the axis carried grounded `modelo_<code>` tokens, a measurement showed only **1 of 32** sat on a `required = true` field (`identity.tax_id` → `modelo_100`). The other 31 are inert for preflight selection, because the per-modelo walk is `field.required AND selectors match the modelo`. That invites an obvious-looking fix: extend the walk to conditionally-required fields so the tokens "work".

### Decision: do not. Conditionals remain unscoped, and the `required` conjunct must not be loosened.

### The decisive mechanism

`ProfilePreflightService._selectors_match_modelo` treats an EMPTY selector tuple as **no match**, not as a wildcard:

```python
if not selectors:
    return False
```

Verified in source and behaviourally: `()` → `False`, `("modelo_100",)` vs `modelo_100` → `True`, `("modelo_303",)` vs `modelo_100` → `False`.

So scoping conditionals would not *narrow* an untokenised conditional field to fewer modelos — it would match **no modelo at all** and stop the check firing entirely.

### Measured blast radius

Driving the real `conditional_profile_required_paths` resolver over value sets that trigger each rule: **3 distinct conditionally-required paths**, and **all 3 carry no `modelo_` token**:

- `taxpayer_type.country_of_fiscal_residence`
- `taxpayer_type.representante_fiscal_nif`
- `taxpayer_type.representante_fiscal_nombre`

The last two are the fiscal-representative fields a non-EU/EEA-resident IRNR filer is legally required to declare. Under the scoping change they would silently never be asked for — no error, no advisory, just an absent prompt. The M184 socio `country_of_residence` rule is a separate resolver of the same shape and equally untokenised.

### Why a completeness gate does not rescue the alternative

A gate over the 53 binding-derived pairs was considered as a precondition and rejected, on an argument that is about the predicate rather than the data: a gate makes TODAY's state safe, but with `empty → False` the **default for every newly-added conditional field is "fires for nothing"**. The next author who adds a representante-fiscal-shaped requirement and omits the tokens gets silence, permanently, unless the gate is also written to fail on new untokenised conditionals — i.e. unless it becomes a standing authoring obligation.

Under the decision above the default runs the safe way: an untokenised conditional **over-asks**. That is a property of the predicate's semantics, not of how complete the grounding happens to be, which is why it is not tradeable for a gate.

### What this means for the 31 inert tokens

They are **correct as they stand**. They are real grounding, verified against live registry bindings, and they populate `legal_refs` and `modelos` on requirement rows. They are inert for *selection* by design, not by oversight.

**The `required` conjunct is load-bearing precisely BECAUSE `_selectors_match_modelo` treats empty as no-match** — and those two facts live two functions apart. A reader who notices 31 inert tokens will reach for the conjunct, which is the nearer of the two, and will not see the semantics that make loosening it unsafe. Naming that adjacency here is the point of this amendment, more than the verdict is.

### Also recorded: the per-modelo axis is not the primary safety net

A related measurement, worth stating so the axis is not over-credited: the per-modelo walk currently selects exactly one field for one modelo. What actually carries requirement enforcement today is the **unscoped** validation path and the **unscoped** conditional path, both of which run regardless of modelo. The per-operation axis is additive precision on top of those, not the mechanism holding the floor.

### Honest limits

The blast-radius figure covers the paths reachable from the resolvers driven here. An initial attempt to count conditional entries by parsing `schema.toml` returned zero and was **discarded as a broken probe rather than reported as a result** — the conditional set is assembled in code (`application/user_profile/_completeness.py`), not declared in TOML, so a schema walk cannot see it. Recorded because a zero from a broken instrument is exactly the number that gets repeated later as though it meant something.

