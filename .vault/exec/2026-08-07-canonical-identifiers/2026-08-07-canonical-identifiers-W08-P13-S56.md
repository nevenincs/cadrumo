---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7f21dc183c8f5b6487f78bd156b51c59d39768558f9b02d86fca4f8acca0db0f'
step_id: 'S56'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# add a golden-schema pinning test capturing each enumerated class's `model_json_schema()` output (the CLI envelope shape) and, for classes backing an MCP tool, the MCP `output_schema` from `_output_schema_for`, asserting the pinned constraints match the enrolled type

## Scope

- `src/cadrumo/entrypoints/mcp/tests/`

## Description

- Pin every identifier field reached from the live CLI result registry against literal constraints transcribed from the canonical aliases; expected fragments are not computed from those aliases.
- Resolve field annotations and nested Pydantic models before walking the surface, then inspect each owner model's CLI JSON schema.
- Derive each owning model's MCP command paths from the same production registry and inspect the exact field under the actual success `result` object or its `$defs` model definition.
- Keep whole-schema CLI/MCP parity for unthinned commands, but do not let thinning exclude retained identifier fields from the exact field-level MCP pin.

## Outcome

The test lives beside `_output_schema_for`, its canonical owner. It imports the CLI side through public `SCHEMA_REGISTRY`, so it adds no cross-package private dependency, duplicate schema, fake transport, or mirrored identifier business logic.

The current live inventory is 113 reachable identifier-bearing models and 221 alias-typed sites. The CLI owner-schema sweep validates every site. The MCP sweep derives every model-to-command route at runtime and validates every exact field in each actual MCP output schema. Every class is MCP-backed; none is CLI-only. This includes thinned `WorkCalculateResult` (`modelo.work.calculate`), `WorkObservationsResult` (`modelo.work.observations`), and `WorkRevisionResult` (`modelo.work.revision`). Their retained identifier fields are checked directly rather than skipped with the omitted bulk arrays.

Five focused assertions are green: all CLI field pins, the named-site regression floor, all exact MCP field pins, CLI/MCP constrained-shape parity for unthinned commands, and the AEAT CSV enforcement proof. The prior five representative MCP parameter cases were replaced by the exhaustive field-level route, not retained as a second coverage layer.

## Pinned contract

- `hex64`: `type: string`, `minLength: 64`, `maxLength: 64`, `pattern: ^[0-9a-f]{64}$`.
- `bucket_id`: `type: string`, `minLength: 1`, `maxLength: 128`.
- `profile_id`: `type: string`, `minLength: 1`, `maxLength: 36`, UUIDv4 pattern.
- `aeat_csv`: `type: string`, `minLength: 8`, `maxLength: 32`; the validation-mode pattern is deliberately absent.
- `tax_id_identity_token`: validator-only bare `type: string`.
- `aeat_expediente_id`: `type: string`, `minLength: 12`, `maxLength: 32`, leading-year-run pattern.

Nine enrolled aliases have no registered-wire field and are outside this pin until a payload adopts one: `Hex16Str`, `RegistrySnapshotId`, `ProfileLabel`, `ContentDigestOrAbsent`, `AeatCertificadoId`, `AeatClaveLiquidacion`, `AeatPresentationId`, `AeatBoxNumber`, and `SubjectTaxId`.

## Verification

- `uv run --no-sync ruff check src/cadrumo/entrypoints/mcp/tests/test_identifier_schema_contract_pin.py`: pass.
- `uv run --no-sync ty check src/cadrumo/entrypoints/mcp/tests/test_identifier_schema_contract_pin.py`: pass.
- `uv run --no-sync pytest -m integration src/cadrumo/entrypoints/mcp/tests/test_identifier_schema_contract_pin.py -q`: 5 passed.

## Notes

Literal expectations remain separate from the live alias classifier. A constraint change can leave a field classified while failing the pin it must satisfy.
