---
tags:
  - '#plan'
  - '#modelo-enum-hardening'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-modelo-enum-hardening-adr]]'
---


# `modelo-enum-hardening` `Modelo enum hardening and centralisation follow-ups` plan

### Phase `P01` - Discovery and decisions

Quantify the value-vs-member inconsistency and investigate modelo:str max_length=8 fields before any change

- [x] `P01.S01` - Quantify Modelo member vs .value usage and record the decision to prefer the enum member where StrEnum semantics suffice; `src/aeat`.
- [x] `P01.S02` - Investigate every modelo:str max_length=8 field to determine which carry pure modelo codes versus composite/loose forms; `src/aeat/**/_schema.py, _models.py, payloads`.

### Phase `P02` - Literal rollout

Convert Literal code-string fields to Literal Modelo-member fields

- [x] `P02.S03` - Convert Literal code-string fields to Literal[Modelo.M<code>] and update the CI gate exclusions; `src/aeat/adapters/inbound/borrador/_schema.py, src/aeat/adapters/outbound/aeat/sede/_schema.py, src/aeat/domain/calculations/registry/_ledger_bindings.py, src/aeat/domain/renta/_ledger_expenses.py, src/aeat/core/tests/test_modelo_string_usage.py`.

### Phase `P03` - Value vs member standardisation

Adopt one convention: enum member where StrEnum suffices, .value only where a plain str is contractually required

- [x] `P03.S04` - Standardise to the enum member in comparison/membership/dict-key/str-field positions; `reserve .value for genuine plain-str contracts; `src/aeat (files touched in the modelo-enum sweep)`.

### Phase `P04` - Registry-resolver rollout for rates

Route amortisation 3pct and REBECA 50pct through the registry-backed resolver with legal grounding

- [x] `P04.S05` - Route AMORTIZACION_INMUEBLE_RATE through a registry parameter and _resolve_ fallback with legal grounding and a grounding test; `src/aeat/domain/fincas/_amortization_ledger.py, src/aeat/_data/registry/aeat/..., legal catalogue`.
- [x] `P04.S06` - Route REBECA_MARITIME_EXEMPTION_FRACTION through a registry parameter and _resolve_ fallback with legal grounding and a grounding test; `src/aeat/domain/renta/_maritime_exemption.py, src/aeat/_data/registry/aeat/..., legal catalogue`.

### Phase `P05` - Typed modelo fields

Retype confirmed-pure modelo str fields to Modelo where safe; document the rest

- [x] `P05.S07` - Retype the confirmed-pure modelo:str fields to Modelo where serialization and validation stay sound; `document each field left as str; `src/aeat (modelo:str fields identified in P01.S02)`.

### Phase `P06` - CI gate robustness

Reduce false-positive reliance in the modelo-string gate

- [x] `P06.S08` - Refactor the period digit-membership false positive so it no longer reads as a modelo code; `keep the article-number allowlist with its reason; `src/aeat/application/modelo/_workflow_gate.py, src/aeat/core/tests/test_modelo_string_usage.py`.

## Description

This plan tracks the follow-on hardening from the in-session Modelo-enum and
regulatory-value centralisation campaign (commits `cae8e870a` through
`83b7b4fee` on `chore/eliminate-shims`). That campaign introduced the canonical
`Modelo` StrEnum, swept roughly sixty production identifier sites from bare
code strings to enum members, added the retired `M037` non-registry member, and
committed an AST CI gate (`test_modelo_string_usage.py`). This plan closes the
deferred and newly-discovered items: the Literal-annotation rollout, the
value-versus-member inconsistency the sweep introduced (81 `.value` against 67
bare-member uses), the registry-resolver rollout for the amortisation and REBECA
rate constants, a per-field investigation of `modelo: str` fields declared with
`max_length=8`, and a CI-gate false-positive cleanup. No new domain behaviour is
introduced; every Step is behaviour-preserving or registry-grounded and gated by
tests.

## Steps







## Parallelization

P01 (discovery and decisions) runs first and gates P03 and P05, both of which
depend on its findings (the value-versus-member convention and the pure-versus-
composite field classification). P02 (Literal rollout), P04 (registry-resolver
rollout), and P06 (gate robustness) share no hard interdependency and may run in
parallel once P01 has settled. P04.S05 and P04.S06 are independent of each other.
P03.S04 re-touches files already converted in the original sweep, so it must land
after P02.S03 to avoid editing the Literal sites in two passes.

## Verification

The plan is complete when every Step is closed. Mission success criteria:

1. `test_modelo_string_usage.py` stays green with an allowlist that is the same
   size or smaller (P06 should remove the digit-membership false positive).
2. The Literal sites compile and pass strict-pydantic validation as
   `Literal[Modelo.M...]`, and the CI gate's Literal-default exclusion still
   accounts for them.
3. A single documented value-versus-member convention is applied, with no file
   mixing `Modelo.M###` and `Modelo.M###.value` for the same kind of use.
4. The amortisation and REBECA rates resolve from the registry with passing
   grounding tests, and the leaf constants remain as documented fallbacks.
5. `uv run --no-sync pytest --collect-only -q` is clean and the touched test
   surfaces are green, excluding the pre-existing peer-WIP IVA-303 failures.
6. Every `modelo: str` field is either retyped to `Modelo` or carries a one-line
   note explaining why it stays `str`.
