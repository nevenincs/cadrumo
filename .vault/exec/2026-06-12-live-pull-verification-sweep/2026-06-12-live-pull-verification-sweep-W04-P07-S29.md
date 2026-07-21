---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-13'
step_id: 'S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W04.P07.S29 Cross-Period Filed-History Reference Locking

Scope: local cross-period clean-state hardening for Modelo filing records, filed-history observations, parsed justificante metadata, and member fan-in evidence.

## Description

- Pass member-specific source kind and source metadata into cross-period filing-history evaluation.
- Compare optional filed-history `aeat_justificante_csv` metadata to the parsed justificante CSV backing the current Modelo filing record.
- Thread parsed filed-history justificante CSVs from single, bulk, and source filed pulls into calculation-observation source metadata.
- Compare optional filed-history `aeat_expediente_id` metadata to parsed justificante `presentation_id` only when the parsed receipt exposes that presentation id.
- Refuse filed-history justificante metadata persistence and Modelo filing stamping when a parsed receipt presentation id disagrees with the filed-register expediente id.
- Enforce plural filed-history `aeat_justificante_csvs` metadata in clean-state instead of letting ambiguous multi-CSV metadata bypass the reference lock.
- Preserve the existing model, year, typed `Period`, taxpayer identity, AEAT acceptance, calculation revision, and verification gates.
- Add real-behavior regressions for mismatched filed-history justificante CSV, plural CSV metadata, mismatched presentation id, matching optional CSV metadata, metadata threading from latest filed observations, and full clean-state verdict refusal.
- Tighten the active plan tracking for CLI verb drift (`pull` only, no `pull-all`) and for Modelo 036/censo-derived calendar reconciliation using typed `core.Period` identities and justificante-backed AEAT filing evidence.
- Add a first-class calendar `verified_justificante_csv` audit reference so entries and filing events can only report `justificante_verified=true` when the verified receipt CSV is also exposed.
- Promote `aeat_sede_justificante` calculation observations from `submitted_observed` to `justificante_verified` only when their single or plural filed-history CSV metadata resolves to matching persisted justificante metadata for the same model, typed period, filing year, and taxpayer.
- Resolve code-review finding: avoid false `filing.aeat_evidence_conflict` warnings when one source names the same verified receipt by justificante CSV and another source names the expediente id; conflicting verified CSVs still remain conflicts.

## Outcome

Focused local gates passed:

- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_live_capture_evidence_rejects_mismatched_filed_history_justificante_csv src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_live_capture_evidence_rejects_mismatched_filed_history_presentation_id src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_cross_period_clean_state_accepts_matching_filed_history_justificante_csv_provenance src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_cross_period_clean_state_blocks_filed_history_justificante_csv_mismatch -q`
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q`
- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q`
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q`
- `uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q`
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
- `uv run pytest src/aeat/core/tests/test_json_envelope_roundtrip.py src/aeat/core/tests/test_output_rendering.py -q`
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q`
- `uv run ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`
- `uv run ruff check src/aeat/application/live/_filed_data_capture.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/_calendar_models.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_overview_payloads.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q`
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q` selected the application calendar filing evidence tests under default marker filtering: 40 passed, 19 CLI integration tests deselected.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q`

## Notes

RAG discovery was attempted first with a 300 second timeout and returned `http_search_timeout`; a later high-timeout RAG query for filed observation source metadata returned code hits in `_cross_period_clean_state.py` and related tests, and exact `rg` discovery was used for the scoped implementation.

Positive authenticated censo, filed-history, justificante, and calendar aggregation remain open for this S29 slice. A fresh isolated live root created on 2026-06-13 proved profile creation and Cl@ve provider configuration with identity alignment, but `config auth login --provider clave_movil --fresh --reset-lock` timed out waiting for operator-mediated Cl@ve approval, so downstream censo/filed/notification pulls did not acquire live evidence in that attempt.

## 2026-06-13 Continuation

RAG discovery was rerun with `vaultspec-rag search --timeout 300` before this continuation. The highest-score vault/code cluster pointed back to the calendar CSV-register justificante guard, Modelo external import evidence, and the known requirement that `pull` remains the only live acquisition verb.

The Modelo external import and downstream clean-state/calendar behavior were rechecked against the current, drifted worktree:

- `AEAT_CSV_REGISTER` imports can still record AEAT acceptance as observed external baseline evidence, but the calendar strict-mode gate refuses them as `filing.justificante_unverified` unless a matching persisted taxpayer-bound justificante exists.
- Modelo 390 cross-period clean-state still refuses CSV-register prior filings without justificante verification via `missing_justificante_verification`.
- `AEAT_JUSTIFICANTE_PDF` and `AEAT_LIVE_CAPTURE` import paths still require persisted justificante metadata bound to model, filing year, typed `core.Period`, and expected taxpayer identity.
- CLI help for filed, censo, justificante, and notifications exposes `pull`; `pull-all` remains unregistered in production command help.

An isolated live profile/password run was created under `var/live-auth-sweep-20260613` to avoid unlocking the unknown shared default profile. Local setup succeeded:

- `config profile create codex-live-20260613 ... --quiet --accept-defaults` exited 0 with the configured Cl@ve identity as the profile tax id.
- `config auth configure --provider clave_movil` exited 0 with `profile_tax_id=present`, `clave_identity=present`, and `identity_alignment=matches`.
- `config profile status` exited 0 for the isolated profile, with the tax id redacted to a fingerprint.

Authenticated live access still did not complete:

- `config auth login --provider clave_movil --fresh --reset-lock` in headless non-QR mode timed out at AEAT Cl@ve request diagnostic `20260613T061642Z`.
- The same login in visible non-QR mode timed out at diagnostic `20260613T061921Z`.
- Visible QR mode timed out at diagnostic `20260613T062143Z`.
- `config auth status --provider clave_movil` then reported `configured=True`, `authenticated=False`, and health summary "operator-mediated Cl@ve completion required".
- `config auth diagnostics report 20260613T062143Z --phone-state operator_did_not_check` recorded the observed operator-state uncertainty for the latest attempt.

No positive live censo/Modelo 036, filed-history, justificante, notifications, or live-backed calendar aggregation evidence is claimed from this continuation. The open live blocker remains operator-mediated Cl@ve approval not completing inside AEAT's 120 second request window, despite the isolated profile/password creation flow and identity-aligned Cl@ve configuration working.

## 2026-06-13 Cross-Period Expediente/CSV Lock

RAG discovery was rerun with:

- `vaultspec-rag search --type code --port 8766 --max-results 12 --timeout 300 "calendar modelo filing justificante AEAT accepted evidence bypass"`
- `vaultspec-rag search --type vault --port 8766 --max-results 12 --timeout 300 "justificante enrolment calendar modelo filing AEAT state cross period"`

The next weak proof path was in cross-period clean-state reference comparison.
Filed-history observations always carry AEAT register status, expediente id, and
authenticated identity, but only carry `aeat_justificante_csv` or
`aeat_justificante_csvs` after a matching justificante artefact has been parsed.
Before this slice, an expediente id could be present while the parsed
justificante had no comparable `presentation_id`; that was treated as
non-comparable rather than as an unresolved reconciliation reference.

The clean-state gate now fails closed when filed-history metadata carries an
`aeat_expediente_id` and the persisted justificante has neither a matching
`presentation_id` nor a matching filed-history justificante CSV reference. Clean
positive fixtures were updated to carry the same `aeat_justificante_csv` that
the production filed-history persistence path stores after parsing a receipt.

Focused gates passed:

- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q`
  passed 38 tests.
- `uv run ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`
  passed.
- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py -q`
  passed 23 tests.
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 42 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 40 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  passed 19 tests.
- `uv run ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  passed.

This remains local/backend proof only. It does not close the live Modelo
036/censo/filed-history/justificante/calendar acceptance gap because the fresh
Cl@ve run above still failed to acquire an authenticated AEAT session.

## 2026-06-13 Notification Calendar Taxpayer Scope and Pull Verb Recheck

RAG discovery was rerun with:

- `vaultspec-rag search --type code --port 8766 --max-results 16 --timeout 300 "AEAT notifications messages calendar filing justificante overview events"`
- `vaultspec-rag search --type vault --port 8766 --max-results 16 --timeout 300 "messages notifications calendar AEAT filing justificante enrolment"`
- `vaultspec-rag search --type code --port 8766 --max-results 16 --timeout 300 "CLI pull pull-all live filing history calendar Period"`

The notification calendar projection now applies the same expected-taxpayer
scope as expediente-derived calendar events. AEAT notification/message
snapshots still project as `message` calendar events and do not become Modelo
filing evidence, but rows whose `titular_nif` or `destinatario_nif` do not
match the active profile tax id are omitted from the profile calendar.

The CLI verb drift check was repeated after the typed `core.Period` backend
changes. Active source and how-to documentation keep bulk filed-history reads
under `app live filed pull`; `pull-all` appears only in negative command-tree
guard tests and historical vault records.

Focused gates passed:

- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q`
  passed 43 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  passed 19 tests.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
  passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py::test_live_filed_bulk_pull_text_reports_failures_without_pull_all -q`
  passed 4 tests.
- `rg -n "pull-all|pull_all" src/aeat/entrypoints src/aeat/application src/aeat/domain src/aeat/locales docs/how-to`
  found only negative test assertions and helper names, not production command
  registrations, locale strings, or how-to commands.

This remains local/backend proof only. It strengthens profile-scoped message
calendar aggregation and the `pull`-only command contract, but it still does not
claim positive authenticated Modelo 036/censo, filed-history, justificante, or
live-backed calendar evidence because the current AEAT session has not been
authenticated.

## 2026-06-13 Live Auth Reattempt

The user indicated readiness to authenticate, so a new read-only live-auth
attempt was made after the local gates:

- The prior passphrase candidate `horatio` was tested against the isolated
  `var/live-auth-sweep-20260613` root and refused before storage access with
  `REFUSED_STORAGE_PASSPHRASE_TOO_SHORT`; the CLI requires at least eight
  characters.
- The current process had no `AEAT_CLAVE_MOVIL_DNI_NIE`,
  `AEAT_CLAVE_MOVIL_DNI_FECHA`, or `AEAT_CLAVE_MOVIL_NIE_SOPORTE` environment
  variables, so a brand-new non-interactive real Cl@ve profile could not be
  created from flags alone.
- A visible read-only runner was launched from
  `var/aeat/live-auth-run/run-live-auth.ps1` with
  `AEAT_BROWSER_HEADLESS=false`, `AEAT_OUTPUT_LANGUAGE=en`,
  `AEAT_LIVE_TESTS_ENABLED=1`, and `AEAT_CLAVE_PREFER_NON_QR=true`.
- The runner stayed alive but did not create its redacted log after repeated
  checks, which means it did not reach `config auth status`, AEAT Cl@ve,
  censo pull, filed pull, notifications pull, or calendar projection. It was
  stopped as an idle passphrase prompt.

No positive live evidence is claimed from this reattempt. The next live pass
needs an operator-entered secure-storage passphrase of at least eight
characters and either an existing configured profile unlocked with that
passphrase or Cl@ve identity settings available to create/configure a fresh
profile.

## 2026-06-13 Notification Snapshot Authenticated Identity Lock

RAG discovery was rerun with:

- `vaultspec-rag search --type code --port 8766 --max-results 16 --timeout 300 "notifications authenticated_identity calendar taxpayer profile AEAT messages"`
- `vaultspec-rag search --type vault --port 8766 --max-results 16 --timeout 300 "notifications authenticated identity calendar taxpayer scope live pull verification sweep"`

The next integration gap was that live notifications had row-level taxpayer
fields but did not persist the authenticated AEAT session identity on the
snapshot. Expedientes already persisted this identity, so profile calendar
projection could reject wrong-taxpayer expediente snapshots before deriving
filing events; notifications only had row-level filtering.

The notifications live capture now passes `session.identity_nif` into
`NotificationsService.capture`. The persisted notification snapshot stores a
normalised `authenticated_identity`, and new live captures include that
identity in the content-addressed snapshot id. Existing snapshots without the
field remain readable and keep the old id derivation.

Calendar projection now applies a snapshot-level authenticated-identity gate
for notification snapshots that carry the field, then still checks explicit
row-level taxpayer ids so a representative or mixed mailbox row for another
taxpayer cannot leak into the active profile calendar. Older snapshots without
the field continue to use row-level filtering.

Focused gates passed:

- `uv run pytest src/aeat/application/live/tests/test_notifications.py -q`
  passed 18 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py -q`
  passed 44 tests.
- `uv run ruff check src/aeat/application/live/_notifications.py src/aeat/application/live/__init__.py src/aeat/application/live/tests/test_notifications.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py`
  passed.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  passed 19 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 40 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q`
  passed 81 tests and rechecked the `pull`-only/no-`pull-all` command tree.

This is still local/backend proof. It improves the authenticated live
notification-to-calendar chain, but no positive AEAT live notification pull or
live-backed calendar aggregation is claimed without a completed authenticated
session.

## 2026-06-13 Direct Justificante Snapshot CSV Lock

RAG discovery was rerun with:

- `vaultspec-rag search --type code --port 8766 --max-results 20 --timeout 300 "register_capture_as_filing_evidence justificante filing record AEAT filed state calendar cross period"`
- `vaultspec-rag search --type vault --port 8766 --max-results 20 --timeout 300 "direct justificante stamp filing evidence filed history AEAT state cross period"`

The next direct stamping weakness was in `register_capture_as_filing_evidence`.
The path parsed the official receipt bytes but then overwrote the parsed
justificante CSV with `snapshot.csv` before saving metadata and stamping the
Modelo filing record. A persisted or mutated snapshot whose CSV metadata did
not match the actual receipt bytes could therefore stamp a filing with the
wrong AEAT evidence reference.

The direct live-capture stamping path now requires the parsed receipt CSV to
match the live snapshot CSV before it saves `JustificanteRepository` metadata,
marks `aeat_accepted`, attaches `AEAT_LIVE_CAPTURE` evidence, or emits the
`MODELO_LIVE_EVIDENCE_STAMPED` event. The existing model, filing year, typed
`core.Period`, taxpayer identity, active-snapshot, and existing-evidence
conflict checks remain in force. No expediente/presentation-id equality rule
was added because the current official fixture shows AEAT's expediente id and
receipt presentation id are different identifiers in this direct capture path.

Focused gates passed:

- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 19 tests.

Vault and command drift checks after the review fixes:

- `vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md`
  passed.
- `vaultspec-core vault feature index -f live-pull-verification-sweep` rebuilt
  `.vault/index/live-pull-verification-sweep.index.md`.
- `vaultspec-core vault check all --feature live-pull-verification-sweep`
  still reported 47 structure errors from pre-existing non-standard exec
  filenames and one no-ADR warning for this feature. Frontmatter,
  modified-stamp, annotations, links, dangling, body-links, orphans,
  references, schema, and rename-integrity all reported clean. No vault repair
  or file rename was attempted in the shared worktree.
- `rg -n "pull-all|pull_all" src/aeat/entrypoints src/aeat/application src/aeat/domain src/aeat/locales docs/how-to`
  found only negative guard tests.
- `uv run aeat app live filed pull-all --help` failed with
  `No such command 'pull-all'. Did you mean 'pull'?`.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q`
  passed 38 tests.
- `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`
  passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 40 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py -q`
  passed 49 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q`
  passed 19 tests.

This is local/backend proof. It closes a direct metadata-substitution bypass
for live justificante stamping, but still does not claim live AEAT censo,
filed-history, justificante, or calendar aggregation without a completed
authenticated session.

## 2026-06-13 Period Boundary and Pull-Verb Drift Recheck

RAG discovery was rerun with high timeouts before this continuation:

- `vaultspec-rag search --type code --port 8766 --max-results 24 --timeout 300 "pull-all pull command live filed censo calendar CLI acquisition verb Period typed"`
- `vaultspec-rag search --type vault --port 8766 --max-results 24 --timeout 300 "live pull verification sweep W03 P05 S18 pull-all Period calendar censo filed justificante"`

Two sidecar codebase analysis agents checked the exact risks the user called
out: one audited `pull` versus `pull-all` and stale acquisition verbs, and one
audited the newly strong-typed `core.Period` boundary in calendar and live
filing evidence. The findings were actionable:

- Live filed acquisition still exposes `pull` and `pull-sources`; no production
  `pull-all` command is registered. The active plan correctly leaves
  `W03.P05.S18` open because positive authenticated filed list/pull/source-pull
  proof is still missing, even though the local `pull`/no-`pull-all` drift guard
  is green.
- The overview calendar models serialized typed `Period` values as display
  strings but did not hydrate those strings on JSON reload, making
  period-bearing calendar models fail their own strict JSON round trip.
- The registry observation boundary allowed a typed `filing_period` to coexist
  with a divergent display-form `period` string when the string could not be
  parsed as a bare registry token.
- Live justificante `list` and `view` emitted `str(period)` at a CLI boundary
  that already carries `filing_year`, so the visible period became `2026 1T`
  instead of the operator token `1T`.

Implementation completed:

- Added matching `field_validator` hydration for every period-bearing overview
  calendar model that serializes a `Period` to the canonical display string, so
  `model_validate_json(model_dump_json())` preserves the typed Period value.
- Made the calculation-observation filing-evidence bridge prefer a typed
  `filing_period` when present and ignore legacy unparsable period strings
  instead of crashing the calendar.
- Tightened `RegistryModeloObservation` so `filing_period.registry_token` must
  match the legacy `period` token exactly; display strings such as `2025 1T`
  are now rejected when paired with a typed period.
- Changed live justificante `pull`, `list`, and `view` payload/text output to
  emit `period.registry_token` at the CLI boundary.
- Added negative CLI regressions proving `aeat config profile censo refresh`
  and `aeat app live justificante capture` remain unregistered.

Focused gates passed:

- `uv run pytest src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py::test_registry_filing_observation_preserves_observation_tuple src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py::test_registry_filing_observation_refuses_display_period_drift -q`
  passed 2 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_period_bearing_calendar_models_roundtrip_through_json src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_event_refuses_contradictory_justificante_state -q`
  passed 2 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_censo_help_lists_four_verbs src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_censo_refresh_command_is_not_registered -q`
  passed 6 tests.
- `uv run ruff check src/aeat/application/overview/_calendar_models.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/overview/tests/test_calendar.py -q`
  passed 85 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_list_payload_and_text_use_registry_period_tokens -q`
  passed 39 tests.
- `uv run pytest src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py -q`
  passed 13 tests.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 19 tests.

Live authenticated proof remains blocked in this Codex command session:

- `uv run aeat config profile status` failed before profile inspection with
  `AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive`.
- The current process exposes no `AEAT_*` environment variables, so no
  passphrase, existing profile unlock, Cl@ve identity, censo pull, filed pull,
  justificante pull, notifications pull, or live-backed calendar aggregation
  could be executed from this non-interactive shell.

The relevant authenticated-live rows remain open. This pass only claims local
hardening and regression proof for typed `core.Period` consistency, pull-only
CLI drift, and calendar/justificante output boundaries.

## 2026-06-13 Review Fixes for Period Boundary Recheck

The mandatory code-review pass found two real issues in the period-boundary
continuation:

- `RegistryModeloObservation` still accepted display-form `period` values such
  as `2025 1T` when `filing_period` was omitted, because hydration failure
  fell back to the original data and left `filing_period=None`.
- Calendar evidence merging could falsely mark a conflict when local
  `AEAT_LIVE_CAPTURE` evidence used the receipt CSV as its reference and
  filed-history evidence used the expediente id as its AEAT reference while
  verifying the same justificante CSV.

Both findings were fixed before this step was considered complete:

- Registry observation hydration now raises `RegistryValidationError` when the
  legacy `period` field is not a bare registry token, even if no typed
  `filing_period` was supplied.
- Calendar conflict detection now treats one side's AEAT reference matching the
  other side's verified justificante CSV as the same receipt, while retaining
  the warning for genuinely different local and filed-history references.

Review-fix gates passed:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_entry_warns_when_local_and_filed_history_aeat_references_disagree src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_does_not_conflict_live_capture_csv_with_matching_filed_history_csv src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_does_not_conflict_matching_verified_csv_across_reference_namespaces -q`
  passed 3 tests.
- `uv run pytest src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py::test_registry_filing_observation_refuses_display_period_drift src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py::test_registry_filing_observation_refuses_bare_display_period_drift src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py::test_registry_filing_observation_preserves_observation_tuple -q`
  passed 3 tests.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py src/aeat/application/overview/_calendar_models.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/overview/tests/test_calendar.py src/aeat/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py -q`
  passed 100 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_list_payload_and_text_use_registry_period_tokens -q`
  passed 39 tests.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 19 tests.

## 2026-06-13 Cross-Period Verified-State and Reconcile Hardening

RAG discovery was rerun with a high timeout before this continuation:

- `vaultspec-rag search --type code --port 8766 --max-results 30 --timeout 300 "cross period clean state justificante AEAT filing evidence calendar Modelo filing record lock submitted accepted verified"`
- `vaultspec-rag search --type vault --port 8766 --max-results 30 --timeout 300 "justificante enrollment calendar modelo filing system cross period filing locked AEAT state evidence conflict missing verification"`

Sidecar review identified three remaining risks in the local backend boundary:

- `mark_revision_verificado_completo` could directly promote a cross-period
  draft revision to `VERIFICADO_COMPLETO` without using the verification path
  that evaluates cross-period clean-state.
- Official observation kinds other than `aeat_sede_justificante` skipped the
  AEAT register `ALTA` and authenticated-identity provenance checks.
- Modelo justificante reconcile could report `matches` when modelo and year
  aligned but period or taxpayer identity differed.

Implementation completed:

- Direct `mark_revision_verificado_completo` now loads the target work unit,
  resolves its law-determined registry snapshot, and refuses direct promotion
  when that snapshot declares cross-period dependencies. Cross-period periods
  must use the production `verify_modelo_revision` path so clean-state,
  justificante, and AEAT evidence gates run before local verified state is
  granted.
- `_aeat_register_provenance_blockers` now applies the same `ALTA` and
  authenticated-identity checks to every official observed-state source kind
  in `_OFFICIAL_SOURCE_KINDS`, not only `aeat_sede_justificante`.
- Modelo reconcile now compares typed `Period` and active-profile taxpayer id
  against the parsed justificante before emitting a `matches` verdict.
- Existing file/export/import tests that used the direct mark helper for
  cross-period Modelo 130/303 scenarios were updated to use real
  `verify_modelo_revision` flows or a non-cross-period Modelo 111 fixture when
  the test is specifically about direct state-transition semantics.

Focused gates passed:

- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q`
  passed 53 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_import_flow.py -q`
  passed 59 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_reconcile.py src/aeat/application/modelo/tests/test_reconciliation_history.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 33 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_reconcile.py src/aeat/application/modelo/tests/test_reconciliation_history.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 145 tests.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_list_payload_and_text_use_registry_period_tokens -q`
  passed 125 tests.
- `uv run ruff check src/aeat/application/modelo/_calculation_actions.py src/aeat/application/modelo/_reconcile.py src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_reconcile.py src/aeat/application/modelo/tests/test_reconciliation_history.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py`
  passed.

Pull-only CLI drift was rechecked:

- `uv run aeat app live filed pull --help` succeeded and exposed the filed
  acquisition command as `pull`.
- `uv run aeat app live filed pull-all --help` failed with `No such command
  'pull-all'. Did you mean 'pull'?`
- `rg -n "pull-all|pull_all" src/aeat/entrypoints src/aeat/application src/aeat/domain src/aeat/locales docs/how-to`
  found `pull-all` only in negative guard tests.

Live authenticated proof remains open:

- `AEAT_SECRET_PASSPHRASE` is not present in the process environment.
- The current active profile did not unlock with the development/test database
  password or `horatio2026`.
- `horatio` is rejected by policy because it is shorter than the NIST
  passphrase minimum.
- No fresh authenticated live profile could be created from this shell because
  the required real taxpayer identity and AEAT authentication handoff were not
  completed inside the non-interactive command session.

The authenticated censo Modelo 036, filed-history, justificante, notifications,
and live-backed calendar rows remain open. This wave closes local/backend
verified-state, official-provenance, reconcile-period, reconcile-taxpayer, and
pull-only command drift gaps only.

## 2026-06-13 Calendar Official Calculation-Observation Source Alignment

RAG discovery was rerun with a high timeout after the typed `core.Period`
stringification work landed:

- `vaultspec-rag search --type code --port 8766 --max-results 30 --timeout 300 "core Period typed calendar modelo obligation filing history justificante pull AEAT live profile censo"`
- `vaultspec-rag search --type code --port 8766 --max-results 30 --timeout 300 "calendar local ready to file AEAT submitted justificante verified distinct state modelo filing evidence"`

The recheck confirmed that overview calendar models now carry typed `Period`
values internally, serialize only at the CLI/API boundary, and expose separate
local and AEAT filing axes:

- `local_filing_state` for the application's "verified and ready to file"
  meaning of a Modelo filing record.
- `aeat_submission_state`, `justificante_verified`, and
  `verified_justificante_csv` for real-world AEAT submission/receipt evidence.

Implementation completed in this slice:

- `calendar_filing_evidence_from_sources` now treats the same official
  calculation-observation source kinds as the cross-period clean-state verifier:
  `aeat_sede_justificante`, `aeat_sede_live_capture`, and `aeat_csv_register`.
- Live-capture and CSV-register calculation observations with `ALTA` register
  metadata and matching authenticated identity now become calendar
  `submitted_observed` AEAT evidence.
- Those sources still do not become `justificante_verified` unless their
  metadata resolves to a persisted justificante whose CSV, modelo, filing year,
  typed `Period`, and taxpayer id match.

Focused gates passed:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 45 tests.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py`
  passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q`
  passed 111 tests.

Pull-only CLI drift was rechecked again:

- `uv run aeat app live filed pull --help` succeeded and exposes the acquisition
  verb as `pull`.
- `uv run aeat app live filed pull-all --help` failed with `No such command
  'pull-all'. Did you mean 'pull'?`
- `rg -n "pull-all|pull_all" src/aeat/entrypoints src/aeat/application src/aeat/domain docs/how-to`
  found only negative guard tests.

Live authenticated proof remains open:

- `uv run aeat config profile status --output-language en`,
  `uv run aeat config auth providers --output-language en`, and
  `uv run aeat config auth status --output-language en` all refused before
  profile inspection because `AEAT_SECRET_PASSPHRASE` is not set and stdin is
  not interactive.
- The configured development/test passphrase was tried without logging it; the
  existing default store refused it with `La frase de contrasena no abre la
  clave maestra`.
- An isolated interactive `profile create` attempt was launched against
  `var/live-auth-20260613`, but the process ran headless inside this Codex
  command channel, remained stuck at wizard step 1, wrote only
  `var/live-auth-20260613/logs/aeat.log`, and created no profile store. The
  orphaned `uv`/`aeat`/`python` process tree was stopped, and the scratch
  `var/live-auth-20260613` directory was removed after verifying it resolved
  inside the workspace.

The authenticated censo Modelo 036, filed-history, justificante, notifications,
and live-backed calendar rows therefore remain open. This continuation closes
only the local calendar evidence alignment between official observed
calculation sources and the AEAT submission axis.

## 2026-06-13 CSV Register Justificante-Bound Clean-State Gate

Workspace-targeted RAG discovery was rerun after the daemon recovered and the
typed `core.Period` stringification work landed:

- `vaultspec-rag -t . search --type code --port 8766 --max-results 30 --timeout 300 "core Period typed modelo calendar filing history justificante Period contains canonical period stringification"`
- `vaultspec-rag -t . search --type code --port 8766 --max-results 30 --timeout 300 "AEAT_CSV_REGISTER justificante bound import cross period clean state missing external evidence record live filed same CSV conflict"`
- `vaultspec-rag -t . search --type vault --port 8766 --max-results 30 --timeout 300 "justificante enrollment calendar modelo filing system cross period filing locked AEAT state evidence conflict missing verification pull only"`

The code searches resolved the active seam back to filed-observation
persistence and its regression tests. The vault query returned no matching
results, so source discovery continued with `rg` and focused file reads.

Implementation completed:

- `AEAT_CSV_REGISTER` imports now require the same persisted justificante
  binding as justificante-PDF and live-capture evidence before import can stamp
  a filing as AEAT accepted.
- Cross-period clean-state now treats CSV-register evidence as filing-grade
  only after matching justificante metadata has been enrolled, including CSV,
  modelo, filing year, typed `Period`, and taxpayer identity checks.
- Filed-history justificante enrollment now recognises existing CSV-register
  evidence for the same CSV as already verified, with case-insensitive CSV
  comparison, instead of reporting a false conflict.
- The affected Period boundary was rechecked: comparisons remain typed
  `Period` comparisons, while registry-token stringification is limited to
  sorting, event payloads, metadata keys, and CLI/API boundaries.

Code review completed:

- Reviewer Russell reported `CSVREG-001`, a medium severity filed-history
  enrollment bug where same-CSV `AEAT_CSV_REGISTER` evidence was compared
  case-sensitively.
- The finding was fixed by normalising both CSV references to uppercase in the
  existing-evidence comparison and adding a live filed-history regression that
  keeps lowercase existing CSV-register evidence for a matching parsed receipt.

Focused gates passed:

- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_clears_with_matching_justificante_metadata src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_without_enrolled_justificante_still_blocks src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py::test_cross_period_clean_state_blocks_csv_register_without_justificante_verification src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py::test_cross_period_clean_state_accepts_csv_register_with_matching_justificante_metadata src/aeat/application/modelo/tests/test_import_flow.py::test_import_supersedes_prior_current_filing src/aeat/application/modelo/tests/test_import_flow.py::test_import_csv_register_refuses_without_enrolled_justificante src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py::test_verify_modelo_390_refuses_csv_register_prior_filing_without_justificante -q`
  passed 7 tests.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 143 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_reconcile.py src/aeat/application/modelo/tests/test_reconciliation_history.py -q`
  passed 61 tests.
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q`
  passed 45 tests.
- `uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_keeps_existing_csv_register_evidence_for_same_csv_case_insensitive src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_keeps_existing_justificante_pdf_evidence_for_same_csv src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_reports_existing_evidence_conflict_without_overwrite -q`
  passed 3 tests.
- `uv run ruff check src/aeat/application/modelo/_external_import_actions.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/_justificante.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`
  passed.
- `uv run ruff check src/aeat/application/live/_filed_observation_persistence.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py`
  passed.

Pull-only CLI drift was rechecked:

- `uv run aeat app live filed pull --help` succeeded.
- `uv run aeat app live filed pull-all --help` failed with `No such command
  'pull-all'. Did you mean 'pull'?`
- `rg -n "pull-all|pull_all|capture-all|capture_all" src/aeat/entrypoints src/aeat/application src/aeat/domain docs/how-to`
  found only negative guard tests.

`W04.P07.S29` was closed through
`vaultspec-core vault plan step check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md S29`
after the focused local and integration gates passed.

Live authenticated proof remains open. The shell still cannot inspect or
create an authenticated live profile without the interactive AEAT credential
handoff, so Modelo 036/censo, filed-history, justificante, notification, and
live-backed calendar proof rows remain unchecked.

## 2026-06-13 Calendar Justificante CSV Case-Equivalence Hardening

RAG discovery was rerun against the current workspace before this slice:

- `vaultspec-rag -t . search --type code --port 8766 --max-results 40 --timeout 300 "calendar AEAT submission state justificante verified local filing state ModeloRecord aeat_accepted external evidence missing conflicting"`
- `vaultspec-rag -t . search --type code --port 8766 --max-results 40 --timeout 300 "filing history enrollment justificante calendar event bucket event Modelo live evidence stamped overview calendar"`
- `vaultspec-rag -t . search --type vault --port 8766 --max-results 40 --timeout 300 "calendar must track local ready to file and AEAT submitted filings justificante checks Modelo filing history"`

The code results pointed back to calendar evidence merge logic and
filed-history live-evidence events. The vault results pointed to the prior
calendar evidence-loader audit trail.

Implementation completed:

- Calendar justificante lookup now uses a casefolded AEAT CSV lookup key so
  Modelo-record and calculation-observation verification align with the
  backend clean-state and filed-history case-insensitive CSV identity rules.
- Case-equivalent justificante metadata is grouped rather than overwritten.
  Verification is granted only when every record under the casefolded CSV key
  matches the same modelo, filing year, typed `Period`, and taxpayer identity.
  A conflicting case-only duplicate leaves the calendar at accepted or
  submitted-observed instead of reporting `justificante_verified`.
- Added regressions for case-insensitive happy paths and conflicting
  case-equivalent metadata on both Modelo-record evidence and official
  calculation-observation evidence.

Code review completed:

- Reviewer Mencius reported a medium issue: the first casefolded dict
  implementation silently overwrote case-only duplicate justificante metadata,
  making verification order-dependent and able to mask contradictory evidence.
- The finding was fixed by grouping duplicate CSV keys and requiring all
  grouped justificantes to agree before calendar verification is granted.

Focused gates passed:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_justificante_csv_match_is_case_insensitive src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_case_equivalent_conflicting_justificantes_do_not_verify src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_sede_calculation_observation_justificante_csv_match_is_case_insensitive src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_sede_calculation_observation_conflicting_case_equivalent_justificantes_do_not_verify -q`
  passed 4 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 49 tests.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_clears_with_matching_justificante_metadata src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_without_enrolled_justificante_still_blocks src/aeat/application/modelo/tests/test_import_flow.py::test_import_csv_register_refuses_without_enrolled_justificante src/aeat/application/live/tests/test_filed_capture_calculation_history.py::test_filed_observation_capture_keeps_existing_csv_register_evidence_for_same_csv_case_insensitive -q`
  passed 4 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 93 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q`
  passed 21 tests.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py`
  passed.

Live authenticated proof remains open. The isolated visible profile wizard at
`var/live-auth-20260613-operator` still has no profile bucket or active-profile
pointer, so this slice proves local projection hardening only.

## 2026-06-13 ModeloRecord CSV-Register Calendar Alignment

RAG discovery was rerun against the current workspace:

- `vaultspec-rag -t . search --type code --port 8766 --max-results 40 --timeout 300 "AEAT_CSV_REGISTER calendar ModeloRecord justificante verified external evidence aeat_csv_register"`

The search and direct `rg` comparison exposed a remaining semantic gap:
calculation observations and clean-state already treated `aeat_csv_register`
as official, justificante-bound evidence, but calendar evidence projected from
persisted Modelo filing records did not include `aeat_csv_register` in its
justificante-backed external-evidence set.

Implementation completed:

- Added `aeat_csv_register` to the calendar's Modelo-record
  justificante-backed evidence kinds.
- Added a regression proving a Modelo record stamped with
  `ExternalEvidenceKind.AEAT_CSV_REGISTER` becomes
  `justificante_verified` only when matching persisted justificante metadata
  exists for the same CSV, modelo, filing year, typed `Period`, and taxpayer.
- Existing conflicting case-equivalent CSV regressions continue to ensure this
  does not mask contradictory metadata.

Code review completed:

- Reviewer Hooke reported no blocking findings.
- The review confirmed that the projection only upgrades when the Modelo
  record is AEAT accepted, the evidence kind is justificante-backed, and
  persisted metadata passes CSV, taxpayer, modelo, filing year, and typed
  `Period` checks.

Focused gates passed:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_csv_register_external_evidence_is_justificante_backed src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_justificante_csv_match_is_case_insensitive src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_modelo_record_case_equivalent_conflicting_justificantes_do_not_verify -q`
  passed 3 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 50 tests.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_clears_with_matching_justificante_metadata src/aeat/application/calculations/tests/test_cross_period_clean_state.py::test_csv_register_evidence_without_enrolled_justificante_still_blocks src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py::test_cross_period_clean_state_accepts_csv_register_with_matching_justificante_metadata src/aeat/application/modelo/tests/test_import_flow.py::test_import_csv_register_refuses_without_enrolled_justificante src/aeat/application/modelo/tests/test_import_flow.py::test_import_supersedes_prior_current_filing -q`
  passed 5 tests.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q`
  passed 94 tests.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q`
  passed 21 tests.
- `uv run aeat app live filed pull-all --help` failed with `No such command
  'pull-all'. Did you mean 'pull'?`
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py`
  passed.

Live authenticated proof remains open. The fresh isolated profile store still
contains only `logs/aeat.log`, so the live Modelo 036/censo, filed-history,
justificante, notification, and calendar pull rows remain unchecked.
