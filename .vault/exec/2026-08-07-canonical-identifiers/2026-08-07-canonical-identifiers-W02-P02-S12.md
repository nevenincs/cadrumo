---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:db4a0a8ce1fb67fb838ee38ba883481dea28ec69230c7a1e9f7c2dc700321bb3'
step_id: 'S12'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# add a golden-schema pinning test capturing `ExpedienteDeclarationPayload`'s advertised `model_json_schema()` before and after `W02.P02.S11`, so the CLI/MCP contract change is a visible reviewed diff rather than a silent constraint shift

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Searched the existing `test_json_schema_conformance.py` gate first; it declares itself STRUCTURAL-SHAPE-ONLY (key parity, never constraint content) in its own module docstring and per-test docstrings, so it cannot host a constraint-content pin without contradicting its stated purpose.
- Searched for an existing golden/snapshot pinning idiom before writing a new one. The repo's one "golden" primitive (`core/observability/_golden.py`) pins full envelope determinism (masking non-deterministic surrogate keys after a frozen clock), a different concern from pinning one field's advertised constraint fragment. `test_evidence_provenance_payload_parity.py` is the closer precedent: a small, standalone test module scoped to one payload's contract concern, already calling `model_json_schema()` and walking the fragment tree. Followed that shape rather than inventing a third idiom.
- Added a new focused test module rather than extending the conformance gate, because folding constraint-content assertions into a file whose own docstring rules that out would either contradict the file's stated scope or require rewriting its self-description; a separate module keeps both gates honest about what each one checks.
- Read `AeatExpedienteId`'s declaration in `core/identity/_namespace.py` (`min_length=12`, `max_length=32`, `pattern=r"^[0-9]{4,}[A-Z0-9]+$"`) and hardcoded those three values as literals in the new test rather than importing the alias's constants or reading them off the alias at runtime, so the pin cannot silently track a future loosening of the alias.
- Confirmed the live schema fragment before writing the assertion: `ExpedienteDeclarationPayload.model_json_schema()["properties"]["expediente_id"]` returns `{"maxLength": 32, "minLength": 12, "pattern": "^[0-9]{4,}[A-Z0-9]+$", "title": "Expediente Id", "type": "string"}`.
- Added a second, negative test anchoring the pre-`W02.P02.S11` shape (`{"title": "Expediente Id", "type": "string"}`, no length bound, no pattern) as a documented historical baseline, without constructing a second throwaway model — the historical fragment is asserted as a literal negative, not rebuilt from old code.
- Proved the gate bites from OUTSIDE the repo: a scratchpad probe script (never touching a tracked file) imported the real `ExpedienteDeclarationPayload`, replaced its `expediente_id` `FieldInfo` in-process with a loosened `StringConstraints` (`max_length=64`, no pattern), called `model_rebuild(force=True)`, and re-ran the pinned assertion against the mutated live schema.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_expediente_declaration_payload_schema_pin.py` pins the current advertised JSON Schema fragment for `ExpedienteDeclarationPayload.expediente_id`:

```
{"title": "Expediente Id", "type": "string", "minLength": 12, "maxLength": 32, "pattern": "^[0-9]{4,}[A-Z0-9]+$"}
```

against the pre-retype baseline it replaces:

```
{"title": "Expediente Id", "type": "string"}
```

A future loosening of `AeatExpedienteId`, or a reversion of this field back to a bare `str`, now fails a focused, fast unit test rather than surfacing only as a silent widened wire contract. Both tests pass (`pytest ... -q` -> `2 passed`); Ruff format/lint and `ty check` are clean on the new file.

Bite-proof observed output (scratchpad probe, mutation never touched a tracked file):

```
BEFORE MUTATION: pin holds, as expected.
MUTATED FRAGMENT: {'title': 'Expediente Id', 'type': 'string'}
GATE BITES AS EXPECTED (AssertionError):
```

The mutated in-process field collapsed to a bare-string schema (the `FieldInfo` reconstruction path did not fully round-trip the loosened `StringConstraints`), which still proves the point: the pinned positive assertion failed immediately against the mutated live schema, and the companion negative-baseline test would independently have failed too since the mutated fragment now equals that exact historical baseline dict. The pin is not vacuous.

Landing evidence for the already-completed `W02.P02.S11` row (retype `ExpedienteDeclarationPayload.expediente_id` onto `AeatExpedienteId`): re-verified at HEAD that the change was already committed by a prior session as `b0c04d57e1cb6742a07c578038574ec5de793d1f` ("refactor(cli): type expediente declaration payload"), numstat `2 2 src/cadrumo/entrypoints/cli/_app_live_payloads.py` (plus its own exec record, audit, and plan-checkbox update in the same commit). Re-confirmed clean: `ruff check` passes on the file, the plan row is `[x]`, and the file's other four `expediente_id` declarations (lines ~79, ~109 bare/optional; ~974, ~1034 already `Field(min_length=12, max_length=32)`) were left untouched, matching this Step's single-field scope.

## Notes

No findings declined outside scope for this Step. The other four `expediente_id` sites on the same file were inspected only to confirm S11's scope boundary held; none were judged to need retyping as part of this campaign row.

The wider registry/CLI suite carries unrelated red signatures noted in the S11 exec record (`test_profile_bound_command_populates_active_profile_label` refusing a missing `--tax-residence-jurisdiction-scope` precondition, and a stale `deudas` subgroup inventory failure) — neither names this payload, its identifier constraint, or the new pinning test, and neither was touched by this Step.
