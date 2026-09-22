# Taxpayer profile and onboarding: preflight brief

Brief ID: PROFILE-01. Revision: 0.1. Date: 2026-09-21.
Session name: `taxpayer-profile`. Goal: let a user configure, review and maintain the correct taxpayer/entity context through either CLI or TUI, persist it securely, and use it consistently across the existing tax and calendar workflows.
Provider, lead model, cc number and UUID: pending user assignment. Provider-neutral; no implementation session has been launched by this brief.
Required instructions: [session policy](session-policy.md) revision 1.7 and [ACCEPTANCE-01](acceptance-pattern.md) revision 1.6. Use mandatory bounded Luna Max discovery, shared acceptance plumbing and the global verification reservation list.
Status: two bounded Luna Max source reports and targeted coordinator checks complete; official census distinctions checked. Source-only findings, not runtime acceptance. No product changes, tests, rendered UI checks, private-store reads or live calls. Adviser consultation could not start because the session agent-thread limit was reached; no adviser review is claimed and no new architecture is decided here.

## Scope and boundaries

Start with the common-regime self-employed taxpayer used by INCOME-01 and IVA-01. Add a small contrast set of actually supported entity kinds, territories and regimes to prove discrimination and refusal; this is not authorization to implement every tax jurisdiction or regime. Cover the profile facts needed by retenciones, assets and calendar without taking ownership of their calculation engines.

The core journey is: create/select the intended taxpayer, understand missing facts, configure activities and applicable tax circumstances, save, reopen from a fresh process in either frontend, review provenance, and safely maintain changes. User-facing profile completeness must be tied to the intended operation, not a blanket promise that every return is ready.

Keep these concepts distinct:

- Product storage profile/bucket, legal taxpayer identity, authenticated operator and represented taxpayer. A display name or active UI selection is not a substitute for durable entity identity.
- Local configuration, imported AEAT census evidence, registry-derived applicability and filing-specific facts. Editing local settings does not amend the official census.
- Identity facts, local encryption/unlock credentials, AEAT authentication configuration and legal representation authority. Selecting a representative is not proof of an active AEAT authorization.
- Fact effective date, observation/import time, current evaluation date and tax period. A current snapshot is not automatically historical evidence.
- Tax residence, fiscal address, notification address, activity premises and transaction territory. Do not use one address as an unproved substitute for every tax jurisdiction.

Official grounding: AEAT's census services separately cover addresses, activities/premises, representatives and tax circumstances. Its consultation guidance exposes activity start/end dates, obligations with periodicity/status and access dependent on the taxpayer and representation permissions. Use these as domain distinctions, not proof that Cadrumo implements every field. [AEAT census data services](https://sede.agenciatributaria.gob.es/Sede/censos-nif-domicilio-fiscal/tramites-censales-relacionados-empresarios-profesionales-retenedores/datos-censales.html), [AEAT census consultation and representation](https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/otros-servicios-ayuda-tecnica/datos-censales.html).

Live testing remains blocked. No authentication, remote census modification, filing submission, credential discovery or real-profile mutation is authorized. Review existing import/live integration source and prove offline behavior with synthetic evidence. Local profile editing must never trigger an implicit live action.

## Existing implementation and reuse map

Source anchor observed: `f72ef01f760f87bbe36e83016ed6393921335090`, worktree `tui/modelo`. The working tree contains concurrent tax, profile-history and frontend changes; this anchor is orientation, not a completeness oracle. Refresh only affected deltas at dispatch. Reports: `profile_domain_map` and `profile_frontend_map`, Luna Max; their decision-relevant findings are retained here. Paths below are relative to `src/cadrumo/`.

| Existing owner | Source evidence | Scope and limits |
| --- | --- | --- |
| Registry-defined profile | `_data/registry/cadrumo/user_profile/schema.toml:1`; `domain/user_profile/schema.py:360`, `:394` | Schema version 6; canonical sections/field lookup. Broad existing coverage includes identity, taxpayer type, preferences, auth, contact/residence/censo, activities, attribution, IRPF/IVA/withholding, family, properties, usage and provenance. A declared field does not establish an installed writer or consumer. |
| Facts, record and snapshot | `domain/user_profile/values.py:237`, `:319`, `:366`, `:502`, `:560` | Typed facts include source and validity windows; record has immutable profile UUID, setup state and digest-linked revisions. Immutable COMPLETE-only snapshot type and canonical hash already exist. Do not add a parallel DTO or snapshot mechanism. |
| Secure current record and event history | `application/user_profile/capsule_record.py:296`, `:351`, `:461`, `:498`, `:624` | One authenticated current record; guarded replacement and append-only event witness. Event revision/digests are not full historical fact payloads. Do not advertise event history as reconstructable tax-period snapshots without proving that path. |
| Selection and entity isolation | `application/user_profile/profile_repository.py:118`; `core/bucket_pointer.py:34`, `:188`; `domain/user_profile/values.py:218` | Stable UUID keys bucket/custody identity; labels are mutable. Selection resolves exact UUID or unique label. Active pointer has selected/absent state and transition revision. Exercise ambiguous labels and selection changes through existing contracts. |
| Shared mutation/validation | `application/user_profile/fact_write.py:69`, `:169`; `application/user_profile/overview.py:172`, `:665` | Canonical manager mutation delegates to fact changes, validation and guarded writes; incomplete profiles can be edited incrementally. Both frontends must retain this owner. |
| Effective-value projection | `application/user_profile/projections.py:145`, `:196`, `:220` | Latest `valid_from` wins; these projections do not accept an as-of date and do not enforce `valid_to`. Validation reports ended windows. This is not period-as-of historical resolution. |
| Filing integration | `application/modelo/profile_binding.py:1580`; `application/user_profile/custody_ports.py:285`; `adapters/persistence/storage/profile_custody.py:257` | Profile-binding fallback loads the current record; snapshot persistence interfaces exist. The scoped audit did not find a production snapshot create/save caller. Establish actual filing pinning before claiming it exists or commissioning another store. |
| Live census reconciliation | `application/user_profile/censo_sync.py:50`, `:69`, `:80`, `:268`; `cotejo_apply.py:184` | Owns identity guard, source-aware reconciliation and reviewed application. Adoptable live paths are three fiscal-address fields, not a full import of regimes/obligations. Operator disagreements remain visible, prior censo values can refresh, explicit clears are protected. |
| Census certificate transport | `entrypoints/cli/config/_censo_transport.py:63`; `adapters/inbound/censo/parser.py:26` | CLI import/apply plumbing exists, but the real byte parser currently refuses every document: non-PDF or extraction-unpinned. Certificate ingestion is therefore not an implemented happy path. Do not prove it using a stubbed parser or invent a PDF layout. |

### Frontend capability and usability

- CLI has `config profile create`, `edit`, `view`, `validate`, `complete-setup`, `delete`, `list`, `status`, and `censo import/pull` in `entrypoints/cli/config/profile_command_specs.py:457` and `_profile_inventory_specs.py:29`. Dynamic create/edit flags share setup projection (`profile_command_specs.py:263`, `:397`; `_manager_dispatch.py:43`). No dedicated `profile select` leaf was found in the inspected graph; determine the existing session/login selection mechanism rather than inventing that command.
- CLI registration can seed taxpayer facts and starts INCOMPLETE (`scripted_registration.py:205`). TUI registration seeds output language only (`entrypoints/tui/secret/registration.py:854`); subsequent taxpayer editing is in `workbench.profile`, reached through Account Profile. Different step counts are acceptable if the same complete outcome is reachable and explained.
- TUI shows schema fields and required gaps. Enum/boolean choices exist; other types use a generic text input (`entrypoints/tui/profile/overview.py:567`). Verify date/number/collection/conditional fields as actual tasks, not merely row presence. Complete Setup revalidates (`:907`; CLI `_complete_setup_cli.py:66`).
- TUI edits persist one field immediately on a worker (`profile/overview.py:856`), with an in-flight guard and reloaded overview; modal cancellation does not undo already-saved fields. CLI interactive edit stages changes and discards interrupted staged edits (`application/wizard/commands.py:1722`, `:2028`). Preserve clear, honest save semantics rather than forcing identical interaction mechanics.
- TUI change-user is F5/CHANGE_USER through LoginScreen (`entrypoints/tui/app.py:397`). Prove that an in-flight write cannot land in the newly selected entity and that caches/views refresh; source existence does not prove this transition.
- TUI profile source cards have an injected launch-door contract, but the inspected installed path supplies no launch door (`profile/overview.py:479`). This is a census-acquisition usability/parity gap to confirm at installed composition, not a reason to duplicate ingestion.
- CLI censo pull has preview and reviewed-apply branches (`_censo_transport.py:112`, `:140`); module prose still describes an older apply refusal. Follow executable registration/branches and test behavior, not that stale prose. Neither branch was exercised. Certificate import refusal is independently confirmed in the parser, not inferred from its CLI registration.

### Priority risks and scope decisions

1. **Historical facts and filing pinning:** schema windows, digest history and snapshot types already exist but do not establish historical resolution or production pinning. Coordinate PR6 with CALENDAR-01 before changes. Extending temporal semantics across callers may require a defined architectural decision; the principal must not invent it.
2. **Cleared facts:** censo reconciliation deliberately preserves clears, whereas the flat value projection filters out null values. Test a later clear after an older dated value across manager, validation and filing consumers for accidental resurfacing. This is a source-supported test target, not a reproduced defect.
3. **Partial onboarding and collection fields:** do not treat the generic editor as proof every required fact/repeatable row can be created, modified and removed. First produce the bounded field/write/consumer matrix for the autonomo workflow.
4. **Census import:** parser happy-path support is missing. A real-format extractor requires grounded, lawfully supplied sample/schema evidence and secure handling. Until available, retain the explicit refusal and mark this subcase blocked; offline typed mapping tests are not certificate ingestion proof. New represented-taxpayer access or broad regime scraping is outside current scope.
5. **Concurrent state:** current-record writes already use guarded replacement. Reuse that mechanism; test stale edits, in-flight acquisition, active-user switch and failure recovery before proposing new locking or persistence.

## Directed verification candidates — NOT RUN

These source names were checked, but not collected or executed:

- `src/cadrumo/domain/user_profile/tests/test_values.py::test_snapshot_is_canonical_and_rejects_incomplete_profiles`
- `src/cadrumo/application/user_profile/tests/test_effective_window_end_is_reported_not_enforced.py::test_a_closed_window_still_projects_its_value` documents the current boundary; it does not prove historical correctness.
- `src/cadrumo/entrypoints/cli/config/tests/test_profile_edit_verb.py::test_an_incomplete_profile_accepts_one_field_at_a_time`
- `src/cadrumo/entrypoints/tui/tests/test_manager_screen.py::test_editing_a_row_writes_through_to_the_encrypted_record`
- `src/cadrumo/entrypoints/tui/tests/test_registration_screen.py::test_typing_credentials_and_pressing_create_makes_a_live_profile` uses a synthetic local profile; “live” in this test name does not mean live AEAT.
- Additional owning contract suite: `src/cadrumo/application/user_profile/tests/test_event_emission_contract.py`; select only affected nodes after a bounded delta report.

The implementation lead identifies missing PR-specific tests and current markers before reserving `uv run pytest -n 0 <exact-node>` with explicit applicable marker selection. Do not run the entire profile or tax lane just to find a small test. Installed runtime setup remains a separately authorized implementation responsibility; no install or setup was attempted by this preflight.

## Acceptance outcomes

Use an explicit as-of date and programmatically selected supported tax year through the existing resolver. Pin authority/context once, derive fixture dates from it, and permit an explicit year override. Do not hardcode the current year into stored taxpayer facts or infer legal support from date arithmetic. Use independent expected facts and application outcomes, not expected values copied from the implementation.

| ID | Scenario | Required proof |
| --- | --- | --- |
| PR1 | First-run and incomplete setup | Both frontends explain prerequisites and missing facts, support the existing secure setup flow, and distinguish an empty profile from a valid taxpayer with no applicable obligations. No manufactured NIF, regime, dates or zero-valued tax facts. |
| PR2 | Identity and selection | Create/select two synthetic entities with distinct identities; duplicate or conflicting identities receive deterministic handling. Active taxpayer is visible. Switching and fresh-process reopening do not leak facts, financial records, credentials or cached results across entities. |
| PR3 | Field capability and parity | Build a bounded field matrix from the actual schema: readable, writable, imported-only, derived, secret or unsupported; identify CLI/TUI path and consumer for each filing-critical field. Typed options, units and clear/unset behavior preserve canonical meaning. Raw JSON transport alone is not proof of usable configuration. |
| PR4 | Activities and tax circumstances | Verify supported multi-activity, regime, territory, payer and other obligation-driving facts through the existing contracts. Unknown/conflicting facts remain explicit. A profile preference or view filter cannot override legal applicability or silently enable an unsupported regime. |
| PR5 | Edits, cancellation and failure | Save, no-op repeat, explicit clearing, cancel, invalid edit and interrupted/failed persistence have defined outcomes. A partial form or parser error must not erase unrelated fields. Reopen and verify actual persisted state; inspect stale concurrent edits before choosing any new conflict policy. |
| PR6 | Historical context | Change a dated activity/regime/residence fact, then inspect earlier-period applicability and existing filing context. Determine actual history support first. Never silently apply today's state backwards or rewrite persisted filings. If a required historical context is unsupported, expose it and escalate the missing contract rather than invent a new versioning subsystem. |
| PR7 | Census ingestion and provenance | Exercise existing synthetic censo import: same taxpayer, wrong taxpayer, duplicate, stale/partial evidence, missing fields and conflicts with local facts. Retain provenance and distinguish unobserved from false. Import must not silently destroy user-maintained fields or claim the official census has changed. Establish the current precedence rules before edits. |
| PR8 | Downstream readiness | Feed supported profile changes into existing income/IVA/retenciones/assets/calendar consumers. Show why a workflow is applicable, incomplete or unsupported. Verify stale caches/workspaces cannot present another entity's or old profile's readiness as current. Reuse tax-lane evidence; do not rerun their full calculations here. |
| PR9 | Credentials and authority boundaries | Field presence/configuration does not mean successful authentication or authority to represent an entity. Missing/locked/wrong credentials give actionable redacted diagnostics. Secret values never appear in structured profile output, logs, exception payloads or receipts. Live is NOT EXERCISED. |
| PR10 | Task usability | Users can answer: who am I configuring; what facts are missing and why; which activities/regimes are recorded; where did facts come from; what did I change; did it save; what is local versus official? Verify keyboard/focus, cancel/back, narrow terminal, labels/locales and readable CLI/typed JSON output. |
| PR11 | Continuation and persistence | CLI-only and TUI-only journeys on independent stores; CLI-to-TUI and TUI-to-CLI sequential continuations on separate owned scenario stores. Assert canonical fields and provenance after fresh-process restart, not only the success message or in-memory model. |
| PR12 | Secure lifecycle | Exercise existing secure persistence and refusal paths, including schema validation and supported migration behavior where touched. No plaintext fallback, fixture-only persistence shortcut or dependence on a developer's .env. Deletion/reset/backup redesign is outside this brief; existing destructive actions must not be invoked against real stores. |

Report each case as proven, failed, blocked or not exercised. A schema field, registered command or passing controller test is not installed-frontend acceptance. Capture unsupported fields and actual missing writer/consumer links explicitly.

## Ownership and work order

1. Consume the source map above and obtain only a bounded delta report. Coordinate ownership of profile schemas/services, secure storage, configuration, frontend composition and shared fixtures with active sessions before changing any file.
2. Trace one representative filing-critical fact from user input through canonical validation and persistence to a consumer. Confirm the matrix of current capabilities before implementing anything.
3. Reproduce the highest-risk gaps with small synthetic tests: current/historical context, import preservation/precedence, entity switching and frontend writer parity. Use existing application owners; do not create a second profile DTO, secret store, applicability engine or import path.
4. Implement already-defined gaps at their canonical boundary, then expose the same behavior in CLI and TUI. Undefined history, merge, conflict or representation semantics require a compact decision packet to the coordinator/adviser, not autonomous new architecture.
5. Run directed checks under one global reservation, then installed-frontend continuation if runtime prerequisites permit. Apply affected ruff, ty, strict typing and import gates once after integration. Product src/ never imports dev/, and CLI/TUI never import each other.
6. Hand off by PR ID with exact checks/results, sanitized evidence, remaining capability limits and downstream contracts affected. Do not restart unaffected tax lanes or relabel their old receipts.

PROFILE-01 owns profile input/selection/persistence/readiness contracts only after assignment. CALENDAR-01 owns deadline/applicability presentation and its date-boundary defects; tax briefs own calculation/filing semantics; LIVE-WALLET-01 owns its live acquisition. Historical profile context and source precedence cross these boundaries: assign one writer and one shared verification owner before either session edits them. Full backup/recovery, general invoice lifecycle and new census filing/export are separate scopes.

## Session roster and opening prompt

Each actual session records provider, lead, cc number, UUID, owned files, acceptance IDs and dependencies before work. Do not invent identifiers or treat this document as a launched session.

| Name/level | Model | Bounded responsibility |
| --- | --- | --- |
| `profile-discovery` | Luna Max | Source/test delta maps and factual audits, <=600-word reports with path:line, uncertainty and checks NOT RUN; no edits, test execution, private reads or children. |
| `profile-principal` | Terra High for Codex / Opus Medium for Claude | Complex analysis and implementation of defined contracts; no new architecture. |
| `profile-execution-*` | Terra Max / Sonnet High | Explicitly assigned files and bounded edits, tool calls, process monitoring or sanitized reporting; no architectural decisions or children. |
| `profile-adviser` | Exactly one Sol High / Fable 5.1 Medium | Bounded architecture/session-optimization consultation, no coding, idle otherwise. Confirm launcher alias and availability. |

The lead follows the central checkpoint cadence and routes Claude discovery through a named coordinated Luna lane where necessary. Each worker receives its goal, allowed files/actions, exclusions, dependencies, stop condition and reporting format. Reports state outcome, changed files if any, exact reserved command/process/result, evidence pointers and next bounded action. Do not hand workers the entire conversation or ask them to rediscover entire subsystems.

> Session taxpayer-profile. Goal: prove and complete the assigned PROFILE-01 profile/onboarding outcomes through both frontends using existing shared services. Read PROFILE-01 revision 0.1, session-policy 1.7 and ACCEPTANCE-01 1.6. Start with the source map and a bounded Luna delta; report current field/write/consumer coverage and shared-file ownership before editing. Preserve selected taxpayer, unknowns, provenance and historical filing context. No duplicate profile or applicability implementation, secret leakage, remote census writes or implicit authentication. Live remains blocked. Reuse central synthetic acceptance setup and coordinate checks once across lanes. Escalate undefined history/merge semantics; report PR outcomes and keep a compact checkpoint.
