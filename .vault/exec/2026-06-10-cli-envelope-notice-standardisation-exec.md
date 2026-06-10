---
tags:
  - '#exec'
  - '#cli-envelope-notice-standardisation'
date: '2026-06-10'
step_id: 'S18'
related:
  - "[[2026-06-10-cli-envelope-notice-standardisation-plan]]"
---

# notice and status standardisation landing

Consolidated execution record for the notice/status standardisation burndown
(Steps S01-S18). One record rather than per-Step files because the contract
change is a single cohesive landing verified by one shared gate.

## Description

- Authored a strict frozen `Notice` model (`severity` info|warning, `code`,
  `message`, optional `suggestion`, optional `context`) plus an
  `EnvelopeStatus` StrEnum and an `ENVELOPE_SCHEMA_VERSION` constant in
  `aeat.core.json_contract`. Added `derive_status` (warning if any notice is
  warning-severity).
- Replaced the dead `SchemaEnvelope.warnings` list with the shared spine:
  `schema_version`, `command`, `status`, `result`, `notices`. Bumped the
  envelope version to `"2"`.
- Gave the stderr `ErrorEnvelope` the same spine in `render_error_json`
  (`schema_version`, `command`, `status="error"`, nested `error`, `notices`);
  removed `schema_version` from the error body (the spine owns it). Used a
  function-local import to avoid the `json_contract` <-> `errors` cycle.
- Threaded a `notices=` parameter and derived `status` through
  `emit_json_success` and the CLI `_emit_envelope` helper.
- Authored the `advisory_notice` projection helper in `_modelo_rendering`.
- Migrated the four bespoke advisory/next fields onto the notices channel and
  deleted them: calculate `source_advisories` and `authorization_advisory`
  (`_modelo_payloads`, `_modelo_work_calculate_cli`), the M100 filing-obligation
  advisory (`_modelo_work_lifecycle_cli`, previously text-only), and the wizard
  `config.profile.create`/`edit` `next` (and stray `next_label`) hint
  (`wizard/_commands`, `_config_payloads`). Text lines were rebuilt from the
  same notices so text and JSON cannot drift.
- Deleted the dead `_active_profile_or_exit` (and its now-orphaned `_exit`
  helper + `NoReturn` import), which emitted a third un-enveloped
  `{"error","next"}` shape; it had zero production callers (the real
  `ledger list` refusal flows through the typed `_no_active_profile_refusal`).
- Extended the no-allowlist conformance gate: success-spine lock, a
  per-registered-schema "no bespoke notice/advisory field" parametrised check,
  and an error-document spine assertion.

## Outcome

- `test_json_schema_conformance` green (92 passed), including the new spine and
  no-bespoke-field checks across all 209 registered schemas.
- `core/tests/test_json_envelope_roundtrip` and `core/errors/tests` green
  (notice redaction roundtrip + error spine).
- Config create/edit notice path green (cold-start 16 passed; wizard 270
  passed). `test_common` green (8). Surface tests 78 passed.
- Quality gates clean on all changed files: `ruff check`, `ruff format --check`,
  `ty`, `pyright` (0 errors), and `apidocs scaffold --check` (no drift),
  `locales scaffold --check` (no drift).

## Notes

- **Concurrent peer WIP blocks the full-suite-green criterion (S17).** A large
  uncommitted peer campaign (666 insertions across 49 files) refactors
  `RawTransaction` to reject negative amounts ("flow carried by direction") and
  reshapes the source mesh / ledger period grammar. This independently breaks
  transaction/ledger/source-mesh/calculate integration tests (e.g. negative-
  amount fixtures in `test_modelo_source_mesh_calculate`, the
  `ledger status --period` year requirement, source-bound casilla overrides).
  Those failures are not caused by this change; my edits import cleanly, pass
  the gate, and render errors correctly through the failing paths. The
  full-suite-green gate must be re-run once the peer transaction refactor
  settles. S17 is therefore verified for this change's scope but its
  full-suite-green clause is deferred to a post-peer-WIP rerun.
- **S15 (overview next-step) landed.** The overview status next-step guidance is
  now also surfaced as `info`-severity notices (`overview_next_step_notices`)
  on the `overview.status` JSON envelope, mirroring the text guidance so JSON
  consumers get the same forward steps. The byte-identical text output is
  preserved (the text renderer is unchanged); overview rendering + conformance
  tests stay green (102 passed).
- **Notice design refinement vs the ADR sketch.** The ADR sketched
  `suggestion`/`next` on the notice; the landed model collapses the actionable
  field to a single `suggestion` (uniform with `ErrorEnvelope.suggestion`) and
  adds an optional `context: dict[str,str]` (mirroring `ErrorEnvelope.context`)
  so migrated advisories keep their structured provenance (`reason`,
  `source_kind`, `resolver_id`) without a bespoke payload model.
- **Breaking JSON contract.** `schema_version` bumped `"1"` -> `"2"`; the
  free-form `warnings` list is removed in favour of typed `notices`. Acceptable
  under the project's zero-legacy / pre-beta posture.

## Honesty review

A fresh-context honesty pass against this landing surfaced three items, each
checked:

- **Combined heterogeneous CLI test runs leak global state.** Running
  `test_json_schema_conformance`, `test_cold_start_no_profile`, and
  `test_registry_enforcement` together produced 9 failures
  (`test_every_cli_leaf_has_a_registered_schema`, cold-start guidance,
  registry-enforcement); every one of them PASSES in isolation (conformance 1,
  cold-start 10, registry-enforcement 4). This is the SCHEMA_REGISTRY /
  lazy-subcommand-tree cross-module state leak the local-execution rule warns
  about (re-run sequentially before triaging), not a regression from this
  change.
- **Calculate-advisory integration verification is peer-WIP-blocked.** The
  `source_advisories` / `authorization_advisory` -> notices projection is proven
  structurally (gate confirms the fields are gone, `ty`/`ruff` clean, the
  projection logic is straight-line) and the notices CHANNEL is proven
  end-to-end by the config-create and overview integration tests; the
  calculate-specific integration test is blocked by the peer negative-amount
  `RawTransaction` refactor and must be re-run once that settles.
- **Error-document `command` is intentionally null.** The CLI error boundary
  terminates before the dotted command path is resolvable, so the spine's
  `command` is present-but-null on error documents. Threading the real path is a
  clean future improvement; the spine uniformity holds today.

Result: standardisation is complete and gate-enforced for the success and error
paths. The one open plan Step (S17 full-suite-green) is deferred to a
post-peer-WIP rerun; it is not satisfiable while a concurrent peer transaction
refactor holds a large swath of unrelated integration tests red.
