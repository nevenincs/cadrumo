---
tags:
  - '#audit'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ff18ac8014853a0eb2f1805c747bb3af043b7c0df2c015a4638959215119d4a5'
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
