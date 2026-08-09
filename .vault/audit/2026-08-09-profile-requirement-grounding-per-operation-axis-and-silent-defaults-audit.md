---
tags:
  - '#audit'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:af0134df296c62503332bee05a5730c770e524de03fbd54ab66e148b9fc7851a'
related:
  - "[[2026-08-08-profile-requirement-grounding-adr]]"
---

# `profile-requirement-grounding` audit: `the per-operation requirement axis is empty and absent profile facts silently default`

Two structural findings from a swarm sweep, both verified against the loaded schema and the real call graph rather than taken from sub-agent output. The first falsifies a premise the accepted ADR rests on; the second is the concrete mechanism by which an incomplete profile produces confident wrong output instead of a refusal.

### The per-operation `model_selectors` axis has zero `modelo_` entries, so the preflight filter can never match

**Pathway:** blocking gate / `config profile preflight` / `app modelo readiness`.

`src/cadrumo/application/user_profile/_preflight.py:164` builds the target prefix `f"modelo_{modelo.strip()}"`, and `:168-172` keeps a field only when one of its `model_selectors` starts with that prefix. Loading the shipped schema through `load_user_profile_schema()` measures **161 fields, 15 required, 143 `model_selectors` values, and exactly 0 beginning with `modelo_`**. The single selector containing the substring is `withholding.modelo_111_no_retenciones_periods` (`_data/registry/cadrumo/user_profile/schema.toml:1124`), which is a field path, not an operation token — it does not start with `modelo_`.

The per-modelo branch of `ProfilePreflightService.report()` is therefore unreachable for every modelo. The codebase already records the behaviour without naming it a defect: `application/user_profile/tests/test_services.py:172` is called `test_preflight_returns_ready_when_no_modelo_selectors_match`.

**What is lost.** The accepted ADR states that per-operation `model_selectors` "already exists on the schema object in scope at the point each report row is built, and is simply discarded". Against the shipped data that is not so: the data does not exist. The enrichment landed by P01 is real and correct, but it decorates a requirement set the per-operation axis contributes nothing to. What actually blocks filing-grade work is `_profile_readiness_gate.py:60`, a two-element literal `_FILING_BASELINE_PROFILE_PATHS = ("identity.tax_id",)` plus a bespoke Modelo-100 branch at `:118-141`. So "which profile facts does operation X require" is answered today by a hand-written tuple, not by the schema.

**Remediation.** Decide the axis explicitly and record it, because both directions are defensible and the current state is the only indefensible one. Either populate `model_selectors` with `modelo_<code>` tokens for the fields each modelo genuinely needs — which makes the schema the canonical per-operation authority and lets `_FILING_BASELINE_PROFILE_PATHS` retire into it — or delete `_preflight.py:92-110` and `:164-172` and strike the capability claim from the module docstring at `:41-47`. Retiring the baseline tuple into the schema additionally requires a conditional-requirement grammar on `ProfileFieldDefinition`; `required_when` exists today only on `ProfileKey` (`domain/contribuyente/_keys.py:51-52`). That grammar is the real prerequisite and should be scoped as its own decision.

### An absent profile silently yields NIF `00000000T` and régimen `GENERAL` across fourteen CLI surfaces

**Pathway:** every CLI command reading the active profile through the shared adapter.

`src/cadrumo/application/user_profile/_projections.py:248` declares `tax_id_default: str = "00000000T"` alongside `iva_regime_default: IVARegime = IVARegime.GENERAL`. `src/cadrumo/entrypoints/cli/_common.py:667-673` reaches it with an empty mapping whenever no profile record exists:

```python
record = state.active_profile_record()
if record is None:
    return projection_for_taxpayer({})
```

`_profile_to_taxpayer` has fourteen call sites across `_overview.py`, `_modelo_records_cli.py`, `_modelo_work_verification_cli.py`, `_modelo_export_cli.py`, `_ledger.py`, `_app_quickfile.py` and `_modelo_review_package_cli.py`. None of them distinguishes a placeholder from a declared value.

**What is lost.** The refusal the operator should receive is replaced by output computed on fabricated identity. Three consequences were traced concretely. `_modelo_records_cli.py:275` passes the placeholder as `expected_tax_id`, which makes the correct application-layer refusal at `application/modelo/_external_import_actions.py:399-407` structurally unreachable — it fires only on an empty string, and the CLI never sends one — so the operator instead sees a justificante-mismatch error naming a NIF they never entered. `_overview.py:327,332,338` filter filed evidence by strict NIF equality (`application/overview/_calendar_evidence.py:411-413`), so with the placeholder every genuinely filed obligation is dropped and reappears as unfiled; the calendar refuses on an undeclared taxpayer model but not on a missing NIF, so it renders confidently. `_ledger_support.py:244-257` returns a hardcoded `"ES"` source jurisdiction when `fiscal_residency` is `None`, because both its refusals key on a *positive* IRNR or impatriado declaration — the undeclared case falls through to Spanish-source and is persisted onto the transaction.

The common shape is worth stating on its own: **these guards refuse on a declared-and-wrong value and fall open on an absent one**, which inverts the safe default for exactly the population still mid-setup.

**Remediation.** Make absence representable and refusable rather than substitutable. The narrowest change that does this is to stop defaulting at the CLI boundary: have `_profile_to_taxpayer` refuse when no record exists, and make `tax_id_default` non-defaulting on the projection so each caller states its intent. Callers that legitimately want a partial projection for display (`overview status`, `overview explain`) then opt in explicitly and surface the placeholder as an advisory notice. Sequence it behind the axis decision above, because the refusal should name the missing selector, and today only the hand-written baseline can supply that name.

### `tax_residence.ccaa` is optional everywhere, so the foral guard is a no-op

**Pathway:** `app modelo work create --modelo 100`.

`application/modelo/_work_create_policy.py:185-187` reads `raw_ccaa = fact_value(record, "tax_residence.ccaa")` and parses it only `if raw_ccaa`. The field is `required = false` in `schema.toml:270-272`, is absent from `_FILING_BASELINE_PROFILE_PATHS` (`_profile_readiness_gate.py:60`), and is not conditionally required by `application/user_profile/_completeness.py:34-53`. An undeclared CCAA therefore parses nothing and raises nothing.

**What is lost.** Downstream the autonómico tranches fall back to the estatal parameter, so a foral or divergent-CCAA filer gets a común-régimen Modelo 100 built, calculated, verified and exported — by a tool that carries an explicit refusal for precisely that case. This is the under-declaration shape the project's own no-silent-under-declaration rule governs, reached through an optional field rather than a missing formula.

**Remediation.** Treat CCAA as conditionally required for the modelos whose calculation reads an autonómico parameter, which again needs the conditional-requirement grammar named in the first finding. Until that exists, the honest interim is an advisory notice on `work create` naming `tax_residence.ccaa` when a CCAA-sensitive modelo is targeted and the fact is absent — visible, not silent.

### Ten mechanisms declare profile requirements across four unconvertible namespaces

**Pathway:** cross-cutting.

The requirement concept is spelled in four namespaces that cannot be compared without a translation layer: dotted schema paths (`identity.tax_id`), selector aliases (`tax.id`, `has_employees`), `TaxpayerProfile` attribute names (`_DEADLINE_RELEVANT_FIELDS`, `application/overview/_explain.py:137`), and CLI flag names (`application/user_profile/_filing_baseline.py:14-41`). Two measured divergences show the cost. The schema declares 15 required fields while the wizard-compiled `PROFILE_KEYS` (`application/wizard/_compiler.py:66-70`) declares 1, so `validate_profile_values` returns `valid=True` for a record that `ProfileValidationService` refuses — opposite verdicts on the same record from two surfaces. And `_calendar_warnings.py:287` intersects a mixed flat/dotted key tuple against a dotted-only set, so every flat key is silently dropped and `has_employees` can never contribute to the censo enrolment verdict.

**What is lost.** No single place answers "operation X requires facts Y", so each surface answers it differently and the disagreements are invisible.

**Remediation.** This is too large for one change and should not be attempted as one. The tractable first move is a parity gate rather than a refactor: a test asserting that the schema-required set and the `PROFILE_KEYS`-required set agree, failing with the field-level delta. That converts a silent divergence into a visible one and pins the surface before anything is moved. The ADR already defers the `ProfileKey` / `_DEADLINE_RELEVANT_FIELDS` reconciliation; this audit adds that the deferral currently has no detector, so the divergence can widen unobserved.

### Method note: what was verified and what was not

The two headline findings were re-verified after the swarm reported them — the selector count by loading the real schema in-process, the placeholder by reading the declaration and enumerating call sites. The ten-mechanism inventory and the per-command classification are sub-agent output confirmed only at the `file:line` level, not exhaustively; the per-command table in particular covers commands reachable from the profile read paths traced, not all ~300 CLI verbs. One reported item is explicitly **unconfirmed** and should not be actioned as fact: that `verify`/`file`/`export` may resolve the readiness gate against the work unit's bucket while building the taxpayer projection from the workflow state's active profile, which would diverge under a `--bucket-id` override.

### Outcome (2026-08-09, same day): what was actioned, and one finding withdrawn

Appended after acting on the placeholder finding, so a later reader does not re-derive a claim this document itself no longer supports.

**Fixed and verified:**

- `_modelo_records_cli.py` — the placeholder made `import_external_filing_evidence`'s existing refusal structurally unreachable (it fires only on a falsy identity). Fixed in `a7c58e309b` by reading the declared identity.
- `_overview.py` calendar — the evidence matchers fail OPEN on an empty identity and CLOSED on a non-empty wrong one, so the placeholder dropped genuinely filed obligations and redisplayed them as unfiled. Fixed in `a82de57da0`.
- `_ledger_support.py` — unrelated to `_profile_to_taxpayer` but the same shape: an undeclared `fiscal_residency` fell through to a hardcoded `"ES"`, defeating the impatriado aggregation's documented invariant that an unresolved jurisdiction "is NEVER silently coerced to ES". Fixed in `c8b26b1fc4` by resolving to `None`, the state that aggregation already handles.

**Withdrawn:** the claim does NOT hold for `_modelo_work_verification_cli.py` (`work dependencies`). A fix was written, then withdrawn unshipped. Driving the real clean-state evaluator over one seeded, genuinely-filed observation and varying only the identity:

| `taxpayer_tax_id` | blockers |
|---|---|
| `"00000000T"` (placeholder) | `mismatched_external_evidence_record` |
| `None` | `mismatched_external_evidence_record` |
| `"X1234567L"` (**correct**) | `mismatched_external_evidence_record` |

Identical in all three, **including the correct identity** — so that path was not identity-gated at all under this seed, and a test asserting "placeholder blocks" passed for an unrelated reason. Only the correct-identity positive control exposed it. Without that control a no-op change and two tests encoding a false belief would have shipped looking green.

**A smaller, real finding replaces it.** This surface has two identity paths with OPPOSITE empty-handling — `_aeat_register_provenance_blockers` skips on empty, `_justificante_matches_filing` returns `False` on empty — and both map to the same `MISMATCHED_EXTERNAL_EVIDENCE_RECORD`. So an operator who has declared no NIF is told their external evidence record is mismatched, pointing them at their filed evidence rather than at their profile. The fail-closed half is arguably correct for a clean-state gate (official AEAT evidence cannot be confirmed without knowing whose it is); what is wrong is that absence and mismatch are indistinguishable in the report. Remediation is a distinct unresolved-identity blocker in `application/calculations`, not a CLI change — it alters a typed enum consumed by verification surfaces and needs its own decision. **Not actioned here.**

### Correction: a call-site count is not a defect count

The finding above is headed "across fourteen CLI surfaces", and that framing was wrong in a way worth naming, because it is the kind of error that reads as rigour.

Fourteen is the number of `_profile_to_taxpayer` call sites. It is not the number of defective ones. Whether the placeholder does harm at a given site depends entirely on how that site's CONSUMER handles an empty value — and the consumers disagree: some fail open on empty (placeholder harmful, absence safe), one fails closed on empty (both equally blocked), and the rest are unexamined. Two of the three sites investigated were genuine defects; one was not.

So the honest scope is: **three sites investigated, two defects fixed, one withdrawn, eleven unexamined** — not "fourteen surfaces affected". Counting the call sites and reporting that count as the blast radius silently substitutes an easy measurement for the hard one, and the resulting number is both precise and unearned.

### Sweep closed: every call site examined, and the exposure is far narrower than this finding claimed

The correction above left "eleven unexamined". They are now examined. There are **twelve** call sites, not fourteen — the original count included the function definition and double-counted a file. Every one is classified below, and **no further placeholder defect exists**.

**Guarded — the placeholder is structurally unreachable (5).** `identity.tax_id` is a member of `_FILING_BASELINE_PROFILE_PATHS`, so `require_profile_ready_for_work_unit` refuses an undeclared identity before these paths run: `_modelo_export_cli.py:188` (gate at `_export.py:1220`, which precedes the header build at `:665` where the NIF would otherwise be written into the fichero), `_modelo_review_package_cli.py:248` (routes through `export_modelo_revision`), `_modelo_work_verification_cli.py:179` (verify, gate at `:178`) and `:499` (file, gate at `:498`), and `_app_quickfile.py:127` (routes through the create/calculate/verify/export gates).

The export case is the one worth stating explicitly, because it is where the alarm would have been justified: a placeholder NIF reaching `_export.py:665` would be written into a filed fichero-BOE artefact. It cannot, because the baseline gate refuses first — and it refuses on the DECLARED record, not on the projection.

**Fixed (3).** `_modelo_records_cli.py:275` (`a7c58e309b`), `_overview.py:321` (`a82de57da0`), and the residency-driven jurisdiction default in `_ledger_support.py` (`c8b26b1fc4`).

**Not identity-bearing (4).** `_overview.py:204` (status), `:626` (agenda), `:702` (backlog), `:765` (explain). These derive which obligations apply; they do not match identity. `build_overview_calendar` accepts an `expected_tax_id`, but `status` does not pass one, so it defaults to `None` and fails open; `build_overview_agenda`, `build_overview_backlog` and `build_overview_explain` take no identity at all.

**Withdrawn (1).** `_modelo_work_verification_cli.py:286`, per the section above.

`_ledger.py:381` reads only `fiscal_residency` and `irpf_special_regime`, both of which are honestly `None` when undeclared — the projection fabricates no value on those axes.

**What this means for the finding's own framing.** The heading says the placeholder "silently yields NIF `00000000T` ... across fourteen CLI surfaces". Measured: **two** sites were genuinely harmed by it, five were already protected by an existing gate, four never compare identity, and one claim did not reproduce. The filing-grade surfaces — the ones where a fabricated NIF would have reached a persisted or exported artefact — were **all** already guarded.

The defect was real and worth fixing, and it was narrower than a call-site census made it look. Recorded at this length because the overstatement is the more transferable lesson: the census was easy, precise and wrong, and the only thing that corrected it was reading each consumer's own handling of an empty value.

### Withdrawn: the CCAA foral finding does not survive verification either

The `tax_residence.ccaa` finding above is **retracted in its load-bearing claim**. Verified against the real code rather than re-read from the sweep that produced it.

**"The foral guard is a no-op" is false.** `guard_active_profile_foral_ccaa` documents its own contract as raising the foral refusal "if present", and it honours it. Driving `parse_tax_region` directly:

```
'madrid'      -> madrid
'pais_vasco'  -> ForalRegimeError: foral regime outside the scope of this profile
'navarra'     -> ForalRegimeError
'PAIS_VASCO'  -> ForalRegimeError          (case-insensitive)
'andalucia'   -> andalucia
''            -> TaxResidenceProfileError: unknown tax-region
```

A **declared** foral filer is refused at work-create. The claim that such a filer "gets a común-régimen Modelo 100 built, calculated, verified and exported" is wrong: they cannot create the work unit.

**"Silently falls back to estatal" is also wrong.** The fallback is a documented, deliberate decision at `_profile_binding.py:505-511`, which cites the 0511/0512 mínimo-del-contribuyente precedent and names the CCAA whose own 2025 figures are a follow-up, stating in terms that they are "a named follow-up, **not silently assumed to mirror estatal forever**". The partial-divergence design is also deliberate: a CCAA regulating only some tranches resolves per-tranche rather than needing a full parallel table.

**What survives is narrow.** `tax_residence.ccaa` is genuinely optional, genuinely absent from the filing baseline, and genuinely not conditionally required — so an **undeclared** CCAA receives estatal parameters with no advisory. That is the same optional-field-without-a-conditional-requirement-grammar gap already recorded in the first finding, not a separate defect, and it is the general case that grammar exists to solve.

### Pattern across the withdrawals: measured findings held, reasoned ones did not

Three findings in this document have now been tested against running code. The split is not random and is worth stating.

**Held — both established by driving the real code in-process:** the per-operation axis measurement (161 fields, 143 selectors, 0 `modelo_`-prefixed, and `report()` returning `ready=True` for a profile declaring nothing), and the calendar matcher behaviour (fail-open on empty, fail-closed on mismatch, placeholder drops filed evidence).

**Withdrawn — both asserted downstream CONSEQUENCES from reading code paths:** the `work dependencies` claim (three-way probe showed the path was not identity-gated at all under that seed) and the CCAA claim (the guard raises; the fallback is documented).

The distinguishing factor is not care or detail — the withdrawn findings carried precise `file:line` citations and plausible mechanisms. It is whether the claimed BEHAVIOUR was ever executed. A code path read carefully still only supports "this branch exists"; it does not support "and therefore the operator sees X", because the consequence depends on callers, guards and defaults that are not visible from the site. Every consequence claim in an audit should carry either a probe that produced it or an explicit marker that it is inferred and untested.


### The replacement finding is now fixed, and it needed measuring first too

The withdrawal section above recorded a smaller real finding in place of the `work dependencies` claim — absent and mismatched identity reporting the same blocker — and marked it **not actioned**. That is now stale: it is fixed in `1ca1b2dec9`. Recorded here so the entry does not keep reading as open work.

**It was measured before it was touched**, because it had been recorded from a code READ, which is the class this document has already retracted twice. Probing both identity paths directly:

| path | correct | wrong | empty / None |
|---|---|---|---|
| `_aeat_register_provenance_blockers` | `[]` | mismatch | **`[]`** — fails open |
| `_justificante_matches_filing` | match | mismatch | **mismatch** — conflates |

So the finding held on the justificante path **only**. The register path already handled absence correctly, which is narrower than the original note implied and is why the fix brings one path into line with its sibling rather than introducing a new convention.

`UNRESOLVED_TAXPAYER_IDENTITY` now reports the absent case. The gate stays fail-closed — an unidentifiable receipt still blocks — so only the reason changes, and the reason is what tells the operator to fill in their profile rather than to go looking at a receipt they cannot alter.

**The first attempt at the fix was wrong, and the existing suite caught it.** Checking identity BEFORE the match let an absent identity mask a genuinely mismatched modelo, year or period — the exact inverse of the confusion being removed. `test_cross_period_clean_state_blocks_mismatched_justificante_metadata` went red and named it. The identity axis is now neutralised for the match probe and judged separately afterwards.

That is worth recording beside the pattern above rather than buried in a commit message. The lesson from the two withdrawals was "execute the claim before believing it"; this shows the same rule applies to the FIX, not only to the finding. A remedy reasoned from a correct diagnosis can still be wrong in a way only running it reveals, and the thing that caught it was a test written by someone else for an unrelated case.

