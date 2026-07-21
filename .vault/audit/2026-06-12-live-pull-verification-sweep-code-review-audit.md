---
tags: ['#audit', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-13'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# `live-pull-verification-sweep` Code Review

## LPS-001 | INFO | No blocking review findings for W01.P01-S01 through W01.P02-S06

Reviewed the sweep plan state, sweep index, and six new exec records for the inventory, classification, predecessor cross-link, central access gate, remote-operation policy, and static live-surface mutation guard rows. The checked plan rows now have matching exec records with required `#exec` and `#live-pull-verification-sweep` tags, `step_id` values, and parent plan wiki-links.

The evidence does not claim authenticated AEAT success for rows that only ran local help, inspection, and focused test gates. The remaining live credential/profile dependency is preserved in the notes instead of being treated as closed work.

## LPS-002 | INFO | S07 remains correctly open

The review intentionally leaves `W01.P02.S07` unchecked because `aeat app live iva-wallet --help` still exposes `pull-remote-state`. That name is currently described as read-only acquisition in help text, but the plan row requires retiring or rewording operator-facing remote-state vocabulary. Closing S07 would overclaim the current state.

## LPS-003 | LOW | Vaultspec step-check command exits non-zero after saving

Every `vaultspec-core vault plan step check` invocation printed `Closed Step` and the subsequent plan status confirmed persistence, but the command exited with a `ContextVar` lookup traceback during cache invalidation. The saved plan state is valid, but the non-zero exit should be treated as a tooling defect and mentioned in handoff notes.

## LPS-004 | INFO | No blocking review findings for S07 vocabulary cleanup

Reviewed the S07 changes that replaced the operator-facing IVA wallet `pull-remote-state` command with `pull-evidence`, updated the JSON envelope/schema id, help locale key, documented command example, and timeout diagnostic surface. Backend `remote_state` names remain implementation-only vocabulary for the read-only acquisition service.

Focused gates passed for the CLI command registration, JSON schema conformance, documented command conformance, locale parity, and ruff. The old command now fails with `No such command 'pull-remote-state'`; help output lists `pull-evidence`. No blocking findings remain for this row.

## LPS-005 | INFO | No blocking review findings for S14 active justificante snapshot hardening

Reviewed the S14 local backend hardening around `register_capture_as_filing_evidence` and the regression in `test_stamp_refuses_non_active_live_capture_snapshot`. The guard now refuses any non-`ACTIVE` live justificante capture before parsing, justificante persistence, `AEAT_LIVE_CAPTURE` attachment, or `aeat_accepted` stamping. The regression asserts the filing remains unaccepted and has no external evidence after a superseded capture is presented.

The exec record correctly avoids overclaiming full S14 completion: authenticated AEAT justificante pull and censo/profile/calendar reconciliation remain open until a fresh profile tax ID matching the operator-authenticated AEAT identity is available.

## LPS-006 | INFO | No blocking review findings for expedientes/calendar identity binding

Reviewed the W02.P04.S12 and W03.P06.S27 delta in `src/aeat/application/live/_expedientes.py`, `src/aeat/application/live/__init__.py`, `src/aeat/application/overview/_calendar.py`, `src/aeat/entrypoints/cli/_overview.py`, and the focused expedientes/calendar CLI tests. Expedientes snapshots now persist the authenticated session identity, overview calendar projection gates expediente filing events and filing evidence against the active taxpayer, filed-declaration and calculation observations retain taxpayer identity checks, and the event identity field is excluded from JSON output.

Focused gate: `uv run pytest src/aeat/application/live/tests/test_expedientes.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed with 82 selected tests and 9 deselected. No blocking findings were identified.

## LPS-007 | HIGH | Parser-backed verification writes decrypted justificante bytes to a temp file

The W02.P04.S14/W03.P06.S27 overview CLI delta loads encrypted filed-declaration artefact bytes and then materialises them as a plaintext `*.pdf` via `tempfile.mkstemp` plus `handle.write(body)` before calling `parse_justificante`. That violates `sensitive-financial-data-secure-storage-only`: decrypted evidence bytes may exist transiently in memory only and must never be written to temp files, scratch directories, or logs outside secure storage. The post-parse unlink does not make the write acceptable. Keep the parser-backed verification, but route it through an in-memory parser/adapter or another secure-storage-respecting path before this row is accepted.

## LPS-008 | INFO | LPS-007 remediated with in-memory justificante parsing

The filed-declaration calendar verification path now calls `parse_justificante_bytes`, which extracts text from in-memory PDF bytes and binds the digest directly into the shared justificante extractor. The overview CLI no longer imports or calls `tempfile`, `mkstemp`, `os.fdopen`, or any temp-file parser bridge for decrypted filed-declaration artefact bytes.

Focused gates passed after the remediation: `uv run pytest src/aeat/adapters/inbound/justificante/tests/test_parser.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/application/overview/tests/test_calendar.py -m "integration or not integration" -q` with 159 tests, and `uv run ruff check` over the touched justificante parser and overview CLI files. A text scan over the modified calendar/parser path found no remaining `tempfile`, `mkstemp`, or `NamedTemporaryFile` references.

## LPS-009 | INFO | No blocking review findings for filed-pull justificante metadata enrollment

Reviewed the filed-declaration enrollment path that parses matching stored `justificante_pdf` artefacts in memory and persists parsed metadata to `JustificanteRepository`, plus the filed pull report/payload wiring. No blocking findings were identified.

The review confirmed that enrollment requires an active `ALTA` observation, matching modelo, ejercicio, typed period, and authenticated taxpayer identity; wrong-taxpayer justificantes remain unenrolled. It also confirmed the scoped path uses `parse_justificante_bytes` and does not reintroduce a temp-file bridge for decrypted artefact bytes.

Focused gates passed for the reviewer: the two new filed metadata enrollment tests, and the JSON schema conformance test. Local supervisor gates also passed for the filed capture suite, cross-period clean-state suite, overview calendar suite, filed CLI subset, and schema/payload selected lane.

## LPS-010 | INFO | No blocking review findings for cross-period justificante identity gate

Reviewed the W04.P08.S31 scoped delta in `src/aeat/application/calculations/_cross_period_clean_state.py` and `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`. No blocking findings were identified.

The justificante match now refuses `AEAT_LIVE_CAPTURE` and `AEAT_JUSTIFICANTE_PDF` evidence when neither `member_nif` nor `taxpayer_tax_id` supplies a known taxpayer identity, so a matching modelo, ejercicio, and period alone cannot clear cross-period clean-state. Group member filings remain covered because `filing.member_nif` is still the first identity source for both justificante comparison and member observation provenance checks, so member fan-in does not depend on the parent taxpayer id to validate a member receipt.

The tests use real repository/catalogue/domain objects under `isolated_runtime_profile`, not fakes, mocks, stubs, monkeypatches, skips, or xfails. The focused clean-state suite passed with `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` reporting 31 passed.

## LPS-011 | INFO | No blocking review findings for bounded all-model filed history

Reviewed the W02.P04.S11 and W03.P05.S17 scoped delta in `src/aeat/core/_config_timeouts.py`, `src/aeat/application/live/_filed_data.py`, `src/aeat/application/live/_filed_data_capture.py`, `src/aeat/application/live/__init__.py`, `src/aeat/application/live/tests/test_filed_bulk_capture.py`, and `src/aeat/entrypoints/cli/_app_live.py`. No blocking findings were identified.

The filed CLI now keeps all-model acquisition under `filed pull` options, and the help surface exposes `list`, `pull`, and `pull-sources` only; `pull-all` is rejected. The all-model list path delegates to `list_filed_data_bulk`, which opens one authenticated register session and returns typed per-model/year failure rows instead of looping backend sessions in the CLI. Filed register walks are bounded by `aeat_live_filed_register_walk_timeout_ms` and bulk list/pull paths preserve partial success by mapping query and capture failures into `FiledDataCaptureFailureRow`.

The filed pull and pull-sources report wiring still carries the justificante enrollment fields for metadata CSVs, stamped filing evidence ids, and conflict ids in both text metrics and JSON payload construction. The focused review gates passed: `uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py -q` reported 5 passed, `uv run ruff check` passed for the six scoped files, and CLI help checks confirmed `filed pull-all` is not registered.

## LPS-012 | INFO | No blocking review findings for calendar censo reconciliation warning

Reviewed the scoped delta in `src/aeat/application/overview/_calendar.py`, `src/aeat/entrypoints/cli/_overview.py`, `src/aeat/entrypoints/cli/_config/_profile_censo.py`, `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`, `src/aeat/core/access_gate/__init__.py`, `src/aeat/core/access_gate/tests/test_override.py`, and the four overview locale files. No blocking findings were identified.

The calendar now receives censo-stamped profile paths from the CLI and emits `censo.enrolment_unverified` for active Modelo obligations whose applicability has no censo-backed enrolment path. Strict calendar mode refuses that warning, while `--allow-incomplete` exposes the provisional calendar with affected modelos and still carries per-obligation local-vs-AEAT filing evidence and justificante verification booleans. `config profile censo apply` uses the same provenance input for its post-apply calendar summary, avoiding a parallel enrolment projection path.

The censo CLI sub-app is now decorated with the shared error boundary before mounting. The synchronous live-read preflight prevents censo pull tests from reaching configured Clave identity checks before the pytest live gate; the access gate also detects a loaded pytest module when Click isolation hides `PYTEST_CURRENT_TEST`, while preserving the explicit operator-context seam.

Focused gates passed for the reviewer: 32 CLI/access-gate tests, 189 overview tests, and ruff over the touched calendar/censo/access-gate files. Live verification reached AEAT G313 but returned no readable censo, so the censo-positive plan rows correctly remain open. The live calendar now surfaces the censo-unverified warning for modelos `100`, `303`, `390`, and `721`.

## LPS-013 | INFO | No blocking review findings for Period-backed filed-history calendar guard

Reviewed the additional regression in `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` and the active plan wording update. No blocking findings were identified.

The regression uses the real Modelo 130 justificante PDF fixture and the encrypted filed-declaration observation store. It proves that a stored justificante artefact that parses as Modelo 130 / 2026 / `1T` can verify the matching `1T` observation, while a second observation that reuses the same bytes but claims typed Period `2T` remains only `submitted_observed` with `justificante_verified=false`. This preserves the current `core.Period` authority and prevents a storage-ref-only shortcut from upgrading a filed-history row to verified justificante evidence.

The command-drift tracking was corrected in the active plan: censo is now tracked as `pull`, and filed-history coverage explicitly keeps `pull-all` absent. Focused gates passed for the new regression, the `pull`/no-`pull-all` CLI guards, the overview calendar suite, the live filed/justificante enrollment suites, cross-period clean state, and external import.

## LPS-014 | INFO | No blocking review findings for direct justificante conflict guard

Reviewed the direct `register_capture_as_filing_evidence` change in `src/aeat/application/live/_justificante.py` and its regressions in `src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`. No blocking findings were identified.

The direct live justificante path now matches the filed-history enrollment contract: a current filing with existing AEAT evidence for the same CSV is idempotent and can repair missing parsed justificante metadata, while a different existing AEAT evidence reference is not overwritten. The refusal happens before `JustificanteRepository.save`, filing catalogue save, or `MODELO_LIVE_EVIDENCE_STAMPED` event emission, so a conflicting live capture cannot mutate the official evidence axis.

Focused gates passed across direct live justificante capture, filed-history enrollment, cross-period clean state, external import, overview calendar, and live filed CLI command-tree guards. Live checks additionally proved the filed list/pull command path is operational for Modelo 303/2026, but no filed rows exist in the authenticated account state to enroll as positive official evidence.

## LPS-015 | INFO | No blocking review findings for strict calendar justificante warning

Reviewed the calendar warning hardening in `src/aeat/application/overview/_calendar.py`, the CLI regression in `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`, and the locale additions for `filing.justificante_unverified`. No blocking findings were identified.

The calendar now refuses strict rendering when AEAT-observed or AEAT-accepted filing evidence exists without a verified matching justificante. The warning is keyed separately from censo provenance and points operators to the existing `aeat app live filed pull --modelo MODELO --year YEAR` remediation path; no `pull-all` operator surface was introduced. The CLI regression proves strict mode refuses the unverified AEAT filing while `--allow-incomplete` exposes the warning, affected modelo, and `pull` fix command in JSON.

Focused gates passed for the overview calendar suite, CLI calendar suite, live justificante/filed-history suites, cross-period/model import suites, CLI `pull`/no-`pull-all` guards, ruff over touched Python files, and YAML parsing for the touched locale files. RAG discovery was attempted first with `vaultspec-rag search --timeout 90` but timed out with `http_search_timeout`; direct code search was used afterward.

## LPS-016 | INFO | No blocking review findings for filed CLI output hardening

Reviewed the filed CLI text-output helper added to `src/aeat/entrypoints/cli/_app_live.py` and the focused report-model tests in `src/aeat/entrypoints/cli/tests/test_registry_cli.py`. No blocking findings were identified.

The change does not move the live-read gate or introduce a new AEAT transport path. It only centralizes text metrics after the existing backend reports are returned, preserving the JSON payload construction already used by `filed pull` and `filed pull-sources`. The new text lines improve operator-visible evidence by showing mode, target, failure count, justificante metadata count, filing evidence stamp count, conflict count, observation paths, and artefact refs. Bulk acquisition remains under `filed pull`; no `pull-all` command or alias was introduced.

Focused gates passed for ruff, six filed command/output tests, and the full registry CLI test file. The live-auth acceptance blocker remains open, so this review does not claim authenticated filed command completion.

## LPS-017 | INFO | No blocking review findings for censo CLI auth preflight

Reviewed the scoped censo CLI change in `src/aeat/entrypoints/cli/_config/_profile_censo.py`
and the regression in `src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`.
No blocking findings were identified.

`config profile censo pull` now emits the shared redacted live-auth preflight
after resolving the active profile and before the live-read access gate or
backend censo fetch is reached. This aligns censo/Modelo 036 pull with the
other authenticated pull surfaces without changing the local-only `show`,
`compare`, or `apply` commands, and without introducing any `pull-all` verb.

Focused gates passed for ruff, the censo live-gate refusal regression, and the
full censo CLI verb suite. Live retries reached AEAT Cl@ve in QR and non-QR
modes and timed out before operator-mediated auth completion, so the positive
censo and calendar-projection plan rows correctly remain open.

## LPS-018 | INFO | No blocking review findings for calendar text evidence details

Reviewed the scoped calendar text-output change in `src/aeat/entrypoints/cli/_overview.py`
and its CLI regression in `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.
No blocking findings were identified.

The change only affects operator text rendering for existing calendar filing
evidence rows. It preserves the already-computed local filing axis,
AEAT-submission axis, and justificante verification axis, while adding the
auditable identifiers already present in JSON: local filing record id, AEAT
reference id, AEAT evidence kind, and evidence source. The same helper is used
for single-profile and `--all-profiles` output, so the two text surfaces cannot
drift.

Focused gates passed for ruff, the new evidence-detail regression, and the full
overview calendar CLI suite. This review does not claim live authenticated
calendar completion; the live censo/filed/justificante acceptance rows remain
open until AEAT authentication completes and returns positive evidence.

## LPS-019 | INFO | No blocking review findings for calendar CSV-register justificante guard

Reviewed the scoped CLI regression in
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`. No blocking
findings were identified.

The new regression proves the calendar strict-mode surface refuses an imported
Modelo 303 filing record whose AEAT evidence is `aeat_csv_register` but has no
matching verified justificante. The allowed-incomplete JSON still reports the
record accurately as an external baseline with `aeat_submission_state=accepted`,
`aeat_evidence_kind=aeat_csv_register`, and `justificante_verified=false`. This
matches the cross-period clean-state invariant that CSV/register evidence is
not enough to clear justificante verification.

Focused gates passed for the new CLI regression, full overview calendar CLI
suite, and adjacent cross-period/modelo verification tests covering CSV-register
blockers. No live-auth completion is claimed by this review.

## LPS-020 | INFO | No blocking review findings for censo IVA enrolment provenance

Reviewed the scoped censo CLI provenance change in
`src/aeat/entrypoints/cli/_config/_profile_censo.py` and its regressions in
`src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`. No blocking
findings were identified.

The censo apply calendar summary now includes `iva.regime=aeat_censo_read`
when the active censo snapshot supplies the IVA regime. This aligns the apply
output with the overview calendar warning logic, which already treats
`iva.regime` as an enrolment profile key for IVA modelos. Per-obligation rows
remain applicability-scoped: Modelo 303 carries the IVA regime source while
Modelo 100 remains tied to the taxpayer entity source.

Focused gates passed for ruff, the censo apply text/JSON regressions, the full
censo CLI suite, the censo calendar warning pair, and the user-profile censo
derivation test. Positive live Modelo 036/censo pull evidence remains open.

## LPS-021 | INFO | No blocking review findings for censo enrolment key centralisation

Reviewed the centralisation change in `src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/__init__.py`,
`src/aeat/entrypoints/cli/_config/_profile_censo.py`, and the focused overview
calendar/censo CLI tests. No blocking findings were identified.

The censo apply summary now consumes `calendar_censo_enrolment_profile_keys()`
from the overview application surface instead of carrying a local copy of the
calendar's censo provenance key set. This makes `iva.regime` and future censo
enrolment keys single-authority for both calendar warnings and censo apply
reporting.

Focused gates passed for ruff, the central key-set unit test, the full overview
calendar unit suite, and the full censo CLI suite. Positive live Modelo
036/censo pull evidence remains open.

## LPS-022 | INFO | No blocking review findings for Cl@ve live persistence proof

Reviewed the scoped S09 test change in
`src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py`. No
blocking findings were identified.

The full Cl@ve live test now verifies the persistence contract in the same
pytest-isolated runtime that performs the operator-mediated login: after a real
`ClaveMovilAuthProvider.authenticate()` and `verify()` pass, it asserts the
storage-state object exists only in the encrypted session store, closes the
first provider, and uses a fresh provider instance to run
`probe_persisted_session()` through the central Playwright backend. This avoids
the earlier cross-process profile mismatch without adding a fake backend,
ordering dependency, skip, or production auth path.

Focused gates passed for ruff on the touched live test, the non-interactive
Cl@ve selector live probe, and the full operator-auth Cl@ve live test with the
new persisted-session probe. Certificate live credentials remain unconfigured
and are not claimed as covered by this Cl@ve acceptance pass.

## LPS-023 | INFO | No blocking review findings for all-required censo calendar provenance

Reviewed the scoped censo/calendar hardening in
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/tests/test_calendar.py`, and
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`. No blocking
findings were identified.

The calendar censo warning now requires every censo-relevant enrolment key for
a Modelo obligation to be live-censo verified before the warning clears. This
prevents a partial Modelo 036/censo stamp, such as entity type without
`iva.regime`, from making Modelo 303 look fully censo-backed. The new unit
regressions cover both the partial and complete Modelo 303 provenance states,
and the CLI censo-stamped fixture now stamps `iva.regime` so the stricter rule
matches the expected censo apply output.

Focused gates passed for ruff, the new censo calendar warning unit pair, the
full overview calendar unit suite, the censo calendar CLI warning pair, the
full censo CLI suite, the full overview calendar CLI suite, and the explicit
live command-tree `pull-all` negative tests. RAG discovery was attempted first
against the resident service but timed out with `http_search_timeout`; exact
symbols were verified with `rg`. Positive live Modelo 036/censo, filed-history,
and justificante evidence remains open and is not claimed by this review.

## LPS-024 | MEDIUM | Resolved corporate censo keys missing from per-Modelo warning path

Reviewer Sagan identified that corporate censo enrolment keys were centralized
but not reachable from the per-Modelo applicability helper used by
`censo.enrolment_unverified`. The gap meant a corporate calendar row, including
Modelo 202, could clear the censo warning without verifying
`taxpayer_type.legal_entity_form`, `taxpayer_type.incn_prior_12_months`, or
`taxpayer_type.new_entity_first_two_profit_periods`.

Resolved in the same slice by adding an explicit corporate censo enrolment key
mapping for Modelos 200 and 202 under the overview calendar application
surface. Modelo 200 now includes legal entity form; Modelo 202 includes legal
entity form, INCN, and the first-two-profit-periods flag. Added focused Modelo
202 regressions proving partial corporate provenance still warns and complete
corporate provenance clears.

Focused gates re-ran clean after the fix: ruff over touched files, the Modelo
303 censo warning pair, the new Modelo 202 censo warning pair, the full
overview calendar unit suite, the censo calendar CLI warning pair, the full
censo CLI suite, the full overview calendar CLI suite, and the explicit
`pull-all` negative tests.

## LPS-025 | HIGH | Resolved calendar evidence loaders silently erasing local AEAT state

Reviewer Newton identified that the overview calendar CLI swallowed exceptions
while loading local live-event, Modelo-record, and filing-evidence stores. A
corrupt persisted evidence store could therefore be projected as empty evidence
and allow strict calendar rendering to miss `filing.justificante_unverified`.

Resolved in the same slice by making the three loader helpers fail closed with
a CLI refusal instead of returning `()`. The exceptions remain logged and are
chained into the refusal, but the calendar no longer renders a cleaner state
when persisted AEAT filing evidence cannot be inspected. The `--all-profiles`
loop now re-raises those refusal exceptions instead of converting them into
`profile_skipped`. Added real secure-storage regressions that write a corrupt
encrypted filed-declaration observation record and prove both single-profile
and all-profiles calendar rendering refuse rather than erasing the evidence
set.

The same slice also added Modelo filing records as calendar `event filing`
rows. Local app filing records now appear in the event stream with
`aeat=not_observed` until external AEAT evidence is attached and a matching
persisted justificante verifies the receipt, preserving the application-filing
versus real-world AEAT-filing distinction.

Focused gates passed after remediation: ruff over touched files, the two new
Modelo-record event unit tests, the corrupt-store CLI refusal tests for
single-profile and all-profiles calendar rendering, the full overview calendar
unit suite, the full overview calendar CLI suite, the full cross-period
clean-state unit suite, focused external-import justificante identity tests,
focused filed-history justificante enrollment tests, and the explicit
`pull-all` negative tests. RAG discovery was attempted first against the
resident service and timed out with `http_search_timeout`; exact symbols were
verified with `rg`.

Final reviewer re-check found no remaining issues after the all-profiles
refusal fix. The re-check confirmed corrupt local filing evidence is no longer
downgraded to `profile_skipped`.

## LPS-026 | INFO | No blocking review findings for live justificante reconcile and calendar fail-closed sweep

Reviewed the scoped delta in `src/aeat/application/modelo/_reconcile.py`,
`src/aeat/application/modelo/__init__.py`,
`src/aeat/application/live/_justificante.py`,
`src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`,
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`, and the four
overview locale files. No blocking findings were identified.

The live justificante reconcile path now uses `modelo_reconcile_bytes` and
records only a `secure-object://` reference for persisted captures; exact
search found no remaining `tempfile`, `mkstemp`, `NamedTemporaryFile`, or
`_materialized_capture_pdf` path in the reviewed live/modelo reconcile
surface. Existing file-backed `modelo_reconcile` remains available for the
local `reconcile file --file` surface, while live capture reconcile stays
in-memory and never writes decrypted justificante bytes to plaintext temp disk.

The direct live capture evidence stamp validates active snapshot state, current
filing record, parsed modelo/year/period/taxpayer identity, and conflicting
existing AEAT evidence before mutating filing evidence. The idempotent same-CSV
case repairs persisted justificante metadata without rewriting the filing event.
Calendar loading refuses unreadable local filing evidence through
`typer.BadParameter`; the all-profiles path re-raises that refusal and does not
downgrade corrupt AEAT filing evidence to `profile_skipped`.

Focused gates passed: `uv run pytest
src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py
src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q` reported 14
selected tests passed, and `uv run ruff check` passed for the reviewed Python
files. Locale YAML parsed under the project environment and all four locale
files expose `calendar_local_filing_evidence_unavailable`,
`warning.justificante_unverified` text for the `filing.justificante_unverified`
runtime warning, and `pull_evidence_help` without `pull_remote_state_help`. RAG
discovery was attempted first with
`vaultspec-rag search "live justificante reconcile secure storage calendar fail
closed" --type code --port 8766 --max-results 20 --timeout 120`; the resident
service was healthy but the search timed out with `http_search_timeout`, so the
review proceeded with exact `rg` confirmation. Positive authenticated live-auth
acceptance remains blocked externally and is not claimed by this review.

## LPS-027 | INFO | No blocking review findings for justificante pull enrolment outcome

Reviewer Hilbert audited the focused delta in `src/aeat/application/live/__init__.py`,
`src/aeat/application/live/_justificante.py`,
`src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`,
`src/aeat/entrypoints/cli/_app_live_justificante_cli.py`, and
`src/aeat/entrypoints/cli/_app_live_payloads.py`. No blocking findings were
identified.

The review confirmed that `capture_justificante_snapshot_outcome` returns the
actual stamped `ModeloRecord` when enrolment succeeds, and that
`stamp_capture_evidence_if_filed` now returns `None` only for the no-current
filing and parse-invalid cases. Current-record conflicts for taxpayer, modelo,
year, period, snapshot lifecycle, or conflicting existing AEAT evidence
propagate instead of being silently erased by the capture orchestrator.

The CLI review confirmed that `aeat app live justificante pull` emits
`filing_evidence_stamped` and `filing_record_id` through the registered JSON
payload and text output. Exact search found no reviewed `pull-all` drift and no
plaintext temp-file bridge in the live justificante/CLI path.

Supervisor gates passed for ruff, the live justificante reconciliation suite,
live CLI read/justificante verb tests, pull-only registry guards, calendar CLI
projection, cross-period clean-state, modelo import, and the shared JSON
envelope/output renderer. RAG discovery was retried with a 240 second timeout
and still returned `http_search_timeout`, so exact `rg` discovery was used.
Positive authenticated Modelo 036/censo, filed-history, justificante, and
calendar aggregation evidence remains open because the Codex shell is
non-interactive and `AEAT_SECRET_PASSPHRASE` is not set.

## LPS-037 | MEDIUM | Resolved CSV-register justificante-bound clean-state gate

Reviewer Russell audited the scoped CSV-register hardening in
`src/aeat/application/modelo/_external_import_actions.py`,
`src/aeat/application/calculations/_cross_period_clean_state.py`,
`src/aeat/application/live/_filed_observation_persistence.py`,
`src/aeat/application/live/_justificante.py`, and the related calculation,
modelo, overview, and live tests.

The review identified `CSVREG-001`: filed-history justificante enrollment
treated existing `AEAT_CSV_REGISTER` evidence for the same receipt CSV as a
conflict when letter case differed. That could create a false manual conflict
against an already verified AEAT CSV-register import.

Resolved in the same slice. CSV-register import now requires enrolled
justificante metadata before it can stamp a Modelo filing as AEAT accepted;
cross-period clean-state accepts CSV-register evidence only when the persisted
justificante metadata matches CSV, modelo, year, typed `Period`, and taxpayer
identity; filed-history enrollment now compares same-CSV existing evidence
case-insensitively. The regression keeps lowercase existing CSV-register
evidence without overwriting it when the parsed filed-history justificante has
the same CSV.

Focused gates passed: targeted CSV-register import and clean-state tests, the
full cross-period clean-state/provenance/import/gate/calendar slice, the
affected Modelo clean-state and reconcile suites, the full filed-history
calculation-history plus persisted-justificante live suite, ruff over the
touched files, and pull-only CLI checks proving `pull` is present and
`pull-all` remains absent outside negative guard tests.

Positive authenticated Modelo 036/censo, filed-history, justificante,
notification, and calendar aggregation evidence remains open because no
interactive AEAT-authenticated profile handoff has completed in this shell.

## LPS-038 | MEDIUM | Resolved calendar case-equivalent justificante CSV masking

Reviewer Mencius audited the scoped calendar CSV lookup hardening in
`src/aeat/application/overview/_calendar.py` and
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`.

The review identified that a simple casefolded `dict` index for justificante
metadata would overwrite case-only duplicate CSV records. If the repository
contained `ABC123` and `abc123` with different taxpayer, modelo, year, or
typed `Period` metadata, calendar verification would become order-dependent
and could mask contradictory AEAT evidence while reporting
`justificante_verified`.

Resolved in the same slice. Calendar justificante lookup now groups every
case-equivalent CSV record and grants verification only when all records under
that key match the same modelo, filing year, typed `Period`, and taxpayer
identity. Conflicting case-only duplicate metadata leaves the calendar at
`accepted` or `submitted_observed`, preserving the justificante-unverified
warning path instead of presenting a verified receipt.

Focused gates passed: the four case-insensitive/conflicting-duplicate
regressions, the full overview calendar filing-evidence suite, the combined
overview calendar suite, the focused cross-period/import/live-filed regression
slice, ruff over the touched calendar files, and pull-only CLI guard tests for
`pull` with no `pull-all`.

Positive authenticated Modelo 036/censo, filed-history, justificante,
notification, and live-backed calendar evidence remains open because the fresh
interactive profile/authentication handoff has not completed.

## LPS-039 | INFO | No blocking findings for ModeloRecord CSV-register calendar alignment

Reviewer Hooke audited the scoped calendar consistency change in
`src/aeat/application/overview/_calendar.py` and
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`.

No blocking findings were identified. The calendar now treats
`aeat_csv_register` as a justificante-backed external evidence kind for
persisted Modelo filing records, aligning the calendar projection with
external import and cross-period clean-state rules. The upgrade to
`justificante_verified` remains gated on `aeat_accepted`, the
justificante-backed evidence kind, and persisted justificante metadata matching
CSV, taxpayer, modelo, filing year, and typed `Period`.

The review confirmed that missing metadata stays accepted/unverified and
therefore remains covered by the justificante-unverified warning path.
Conflicting case-equivalent justificante metadata remains rejected by the
existing grouped CSV ambiguity check, so the new CSV-register path does not
mask contradictory evidence.

Focused gates passed: the CSV-register Modelo-record regression, the
case-equivalent conflict regression, the full overview calendar
filing-evidence suite, the combined overview calendar suite, the focused
cross-period/import CSV-register slice, ruff over the touched calendar files,
and pull-only CLI guards proving `pull` remains the acquisition verb and
`pull-all` remains absent.

Positive authenticated Modelo 036/censo, filed-history, justificante,
notification, and live-backed calendar evidence remains open because the fresh
interactive profile/authentication handoff has not completed.

## LPS-036 | INFO | Calendar official observation source alignment

Status: PASS for local/backend scope; authenticated-live rows remain open.

Reviewed the scoped continuation in
`src/aeat/application/overview/_calendar.py` and
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`.

The finding addressed here was an integration drift: cross-period clean-state
accepted `aeat_sede_live_capture` and `aeat_csv_register` as official observed
state sources, but overview calendar calculation-observation evidence still
accepted only `aeat_sede_justificante`. That could make an official live
capture usable for verification while not appearing as AEAT-side submission
evidence in the user-facing calendar.

Resolved by aligning the calendar calculation-observation official source set
with the verifier. Live capture and CSV-register observations now project to
`submitted_observed` only when they carry `ALTA` register metadata and matching
authenticated identity. They still require a separately persisted matching
justificante before the calendar reports `justificante_verified`.

Focused gates passed: the overview filing-evidence suite, the overview calendar
suite, the overview calendar CLI suite, the live filed/expedientes `pull`
without `pull-all` command guards, and ruff over the touched files.

Positive authenticated Modelo 036/censo, filed-history, justificante,
notifications, and live-backed calendar aggregation evidence remains open. The
default profile store is locked in this non-interactive shell; the development
passphrase does not unlock it; and an isolated interactive profile-create
attempt launched from Codex stayed headless at wizard step 1 and was stopped
without creating a profile. The scratch storage root from that attempt was
removed after verifying it resolved inside the workspace.

## LPS-035 | HIGH | Resolved cross-period verified-state and reconcile hardening findings

Reviewer Kuhn audited the scoped delta in
`src/aeat/application/modelo/_calculation_actions.py`,
`src/aeat/application/modelo/_reconcile.py`,
`src/aeat/application/calculations/_cross_period_clean_state.py`, and the
corresponding Modelo, calculations, live justificante, and reconciliation tests.
No blocking findings remained after the fixes.

The review covered the user-requested axes: direct verified-state bypass
closure, official observation provenance across official source kinds, typed
`Period` handling, reconcile period and taxpayer comparison, absence of
`pull-all` drift, and no shortcuts through mocks, stubs, monkeypatches, skips,
or xfails in the touched tests.

Resolved issues in this wave:

- Direct `mark_revision_verificado_completo` now refuses cross-period
  dependency revisions and forces the production verification path, preserving
  the distinction between local calculation readiness and AEAT-submitted
  filing evidence.
- Official observed-state source kinds now share the same AEAT register
  `ALTA` and authenticated-identity provenance check.
- Modelo reconcile now treats typed period and active-profile taxpayer identity
  mismatches as real differences before it emits a `matches` verdict.

Focused reviewer gates passed:

- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_reconcile.py src/aeat/application/modelo/tests/test_reconciliation_history.py -q`
  passed 67 tests.
- `uv run pytest src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_import_flow.py -q`
  passed 59 tests.

Local gates also passed in the main execution session: the consolidated 145
backend/modelo tests, the 125 overview/calendar/CLI tests, and ruff over the
touched files. `aeat app live filed pull --help` exposes `pull`, `aeat app live
filed pull-all --help` is rejected, and source search finds `pull-all` only in
negative guard tests.

Positive authenticated Modelo 036/censo, filed-history, justificante,
notifications, and live-backed calendar evidence remains open. The current
active profile could not be unlocked in this non-interactive shell with the
available development/test secret or the operator-supplied candidate values, so
the authenticated live plan rows are intentionally not marked complete.

## LPS-034 | HIGH | Resolved typed Period boundary and evidence conflict review findings

Reviewer Rawls audited the scoped continuation in
`src/aeat/application/overview/_calendar_models.py`,
`src/aeat/application/overview/_calendar.py`,
`src/aeat/domain/calculations/registry/_bindings.py`,
`src/aeat/entrypoints/cli/_app_live_justificante_cli.py`, and the matching
overview/domain/CLI tests.

The review identified a high-severity issue: `RegistryModeloObservation` still
accepted display-form `period` values such as `2025 1T` when `filing_period`
was omitted, because failed hydration left `filing_period=None` and the
after-validator returned early. That could silently drop AEAT calculation
observation evidence during calendar projection.

The review also identified a medium-severity issue: calendar evidence merging
could falsely mark `filing.aeat_evidence_conflict` when local live-capture
evidence used a justificante CSV as its reference and filed-history evidence
used an expediente id as its AEAT reference while verifying the same
justificante CSV.

Both findings were resolved. Registry observation hydration now refuses
non-bare period tokens before persistence. Calendar conflict detection now
recognises a reference that equals the other side's verified CSV as the same
receipt, while preserving the conflict warning for genuinely disagreeing local
and filed-history references.

Focused gates passed after the fixes: the targeted registry period drift tests,
the targeted calendar same-CSV and disagreeing-reference conflict tests, ruff
over the touched files, the full overview calendar filing-evidence and
calendar suites, the registry cross-boundary roundtrip suite, the overview
calendar CLI / live justificante / profile censo / command-tree pull-only
guards, and the live justificante reconcile suite.

Positive authenticated Modelo 036/censo, filed-history, justificante,
notification, and live-backed calendar proof remains open because this Codex
shell has no `AEAT_SECRET_PASSPHRASE` and no `AEAT_*` identity environment,
and stdin is not interactive.

## LPS-033 | INFO | No blocking review findings for direct justificante snapshot CSV lock

Status: PASS.

Reviewed the scoped delta in `src/aeat/application/live/_justificante.py` and
`src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`.
No Critical or High findings were identified.

The direct live justificante stamping path now compares the CSV parsed from the
official receipt bytes against the persisted live snapshot CSV before it saves
justificante metadata, attaches `AEAT_LIVE_CAPTURE` external evidence, marks
the Modelo filing as AEAT accepted, or emits the live-evidence event. This
removes a metadata-substitution bypass where a corrupted snapshot record could
have replaced the parsed receipt CSV with a different evidence reference.

The guard preserves the existing checks for active snapshot lifecycle, current
filing record, modelo, filing year, typed `core.Period`, taxpayer identity, and
existing AEAT evidence conflicts. The review explicitly did not require
equality between `expediente_id` and justificante `presentation_id`; current
fixture evidence shows those are distinct AEAT identifiers in the direct
justificante capture path.

Focused gates passed for the reviewer: live justificante reconcile/stamping
tests, cross-period clean-state tests, ruff over the touched live/calculation
files, calendar filing-evidence tests, Modelo import and clean-state gates, and
overview calendar CLI tests. This review does not claim positive live AEAT
evidence because the current environment still lacks a completed authenticated
session.

## LPS-032 | INFO | No blocking review findings for notification snapshot authenticated identity lock

Status: PASS.

Reviewed the scoped delta in `src/aeat/application/live/_notifications.py`,
`src/aeat/application/live/__init__.py`,
`src/aeat/application/live/tests/test_notifications.py`,
`src/aeat/application/overview/_calendar.py`, and
`src/aeat/application/overview/tests/test_calendar.py`. No Critical or High
findings were identified.

The live notification capture now persists the authenticated AEAT session
identity on the notification snapshot, matching the expediente snapshot pattern
already used by calendar projection. The persisted field is optional, so older
snapshots without it remain readable and continue to derive their legacy
content-addressed ids. New live captures include the normalised authenticated
identity in the snapshot id, preventing same-row snapshots captured under
different AEAT identities from collapsing to the same persisted record.

Calendar projection first rejects notification snapshots whose authenticated
identity contradicts the active profile. It still checks explicit row-level
`titular_nif` and `destinatario_nif` values, so a matching authenticated
session cannot leak a row that names another taxpayer. Snapshots without the
new identity field fall back to row-level filtering, preserving existing local
data behavior.

Focused gates passed for the reviewer: notification service tests, overview
calendar unit tests, ruff over the touched files, overview calendar CLI tests,
calendar filing-evidence tests, and the live command-tree `pull`/no-`pull-all`
guard suite. This review does not claim positive live AEAT evidence because
the current environment still lacks a completed authenticated session.

## LPS-031 | INFO | No blocking review findings for notification calendar taxpayer scope

Status: PASS.

Reviewed the scoped notification calendar delta in
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/tests/test_calendar.py`, and
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`. No Critical
or High findings were identified.

The calendar now filters notification-derived `message` events by the active
profile tax id using persisted AEAT row identity fields (`titular_nif` and
`destinatario_nif`). These events remain `message` events only and do not
enter the filing-evidence path, so a notification cannot satisfy AEAT filing or
justificante verification. The full calendar builder threads the same expected
tax id already used for expediente, filed-observation, calculation-observation,
and Modelo-record evidence projection.

The review also rechecked typed `core.Period` and CLI verb drift boundaries for
the touched surface. The new code does not stringify a Period for storage or
comparison; notification rows carry dates only, while filing evidence continues
to compare typed Period values. Active source and how-to scans found no
production `pull-all` command or documentation entry; `pull-all` appears only
in negative guard tests and historical vault records.

Focused gates passed for the reviewer: overview calendar unit tests, overview
calendar CLI tests, ruff over the touched files, the `pull`/no-`pull-all`
registry guards, and bulk filed rendering. Positive authenticated Modelo
036/censo, filed-history, justificante, notification, and live-backed calendar
evidence remains open because the latest Cl@ve attempts did not complete an
authenticated AEAT session.

## LPS-030 | HIGH | Resolved filed-history justificante metadata threading review findings

Reviewer Locke audited the scoped filed-history metadata threading in
`src/aeat/application/live/_filed_data_capture.py`,
`src/aeat/application/live/_filed_observation_persistence.py`,
`src/aeat/application/live/tests/test_filed_capture_calculation_history.py`,
`src/aeat/application/calculations/_cross_period_clean_state.py`, and
`src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.

The review identified a high-severity issue: filed-history justificante
enrolment could stamp a current Modelo filing without comparing a parsed
receipt `presentation_id` to the filed-register `expediente_id` when both were
available. It also identified a medium-severity issue: clean-state compared
singular `aeat_justificante_csv` metadata but ignored plural
`aeat_justificante_csvs` metadata emitted when an observation carried multiple
parsed CSVs.

Resolved in the same slice. Parsed filed-history justificantes now refuse
metadata persistence and Modelo filing stamping when the receipt presentation
id and filed-register expediente disagree. Clean-state now accepts plural
filed-history CSV metadata only when the Modelo filing evidence CSV is one of
the parsed filed-history CSVs; otherwise it adds
`mismatched_external_evidence_record`.

Focused gates passed after the fixes: targeted presentation-id and plural CSV
regressions, the full filed-history capture calculation-history suite, the full
cross-period clean-state suite, Modelo clean-state enforcement and gate suites,
filed bulk capture tests, filed CLI rendering tests, JSON envelope/output
rendering tests, and ruff over the reviewed files.

Positive authenticated Modelo 036/censo, filed-history, justificante, and
calendar aggregation evidence remains open because the Codex shell is
non-interactive and `AEAT_SECRET_PASSPHRASE` is not set.

## LPS-029 | INFO | No blocking review findings for cross-period filed-history reference locking

Reviewer Peirce audited the scoped delta in
`src/aeat/application/calculations/_cross_period_clean_state.py` and
`src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
No blocking findings were identified.

The review confirmed that optional filed-history `aeat_justificante_csv`
metadata is compared against the parsed justificante CSV backing the current
Modelo filing record, and optional `aeat_expediente_id` metadata is compared
against the parsed justificante `presentation_id` only when AEAT exposes that
presentation id. Existing modelo, year, typed `Period`, and taxpayer identity
checks remain active. Member fan-in now passes each member observation's own
source kind and metadata into the filing-history check instead of using only
the aggregate source kind.

Focused gates passed: the four new reference-locking regressions, the full
cross-period clean-state suite, the Modelo clean-state enforcement and gate
suites, and ruff over the reviewed files.

Positive authenticated Modelo 036/censo, filed-history, justificante, and
calendar aggregation evidence remains open because the Codex shell is
non-interactive and `AEAT_SECRET_PASSPHRASE` is not set.

## LPS-028 | HIGH | Resolved all-profiles calendar strict-mode warning bypass

Reviewer Halley identified that single-profile calendar rendering refused
`cal.warnings` unless `--allow-incomplete` was set, but the `--all-profiles`
path rendered per-profile warnings and still emitted a successful envelope.
That meant `filing.aeat_evidence_conflict` and
`filing.justificante_unverified` could be downgraded to successful output in
one CLI mode.

Resolved in the same slice by sharing the calendar warning refusal helper
between single-profile and all-profiles rendering. The all-profiles path now
raises the same `cli.overview.calendar_refused_incomplete` refusal before
output succeeds unless `--allow-incomplete` is explicitly present.

The scoped calendar evidence review otherwise found no blocking issues in the
merge logic, conflict reference preservation, typed `Period` keying, JSON/text
field exposure, locale keys, or pull-only wording. Focused gates passed after
the fix: the new conflict all-profiles regression pair, the full overview
calendar filing-evidence suite, the overview calendar unit suite, the full
overview calendar CLI suite, pull-only command conformance tests, ruff over the
reviewed files, JSON envelope/output rendering tests, and locale YAML parsing.

Positive authenticated Modelo 036/censo, filed-history, justificante, and
calendar aggregation evidence remains open because the Codex shell is
non-interactive and `AEAT_SECRET_PASSPHRASE` is not set.

## LPS-040 | INFO | No blocking findings for row-level censo calendar exposure

Status: PASS for the reviewed live-pull-verification-sweep slice; one broader
registry gate remains red outside this slice.

Reviewer Codex audited the scoped delta in
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/_calendar_models.py`,
`src/aeat/application/overview/__init__.py`,
`src/aeat/entrypoints/cli/_overview.py`,
`src/aeat/entrypoints/cli/_overview_payloads.py`,
`src/aeat/application/overview/tests/test_calendar.py`,
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`,
`src/aeat/entrypoints/cli/tests/test_registry_cli.py`, and
`var/aeat/live-auth-run/run-live-auth-20260613-operator.ps1`.
No blocking findings were identified.

The calendar keeps row-level censo provenance on each obligation as
`censo_enrolment_state`, emits the same field through JSON payloads and text
rows, and still refuses strict rendering when live censo-backed enrolment is
missing. Local ready-to-file state remains separate from AEAT submission and
justificante verification: calendar rows carry independent `local`,
`aeat`, and `justificante` axes, and verified justificante status is granted
only after matching persisted metadata or parsed filed-declaration bytes bind
modelo, filing year, typed `Period`, and taxpayer identity.

Typed `core.Period` remains the comparison authority for calendar and filed
evidence. Periods are stringified only at CLI/JSON rendering boundaries and
rehydrated through the typed model validators; evidence keys and justificante
comparisons use `period.registry_token` and typed equality rather than display
string matching.

Pull-only drift and secret handling were rechecked. Production live command
search found no `pull-all` or `capture-all` registration in the scoped
surface; remaining occurrences are negative guards and the live runner's
explicit refusal check. The live-auth runner uses an isolated storage root,
prompts for the secure-storage passphrase with `Read-Host -AsSecureString`,
stores it only in the process environment for the run, and writes redacted
command output to the run log. No hardcoded secret value or plaintext
financial-evidence write was found in the reviewed script or calendar path.

Focused gates passed: ruff over the scoped production and test files; the
overview calendar unit suite with explicit marker selection; the overview
calendar CLI suite with explicit marker selection; and the targeted registry
CLI pull/period guard tests for `pull`, no `pull-all`, command-tree drift, and
filed-list period output.

The broader explicit-marker gate
`uv run pytest src/aeat/application/overview/tests/test_calendar.py
src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py
src/aeat/entrypoints/cli/tests/test_registry_cli.py -m "integration or not
integration" -q` failed 3 of 120 tests. All three failures are existing
registry filed-state tests in `test_registry_cli.py` whose helper now trips
`RegistryValidationError` because previous-filing-bound casilla `05` is
supplied as direct input without matching binding values. The targeted
pull-only and calendar gates above remain green, so this review does not mark
the calendar/censo slice blocked by those unrelated registry-fixture failures.

## LPS-041 | INFO | No blocking findings for Modelo 130 filed-state previous-filing fixture cleanup

Status: PASS.

Reviewer Codex audited the scoped follow-up in
`src/aeat/entrypoints/cli/tests/test_registry_cli.py`. No blocking findings
were identified.

The `_modelo_130_inputs` helper no longer supplies naked casilla `05` as a
direct input. The filed-state fixture still builds the primary filed
observation through `calculate_registry_snapshot`, but casilla `05` now enters
only through the Modelo 130 previous-filing binding
`modelo-130-pagos-fraccionados-anteriores`. The production
`verify_filed_state` path loads the encrypted source observation, converts it
to a registry observation, resolves previous-filing `binding_values`, excludes
unresolved previous-filing bound casillas from raw inputs, and passes the
resolved binding values into the registry runtime. That keeps previous-filing
bindings as the source of truth and avoids the smuggled-bound-casilla shortcut
that previously tripped the registry guard.

The tests remain real-behavior checks rather than tautological calculation
assertions: they persist encrypted filed observations through the production
store, call the application service and CLI, compare only filed-state
verification output for casilla `19`, and exercise the drift path by mutating
the filed observation after the production calculation has been generated.

Focused gates passed:
`uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_compares_local_calculation_to_encrypted_observation src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_cli_loads_secure_observation_refs src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_reports_drift_from_encrypted_observation src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_verify_filed_state_cli_help_resolves_locale_keys -m "integration or not integration" -q`
reported 4 passed. The broader gate recorded red in `LPS-040` now passes:
`uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m "integration or not integration" -q`
reported 120 passed.

## LPS-042 | INFO | No blocking findings for concrete calendar filed-pull warning commands

Status: PASS.

Reviewer Codex audited the scoped follow-up in
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`, and
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`. No blocking
findings were identified.

The `filing.justificante_unverified` and `filing.aeat_evidence_conflict`
warnings now use the pull-only remediation command
`aeat app live filed pull --modelo X --year Y --period P` when the warning
collapses to one typed `core.Period` target. The concrete command renders the
canonical `Period.registry_token`, so display-form strings are not used as the
period authority. When the warning spans more than one affected command target,
the warning falls back to the generic
`aeat app live filed pull --modelo MODELO --year YEAR --period PERIOD`
instruction rather than implying one period-specific pull is sufficient.

The review rechecked the local-vs-AEAT-vs-justificante axes. Local filing
readiness remains separate from AEAT observed or accepted evidence, and
justificante verification still requires matching receipt proof; unverified
AEAT evidence and disagreeing AEAT reference ids only produce strict-mode
warnings/refusals and do not upgrade the justificante axis.

Focused gates passed:
`uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_warns_when_aeat_submission_lacks_verified_justificante src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_uses_generic_justificante_fix_when_multiple_periods_need_pull src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_calendar_entry_warns_when_local_and_filed_history_aeat_references_disagree -m "integration or not integration" -q`
reported 3 passed.

`uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_unverified_aeat_filing src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_conflicting_aeat_evidence_references src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_strict_mode_refuses_imported_csv_register_without_justificante -m "integration or not integration" -q`
reported 3 passed.

`uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q`
reported 70 passed.

## LPS-043 | HIGH | Cross-period expediente hardening leaves valid official fixture paths red

Status: FINDING.

Reviewer Codex audited the scoped cross-period clean-state hardening in
`src/aeat/application/calculations/_cross_period_clean_state.py`,
`src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py`,
`src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`,
and `src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`.

The production hardening is directionally correct: official observation
provenance now requires `aeat_expediente_id` in addition to active
`aeat_register_status` and authenticated identity. The filed-history producer
already emits `aeat_expediente_id`, and the new provenance tests exercise the
missing-expediente blocker without bypassing typed `Period` or justificante CSV
matching.

However, adjacent clean-state fixture helpers that model valid official AEAT
source observations still persist `source_kind="aeat_sede_justificante"` with
`aeat_register_status=ALTA` and `authenticated_identity`, but without
`aeat_expediente_id`. The new blocker therefore keeps those revisions from
reaching `VERIFICADO_COMPLETO` and breaks real-behavior filing gates rather
than only tightening invalid evidence. Confirmed red gates:
`uv run pytest src/aeat/application/modelo/tests/test_file_flow_filing.py -m
"integration or not integration" -q` reported 5 failed and 2 passed, and
`uv run pytest src/aeat/application/modelo/tests/test_verificado_completo_regression.py::test_verify_grants_when_required_casillas_supplied_m130 -m
"integration or not integration" -q` failed because
`granted_verificado_completo` stayed false.

The stale helper locations observed during review are
`src/aeat/application/modelo/tests/_file_flow_support.py`,
`src/aeat/application/modelo/tests/test_verificado_completo_regression.py`,
and a non-failing wallet/export helper in
`src/aeat/application/modelo/tests/test_export.py`. Update the valid official
fixture metadata there to carry an expediente id, or deliberately reclassify
any helper that is meant to model non-official local evidence.

Focused passing gates for the scoped files:
`uv run ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`
reported clean, and
`uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -m
"integration or not integration" -q` reported 41 passed.

## LPS-044 | INFO | PASS for LPS-043 closure, official fixture metadata, and pull-only drift guards

Status: PASS.

Reviewer Codex audited the live-pull-verification-sweep follow-up scope after
LPS-043: cross-period AEAT register-reference hardening closure, valid official
fixture metadata in `src/aeat/application/modelo/tests/_file_flow_support.py`,
`src/aeat/application/modelo/tests/test_verificado_completo_regression.py`, and
`src/aeat/application/modelo/tests/test_export.py`, and CLI drift guards for
`aeat app live filed pull` / `aeat app live expedientes pull` versus forbidden
`pull-all`.

No blocking findings were identified. The official fixture helpers now persist
`aeat_register_status=ALTA`, `aeat_expediente_id`, `aeat_justificante_csv`, and
`authenticated_identity` for valid AEAT-sourced observations. That metadata
matches the hardened cross-period verifier, which now requires active register
provenance, a register reference, and authenticated identity for official source
kinds while still comparing justificante CSV or presentation references when
comparable receipt metadata is available.

The LPS-043 red paths are now green. Focused gates passed:
`uv run pytest src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py::test_verify_grants_when_required_casillas_supplied_m130 src/aeat/application/modelo/tests/test_export.py::test_export_modelo_303_wallet_only_revision_writes_fichero_with_redacted_wallet_provenance -m "integration or not integration" -q`
reported 9 passed, and
`uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -m "integration or not integration" -q`
reported 41 passed.

The pull-only CLI drift gates also passed. `aeat app live filed pull --help`
and `aeat app live expedientes pull --help` expose bounded single and bulk
options under `pull`; `aeat app live filed pull-all --help` and
`aeat app live expedientes pull-all --help` both fail with `No such command
'pull-all'. Did you mean 'pull'?`. The targeted registry guard lane
`uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_capture_sources_cli_help_resolves_without_registry_alias src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m "integration or not integration" -q`
reported 4 passed. The filed rendering guard reported 3 passed, the
expedientes subgroup guard reported 3 passed, and the root fallback/help guard
reported 46 passed.

Ruff passed over the scoped production and test files:
`src/aeat/application/calculations/_cross_period_clean_state.py`,
`src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py`,
the three reviewed Modelo fixture files, `test_file_flow_filing.py`,
`src/aeat/entrypoints/cli/_app_live.py`,
`src/aeat/entrypoints/cli/_app_live_expedientes_cli.py`, and
`src/aeat/entrypoints/cli/tests/test_registry_cli.py`.

Residual risk: the broader `test_live_read_subgroups.py` suite still has two
IVA-wallet watchdog failures in process-command inspection on this Windows run
because subprocess output decoding left `completed.stdout` as `None`; the
expedientes subgroup from the same file passed and the failing cases are not in
the filed/expedientes `pull-all` drift slice. A text search also found stale
`pull-all` references only in ignored generated `docs/_build` artefacts, while
the inspected source docs, CLI-reference inputs, plan tracking, and current
exec records do not ask operators to use `pull-all`.

## LPS-045 | INFO | PASS for isolated live-auth runner and blocker update

Status: PASS.

Reviewer Codex audited the final live-auth runner/blocker update in
`var/aeat/live-auth-run/run-live-auth-20260613-operator.ps1`, the isolated
timeout exec record, the live-auth blocker audit, and the active plan/index
state. No blocking findings were identified.

The runner sets `AEAT_LOCAL_STORAGE_ROOT`,
`AEAT_SECRET_STORE_DIR`, and `AEAT_BLOB_STORE_DIR` under the same isolated
`var/live-auth-20260613-operator-isolated` root after loading `env/.env`, so
the run does not rely on the shared default profile, secret store, or blob
store. Secret storage is file-backed for this run, the secure-storage
passphrase is accepted through the process environment or an interactive
`Read-Host -AsSecureString` prompt, and the redacted log path stays under
`var/aeat/live-auth-run`.

The authenticated command sequence uses pull-only acquisition surfaces:
`config profile censo pull`, `app live filed pull`, `app live expedientes pull`,
`app live notifications pull`, and `app live justificante pull`. Filed and
expedientes all-model coverage remains expressed as bounded options on
`pull`; the reviewed runner contains no `pull-all` invocation.

The latest exec record and blocker audit honestly report the outcome as a
Cl@ve completion timeout. They claim local setup success for isolated profile
creation, provider configuration, identity alignment, encrypted `master.key`,
active-profile pointer, bucket database, and token directory, but they do not
claim positive live Modelo 036/censo, filed-history, justificante,
notification, expediente, or live-backed calendar evidence. The record also
states that downstream filed, expedientes, notifications, justificante, and
calendar commands were stopped before repeating the same auth timeout.

Plan/index consistency was rechecked. The feature index includes the
`2026-06-13` isolated-timeout exec record, and the active plan keeps
`W02.P04.S10` and `W03.P06.S26` open. That matches the blocker evidence:
`W02.P03.S08` remains checked for authentication substrate evidence and
recorded external blockers, while censo-positive proof and the manual
authenticated sweep are not overclosed.

Residual risk: this was a document/script review only. I did not rerun the
visible PowerShell runner or perform live AEAT authentication, so the next
acceptance risk remains operator-mediated Cl@ve completion and AEAT returning
readable live censo/filed/justificante/calendar evidence after authentication.

## LPS-046 | HIGH | Verified Modelo-record receipt timestamp can be overwritten by local capture time

Status: FINDING.

Reviewer Codex audited the live-pull-verification-sweep calendar justificante
presented-at slice in `src/aeat/application/overview/_calendar.py`,
`src/aeat/entrypoints/cli/_overview.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`,
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`, and the
calendar justificante presented-at exec record.

The direct Modelo-record path sets `aeat_submitted_at` from
`Justificante.presented_at` only after matching persisted justificante metadata,
and accepted-but-unverified Modelo-record evidence leaves
`aeat_submitted_at=None`. Text output also renders the field when present, and
the exec record does not claim a successful live AEAT read.

However, the merged evidence path can still replace that official receipt
timestamp. `calendar_filing_evidence_from_sources` merges Modelo records before
calculation observations. `_filing_evidence_from_calculation_observation` marks
a calculation observation as `justificante_verified` when metadata points to a
matching persisted justificante, but it sets `aeat_submitted_at` from the
observation envelope's `captured_at`. Because `_stronger_filing_evidence` lets
an equal-ranked later `justificante_verified` candidate win and copies
`candidate.aeat_submitted_at`, a verified Modelo-record row carrying
`Justificante.presented_at` can be overwritten by the local calculation capture
timestamp for the same modelo, filing year, and typed `Period`.

I confirmed this with an in-memory probe using the reviewed helpers: a verified
Modelo 303 record backed by `JUST-303-2025-1T` and a same-obligation
`aeat_sede_justificante` calculation observation returned
`aeat_submitted_at=2025-04-16T12:00:00+00:00` and
`evidence_source=aeat_sede_justificante`, even though the matched
`Justificante.presented_at` fixture is `2025-04-15T09:30:00+00:00`.

This violates the slice intent that verified Modelo-record justificante
evidence use the official receipt presentation timestamp, and it can present a
local capture/import time as an official AEAT submission time in both JSON and
text calendar output. Add coverage for the mixed Modelo-record plus calculation
observation merge, and make verified calculation-observation rows source their
submission timestamp from matching justificante metadata or preserve the
existing official receipt timestamp instead of promoting `captured_at`.

## LPS-047 | INFO | LPS-046 resolved for calendar justificante submitted-at merge

Status: PASS. LPS-046 is resolved.

Reviewer Codex audited the LPS-046 fix scope in
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`, the
live-pull-verification-sweep plan, prior audit entry, and the
calendar-justificante-presented-at review-fix exec record. No blocking findings
were identified.

The verified Modelo-record path now sets `aeat_submitted_at` from the matched
persisted `Justificante.presented_at`. Verified calculation observations now
resolve the matched `Justificante` object and source `aeat_submitted_at` from
that same `presented_at` value instead of the observation envelope
`captured_at`. When a same-obligation, equal-ranked verified calculation
observation is merged after a verified Modelo record, `_merged_aeat_submitted_at`
preserves the existing verified receipt timestamp, so the old overwrite path is
closed.

Unverified observed evidence behavior remains intact: official calculation
observations without matching persisted justificante metadata still project as
`submitted_observed`, retain `justificante_verified=false`, and keep the local
capture timestamp only for the unverified observed AEAT evidence row. Period
keying remains typed through `core.Period`: fallback registry-token strings are
rehydrated via `Period.from_year_and_code`, merge keys use
`period.registry_token`, and the regression imports and compares the production
`Period` type directly.

No production pull-all/capture-all drift was found in the reviewed surface.
`rg -n "pull-all|capture-all|pull_all|capture_all" src/aeat --glob
'!**/tests/**' --glob '!**/__pycache__/**'` returned no production matches, and
the existing CLI guard lane still rejects the forbidden aliases. I did not run
live AEAT authentication and this review does not claim live AEAT success.

Focused local gates run during review:
`uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_official_calculation_observation_source_with_matching_justificante_is_verified src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_verified_modelo_record_receipt_time_survives_calculation_observation_merge -q --tb=short`
reported 2 passed;
`uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q --tb=short`
reported 52 passed; and
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`
reported 3 passed.

## LPS-048 | INFO | PASS for bulk filed pull limit and live-auth retry slice

Status: PASS.

Reviewer Codex audited the latest live-pull-verification-sweep bulk filed pull
limit and live-auth retry slice in `src/aeat/application/live/_filed_data_capture.py`,
`src/aeat/entrypoints/cli/_app_live.py`,
`src/aeat/application/live/tests/test_filed_bulk_capture.py`,
`src/aeat/entrypoints/cli/tests/test_registry_cli.py`,
`var/aeat/live-auth-run/run-live-auth-20260613-operator.ps1`, the active
plan, the S18/S10 exec record, and this rolling audit. No blocking findings
were identified.

Bulk filed acquisition remains under the existing `app live filed pull` verb.
The CLI accepts `--from-year`, `--to-year`, and `--limit` together in bulk
mode, rejects `--period` and `--expediente` outside single-modelo/year mode,
and passes the validated `limit` to `capture_filed_data_bulk`. No production
`pull-all`, `capture-all`, `pull_all`, or `capture_all` surface was found.

Backend limit handling is coherent and fail-closed. The bulk backend applies
the limit only after the authenticated register rows are returned for a
supported modelo/year, slices the current batch to the remaining capture
budget, and stops once persisted observations reach the limit. Unsupported
modelos remain local typed failures and do not force authentication or local
writes. Register walks are bounded by `aeat_live_filed_register_walk_timeout_ms`
and timeout with modelo/year progress context.

The live-auth runner uses the isolated storage root and sets the fallback
`AEAT_CLAVE_MOVIL_TIMEOUT_MS` to `120000` only when the operator environment did
not already provide a value. That matches the settings default and maximum cap,
so an absent `.env` no longer injects an invalid timeout. The runner invokes
bounded live read commands through `pull`, including
`app live filed pull --from-year 2025 --to-year 2026 --limit 50`, and contains
no forbidden bulk alias invocation.

The exec record is honest about the live outcome. It records Cl@ve completion
timeouts as the remaining blocker, keeps the live censo/filed/justificante and
submitted-calendar proof steps open, and does not claim a successful live
Modelo 036/censo snapshot, filed history, justificante, notification,
expediente, or live-backed calendar capture. The calendar note is explicitly a
local projection with `events=0`, `censo_enrolment=unverified`, and
`aeat=not_observed`.

Focused local gates run during review:
`uv run pytest src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_bulk_pull_accepts_limit_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m "integration or not integration" -q --tb=short`
reported 9 passed; `uv run ruff check src/aeat/application/live/_filed_data_capture.py src/aeat/entrypoints/cli/_app_live.py src/aeat/application/live/tests/test_filed_bulk_capture.py src/aeat/entrypoints/cli/tests/test_registry_cli.py`
reported all checks passed; and
`rg -n "pull-all|capture-all|pull_all|capture_all" src/aeat/entrypoints src/aeat/application var/aeat/live-auth-run/run-live-auth-20260613-operator.ps1 --glob "!**/tests/**" --glob "!**/__pycache__/**"`
returned no production matches. I did not run live AEAT authentication.

## LPS-049 | INFO | PASS for calendar Modelo-record event presented-at slice

Status: PASS.

Reviewer Codex audited the latest live-pull-verification-sweep calendar
Modelo-record event presented-at slice in
`src/aeat/application/overview/_calendar_models.py`,
`src/aeat/application/overview/_calendar.py`,
`src/aeat/entrypoints/cli/_overview_payloads.py`,
`src/aeat/entrypoints/cli/_overview.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`,
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`, the active
plan, the presented-at exec record, and this rolling audit. No blocking
findings were identified.

Verified Modelo-record filing events now derive their calendar `event_date`
and `aeat_submitted_at` from the matched persisted
`Justificante.presented_at`. Local ready-to-file Modelo records still use the
local `record.filed_at.date()` event date, report `aeat_submission_state` as
`not_observed`, and leave `aeat_submitted_at=None`, so local readiness is not
presented as AEAT submission. The earlier LPS-046 overwrite path remains
closed: verified calculation-observation evidence also resolves the matched
`Justificante.presented_at`, and equal-ranked verified evidence merging
preserves the existing official receipt timestamp instead of replacing it with
local capture time.

JSON and text payloads remain aligned. `OverviewCalendarFilingEvidence` and
`OverviewCalendarEvent` both expose optional `aeat_submitted_at`, the overview
JSON payload schemas carry the same field for entry filing evidence and
calendar events, and the text renderer prints it for both row evidence and
event lines only when present. Typed `core.Period` remains the comparison and
payload authority: calendar models hydrate serialized periods back into
`Period`, event/evidence keys compare filing year plus registry token from
typed period objects, and the focused tests import and compare the production
`Period` type directly.

The exec record remains honest about live scope. It records local
calendar/modelo evidence hardening and local gates only, and explicitly does
not claim successful live AEAT authentication or a live AEAT read; the Cl@ve
completion blocker remains open for live-backed censo, filed-history,
justificante, notification, expediente, and submitted-calendar proof.

No pull-all or capture-all production drift was found. `rg -n
"pull-all|capture-all|pull_all|capture_all" src/aeat --glob "!**/tests/**"
--glob "!**/__pycache__/**"` returned no production matches.

Focused local gates run during review:
`uv run pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q --tb=short`
reported 71 passed, and
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q --tb=short`
reported 94 passed. I did not run live AEAT authentication.

## LPS-050 | INFO | PASS for expedientes event submitted-at slice

Status: PASS.

Reviewer Codex audited the latest live-pull-verification-sweep expedientes
event submitted-at slice in `src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/tests/test_calendar.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`,
`src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`,
`src/aeat/application/overview/_calendar_models.py`,
`src/aeat/entrypoints/cli/_overview_payloads.py`,
`src/aeat/entrypoints/cli/_overview.py`, the active plan, the S27/S29 exec
record, and this rolling audit. No blocking findings were identified.

Active expedientes/declaracion filing events now preserve
`Declaracion.presented_at` as `OverviewCalendarEvent.aeat_submitted_at`.
Event-derived filing evidence uses `event.aeat_submitted_at` when present, so
the official AEAT submission time is not downgraded to midnight on
`event_date`. Filed-history and justificante-backed enrichment still upgrades
matching calendar events to stronger AEAT submission states and carries the
stronger evidence timestamp onto the event.

JSON and text output remain schema aligned. `OverviewCalendarFilingEvidence`
and `OverviewCalendarEvent` both expose optional `aeat_submitted_at`, the CLI
payload schemas carry the same field for filing evidence and event payloads,
and the text renderer emits it only when present. Typed `core.Period` remains
the comparison authority for event/evidence keys and tests import the
production `Period` type directly.

No production `pull-all`, `capture-all`, `pull_all`, or `capture_all` drift was
found in `src/aeat`. The focused CLI guard lane still rejects the forbidden
aliases and keeps bulk filed/expedientes acquisition under `pull`.

Residual risk: this was a local, non-live review. I did not run live AEAT
authentication and do not claim successful live censo, filed-history,
justificante, notification, expediente, or live-backed calendar proof. The
operator-mediated Cl@ve completion timeout blocker remains open.

Focused local gates run during review:
`uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
reported all checks passed;
`uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short`
reported 116 passed;
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q --tb=short`
reported 94 passed;
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`
reported 3 passed; and
`rg -n "pull-all|capture-all|pull_all|capture_all" src/aeat --glob "!**/tests/**" --glob "!**/__pycache__/**"`
returned no production matches.

## LPS-051 | HIGH | Live-auth runner seeds an invalid Clave Movil timeout

Status: REVISION REQUIRED.

`var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1:62` through
`var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1:64` sets the
fallback `AEAT_CLAVE_MOVIL_TIMEOUT_MS` to `180000` when the operator
environment has not already provided a value. The production settings schema
caps `aeat_clave_movil_timeout_ms` at `120000`, so this default prevents
`Settings()` from loading before any authenticated read can run. A non-live
probe with `AEAT_CLAVE_MOVIL_TIMEOUT_MS=180000` failed with the Pydantic
validation error `Input should be less than or equal to 120000`.

This is a blocker for the manual live-auth runner because the reviewed script
is part of the operator retry surface and can fail during local configuration
bootstrap rather than reaching the intended `auth_completion_timeout` live
blocker path. It also conflicts with the exec record's statement that the run
timed out after the configured 120 seconds. Change the runner fallback to a
schema-valid value, expected `120000`, or remove the override so the settings
default applies.

The scoped Python auth hardening otherwise preserves the own-name-only
representation gate. `_continue_own_name_representation` still routes through
the remote-operation allow-list before any browser action, refuses an already
checked representative radio with `representation_gate_representative_selected`,
skips the fragile `#propio`/label click when the own-name radio is already
checked, dismisses only visible `#alertsModal.show` modals, and tries the
capitalized `Continuar` modal button before the configured lowercase token and
footer fallback. I did not find a represented-party selection path or an AEAT
remote mutation path in the reviewed Python delta.

The focused regression for the live-observed shape is meaningful within the
existing protocol-test style: it exercises the checked `#propio` radio, unchecked
`#representante`, visible `#alertsModal.show`, and capitalized `Continuar`
button, and asserts that only the modal continue button plus the representation
submit button are clicked. No raw diagnostic HTML is logged by the delta; page
HTML is parsed locally for structural selectors only, and existing diagnostic
HTML capture remains in encrypted session-class storage.

No production `pull-all`, `capture-all`, `pull_all`, or `capture_all` drift was
found in the reviewed auth files or runner. The exec record remains honest that
no successful live AEAT censo, filed-history, justificante, notification,
expediente, or live-backed calendar proof was captured, and keeps the
operator-mediated `auth_completion_timeout` blocker explicit.

Focused local gates run during review:
`uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil_page_flow.py src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py`
reported all checks passed;
`uv run pytest -m "" src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py -k "representation_dispatcher" -q --tb=short`
reported 4 passed and 37 deselected;
`$env:AEAT_CLAVE_MOVIL_TIMEOUT_MS='180000'; uv run python -c "from aeat.core.config import Settings; Settings(); print('settings-ok')"`
failed with the expected settings validation error; and
`rg -n "pull-all|capture-all|pull_all|capture_all" src/aeat/adapters/outbound/aeat/auth/_clave_movil_page_flow.py src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1`
returned no matches. I did not run live AEAT authentication.

## LPS-052 | INFO | PASS for LPS-051 timeout fallback resolution

Status: PASS for LPS-051 resolution.

`var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1:62` through
`var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1:64` now only seeds
`AEAT_CLAVE_MOVIL_TIMEOUT_MS` when the operator environment has not provided it,
and the seeded value is `120000`. That matches the production settings schema
cap at `src/aeat/core/config.py:675` through `src/aeat/core/config.py:678`,
where `aeat_clave_movil_timeout_ms` defaults to `120_000` and is constrained
with `le=120_000`.

The reviewed Python auth slice remains consistent with the expected timeout
surface: the attempt context regression still records `timeout_ms` as
`120_000`, and the exec record remains honest that no successful live AEAT read
was captured. The remaining blocker is still operator-mediated Clave Movil
completion for diagnostic `auth_completion_timeout`; I did not run live auth.

Focused local gates run during follow-up review:
`[System.Management.Automation.Language.Parser]::ParseFile(...)` over
`var/aeat/live-auth-run/run-live-auth-20260613-ready-auth.ps1` reported
PowerShell syntax ok;
`uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil_page_flow.py src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py`
reported all checks passed; and
`uv run pytest -m "" src/aeat/adapters/outbound/aeat/auth/tests/test_clave_movil.py -q --tb=short`
reported 41 passed.

## LPS-053 | INFO | PASS for calendar calculation-observation register-reference guard

Status: PASS.

Reviewer Codex audited the latest live-pull-verification-sweep slice in
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`,
`src/aeat/entrypoints/cli/_app_live.py`,
`src/aeat/entrypoints/cli/tests/test_registry_cli.py`, the active plan, and
the code-review template. No blocking findings were identified.

Official calculation-observation projection now refuses an AEAT submission row
unless `source_metadata.aeat_expediente_id` is present after trimming. The gate
runs after official source-kind, metadata, and active `ALTA` checks and before
any calendar evidence row is constructed, so a Sede calculation observation
with only status, authenticated identity, and justificante CSV metadata does
not become submission evidence. The regression
`test_sede_calculation_observation_without_register_reference_is_not_submission_evidence`
covers that exact shape.

The typed-period boundary remains intact in the reviewed path. Calculation
observations hydrate string registry tokens through `Period.from_year_and_code`
or preserve an existing `Period` only when its filing year matches the
observation year; merge keys and CLI output continue to use
`period.registry_token`. The focused roundtrip regression imports and validates
the production `Period` type rather than mirroring period logic.

The CLI drift watch remains clean for this slice. Filed bulk acquisition stays
under `app live filed pull`, `pull-sources` remains the source-acquisition
verb, and the command-tree tests reject `pull-all` and `capture-all` for both
filed and expedientes surfaces. A scoped production search over
`src/aeat/application/overview` and `src/aeat/entrypoints/cli` found no
production `pull-all`, `capture-all`, `pull_all`, or `capture_all` matches.

Focused local gates run during review:
`uv run pytest -m "" src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_sede_calculation_observation_without_register_reference_is_not_submission_evidence src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_official_calculation_observation_sources_are_calendar_submission_evidence src/aeat/application/overview/tests/test_calendar_filing_evidence.py::test_period_bearing_calendar_models_roundtrip_through_json -q --tb=short`
reported 4 passed;
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`
reported 3 passed; and
`rg -n "pull-all|capture-all|pull_all|capture_all" src/aeat/application/overview src/aeat/entrypoints/cli --glob "!**/tests/**" --glob "!**/__pycache__/**"`
returned no production matches.

## LPS-054 | INFO | PASS for verified live justificante capture calendar enrolment

Status: PASS.

Reviewer Codex audited the direct justificante capture enrolment slice in
`src/aeat/application/live/_justificante.py`,
`src/aeat/application/live/__init__.py`,
`src/aeat/application/overview/_calendar.py`,
`src/aeat/application/overview/__init__.py`,
`src/aeat/entrypoints/cli/_overview.py`,
`src/aeat/application/overview/tests/test_calendar_filing_evidence.py`, and
`src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`.
No blocking findings were identified.

The reviewed design preserves the two-axis filing semantics. A direct live
justificante capture now persists parsed receipt metadata even when no local
`ModeloRecord` exists, but it does not create or stamp a local filing record.
The overview calendar can therefore show an AEAT-side
`justificante_verified` submission while retaining
`local_filing_state=not_ready_to_file` unless the app already has a separate
ready-to-file Modelo record.

The calendar projection is gated by active capture snapshots and matching
persisted Justificante metadata by CSV, modelo, filing year, typed `Period`,
and expected taxpayer identity. Raw captured PDFs are not enough to become
calendar filing evidence. The direct capture path still refuses local
filing-record conflicts in `register_capture_as_filing_evidence`, and the
calendar merge path preserves conflict references when local AEAT evidence and
new live-capture evidence disagree.

The CLI drift watch remains clean for this slice. Filed bulk acquisition stays
under `app live filed pull`, direct justificante acquisition stays under
`app live justificante pull`, and scoped search found no production `pull-all`,
`pull_all`, `capture-all`, or `capture_all` matches in the reviewed live,
overview, and CLI surfaces.

Focused local gates run during review:
`uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/__init__.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/__init__.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`
reported all checks passed;
`uv run pytest -m "" src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q --tb=short`
reported 56 passed;
`uv run pytest -m "" src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q --tb=short`
reported 20 passed;
`uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short`
reported 120 passed;
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`
reported 2 passed;
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -q --tb=short`
reported 4 passed;
`uv run pytest -m "" src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_resolution.py -q --tb=short`
reported 13 passed; and the three CLI help probes for live filed, live
justificante, and overview calendar completed successfully.

Live AEAT verification remains open. The visible runner process is still
waiting at the operator passphrase/auth stage, and no fresh live censo,
filed-history, justificante, notification, expediente, or live-backed calendar
proof was captured for this review entry.

## LPS-055 | INFO | PASS for explicit live justificante metadata-enrolment output contract

Status: PASS.

Reviewer Codex audited the continuation slice in
`src/aeat/application/live/__init__.py`,
`src/aeat/entrypoints/cli/_app_live_payloads.py`,
`src/aeat/entrypoints/cli/_app_live_justificante_cli.py`, and
`src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`.
No blocking findings were identified.

The reviewed change makes the live justificante pull outcome explicit about
three separate states: snapshot persisted, parsed Justificante metadata
registered, and local ModeloRecord evidence stamped. This avoids the prior
operator ambiguity where an unstamped local filing could still have a
calendar-usable AEAT receipt enrolled. The CLI payload now exposes
`justificante_metadata_registered`, `calendar_evidence_available`, and
`modelo_filing_record_required`; text output mirrors those fields and gives the
external baseline import command shape when a full Modelo filing record still
needs submitted casilla values.

The cross-period clean-state invariant remains intact. A direct justificante
capture alone does not create a calculation revision, verification report, or
ModeloRecord; it only makes the AEAT receipt available to the calendar and to
the later `modelo filing-record import` path. The existing import action still
requires matching Justificante metadata by CSV/model/year/typed Period/taxpayer
before accepting `aeat_live_capture` evidence.

Focused local gates run during review:
`uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/_justificante.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/overview/_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py`
reported all checks passed;
`uv run pytest -m "" src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py -q --tb=short`
reported 24 passed;
`uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q --tb=short`
reported 94 passed;
`uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py -q --tb=short`
reported 148 passed; and the registry command-tree guard lane reported 4
passed for the pull-only checks.

Live AEAT verification remains open. The runner log still ends at
`runner initialized; waiting for operator passphrase`, so no fresh live censo,
filed-history, justificante, notification, expediente, or live-backed calendar
proof was captured for this continuation.
