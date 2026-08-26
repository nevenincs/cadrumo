---
tags:
  - '#plan'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_hash: 'sha256:a273f437d1ee623c70e2d1fb003151f366805d12274a2aad3713a64c6c8c3106'
tier: L2
related:
  - '[[2026-08-09-cli-verb-profile-diagnostics-adr]]'
  - '[[2026-08-09-cli-verb-profile-diagnostics-reference]]'
---
# `cli-verb-profile-diagnostics` plan

## Description

Close the coverage gap between the canonical profile-requirement mechanism and
the CLI verbs that refuse or warn on missing profile information, per
`2026-08-09-cli-verb-profile-diagnostics-adr`. The site inventory, with locators
and the classification of message defects against verdict defects, is in
`2026-08-09-cli-verb-profile-diagnostics-reference`.

Every Step here changes WHAT an operator reads when a verb refuses. No Step
changes WHETHER a verb refuses. The readiness-verdict reconciliation deferred
under the `profile-requirement-grounding` feature stays deferred.

## Steps

### Phase `P01` - Selector-to-path resolution primitive

Add the one missing schema primitive that maps a declared model_selectors token to its section.field path, refusing to guess on an absent or ambiguous token, and promote it to the owning package facade.

- [x] `P01.S01` - Add a resolver mapping a declared model_selectors token to its section.field path, returning nothing when the token names no field or more than one; `src/cadrumo/domain/user_profile/_schema.py`.
- [x] `P01.S02` - Promote the selector-to-path resolver to the owning package public facade; `src/cadrumo/domain/user_profile/__init__.py`.
- [x] `P01.S03` - Add real-schema tests covering a resolving token, an absent token and an ambiguous token; `src/cadrumo/domain/user_profile/tests/test_schema.py`.

### Phase `P02` - Overview refusal surfaces

Route the calendar, agenda and backlog refusals through the canonical requirement builder and the typed notice channel, leaving every refusal condition unchanged.

- [x] `P02.S04` - Add a shared refusal-rendering helper that enriches profile-selector warning codes into schema-derived requirement rows and passes non-profile codes through unchanged; `src/cadrumo/entrypoints/cli/_overview.py`.
- [x] `P02.S05` - Route the overview calendar refusal through the shared enrichment helper and the typed notice channel; `src/cadrumo/entrypoints/cli/_overview.py`.
- [x] `P02.S06` - Route the overview agenda refusal through the shared enrichment helper and the typed notice channel; `src/cadrumo/entrypoints/cli/_overview.py`.
- [x] `P02.S07` - Route the overview backlog refusal through the shared enrichment helper and the typed notice channel; `src/cadrumo/entrypoints/cli/_overview.py`.
- [x] `P02.S08` - Add the enriched overview refusal locale strings with real translations in all four catalogues; `src/cadrumo/locales/en.yml`.
- [x] `P02.S09` - Add real CLI tests asserting the overview refusals name the field label and its legal basis and leave non-profile warning codes intact; `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`.

### Phase `P03` - Modelo requires and diagnostics surfaces

Replace raw registry binding ids and the bare missing-key count with schema-derived requirement rows at the remaining message-defect sites.

- [x] `P03.S10` - Promote the binding-selector profile-key extraction to the registry package public facade so consumers outside the domain module can resolve a profile binding to its consumed keys; `src/cadrumo/domain/calculations/registry/__init__.py`.
- [x] `P03.S11` - Enrich the app modelo requires unresolved-coefficient notice with schema-derived requirement rows instead of raw registry binding ids; `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`.
- [x] `P03.S12` - Replace the diagnostics profile-readiness bare-count summary with one naming the missing fields by operator label; `src/cadrumo/application/diagnostics.py`.
- [x] `P03.S13` - Replace the raw profile keys carried in diagnostics findings with schema-derived labels and legal basis; `src/cadrumo/application/diagnostics.py`.
- [x] `P03.S14` - Add the enriched requires and diagnostics locale strings with real translations in all four catalogues; `src/cadrumo/locales/en.yml`.
- [x] `P03.S15` - Add real CLI tests asserting app modelo requires names the missing profile field by label rather than by binding id; `src/cadrumo/entrypoints/cli/tests/test_modelo_requires_profile_grounding.py`.
- [x] `P03.S16` - Add real tests asserting the diagnostics profile-readiness check names its missing fields by label; `src/cadrumo/application/tests/test_diagnostics_profile_grounding.py`.

### Phase `P04` - Verification and honesty review

Run the full affected suites sequentially, confirm locale parity across all four catalogues, and complete the fresh-context honesty review before declaring the work complete.

- [x] `P04.S17` - Run every affected test module in a sequential run and record the full captured result; `src/cadrumo`.
- [x] `P04.S18` - Confirm locale catalogue parity and translation honesty across all four catalogues; `src/cadrumo/locales`.
- [x] `P04.S19` - Run the fresh-context honesty review against the closure summary and action or explicitly defer every finding; `.vault/audit`.

### Phase `P05` - Undeclared taxpayer-model refusal

Name the specific profile facts an undeclared taxpayer model is missing, found during the honesty review after the original inventory recorded only the completeness-warning refusals on these same verbs.

- [x] `P05.S20` - Name the specific missing taxpayer-model profile facts in the undeclared refusal and raise it through the refusal channel rather than as a parameter error; `src/cadrumo/entrypoints/cli/_overview.py`.
- [x] `P05.S21` - Add the undeclared taxpayer-model refusal locale string with real translations in all four catalogues; `src/cadrumo/locales/en.yml`.
- [x] `P05.S22` - Add real tests asserting the undeclared taxpayer-model refusal names the missing facts and reads as a refusal; `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`.

### Phase `P06` - Filing-grade export declarant-identity refusal

Name the missing declarant-identity facts by operator label in the modelo export refusal, found during the honesty review sweep of application-layer refusal sites the initial inventory did not reach.

- [x] `P06.S23` - Render the missing declarant-identity facts in the modelo export refusal as grounded requirement rows rather than raw dotted paths; `src/cadrumo/application/modelo/_export.py`.
- [x] `P06.S24` - Add real tests asserting the export refusal names the missing declarant-identity facts by operator label; `src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py`.

### Phase `P07` - End-to-end profile-field refusal coverage

Close the coverage gap the honesty review recorded by building a fixture whose profile omits a real gating field, so an unanswered profile fact drives an actual CLI refusal for all three overview verbs rather than being covered by construction.

- [x] `P07.S25` - Add a calendar backend fixture variant that omits chosen gating profile facts instead of answering them; `src/cadrumo/entrypoints/cli/tests/_overview_calendar_support.py`.
- [x] `P07.S26` - Add real CLI tests driving an unanswered profile field through an actual overview calendar refusal and asserting the operator label reaches the output; `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`.
- [x] `P07.S27` - Add the same end-to-end refusal assertion for the overview agenda verb; `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`.
- [x] `P07.S28` - Add the same end-to-end refusal assertion for the overview backlog verb; `src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py`.

### Phase `P08` - Remaining hard-coded field-name refusals

Replace the two refusals that name profile fields by baking an identifier into their sentence, so the field name comes from the schema like every other refusal in this work.

- [x] `P08.S29` - Name the missing identity field by its schema-derived operator label in the wizard status refusal instead of baking a selector token into the sentence; `src/cadrumo/application/wizard/_status.py`.
- [x] `P08.S30` - Name the required declarant-identity fields by their schema-derived labels in the export no-profile refusal instead of hard-coding two paths into the sentence; `src/cadrumo/application/modelo/_export.py`.
- [x] `P08.S31` - Update the two refusal locale strings to carry a requirements placeholder with real translations in all four catalogues; `src/cadrumo/locales/en.yml`.
- [x] `P08.S32` - Add real tests asserting both refusals name their fields by operator label and carry no raw dotted path; `src/cadrumo/application/wizard/tests/test_status_refusal_grounding.py`.

### Phase `P09` - Live-auth profile identity refusals

Name the missing profile identity field by its schema-derived label in the two live-auth refusals that spell a dotted path into their sentence, found by the closing locale-catalogue sweep.

- [x] `P09.S33` - Name the cleared profile identity field by its schema-derived label in the live-auth identity-cleared refusal; `src/cadrumo/application/auth/_sessions.py`.
- [x] `P09.S34` - Name the required profile identity field by its schema-derived label in the live-auth missing-tax-id refusal; `src/cadrumo/application/auth/_sessions.py`.
- [x] `P09.S35` - Update the two live-auth refusal locale strings to carry a requirements placeholder with real translations in all four catalogues; `src/cadrumo/locales/en.yml`.
- [x] `P09.S36` - Add real tests asserting both live-auth refusals name the field by operator label and carry no raw dotted path; `src/cadrumo/application/auth/tests/test_session_identity_refusal_grounding.py`.

### Phase `P10` - Cl@ve credential refusals

Name the Cl@ve credential fields by their schema-derived labels in the last two refusals the systematic catalogue census found embedding a profile path in prose.

- [x] `P10.S37` - Name the Cl@ve identity field by its schema-derived label in the missing-identity credential refusal; `src/cadrumo/application/auth/_sessions.py`.
- [x] `P10.S38` - Name both Cl@ve contraste fields by their schema-derived labels in the missing-contraste credential refusal; `src/cadrumo/application/auth/_sessions.py`.
- [x] `P10.S39` - Update the two Cl@ve credential locale strings to carry field placeholders with real translations in all four catalogues; `src/cadrumo/locales/en.yml`.
- [x] `P10.S40` - Extend the live-auth refusal tests to cover the Cl@ve identity and contraste field renderings; `src/cadrumo/application/auth/tests/test_session_identity_refusal_grounding.py`.

### Phase `P11` - Field-path correctness in operator-facing finding messages

Fix the three modelo-finding next_action messages the honesty review found citing a nonexistent profile.* path instead of the real schema path, and add a matching test.

- [x] `P11.S43` - Ground the three modelo-finding next_action messages that cite a nonexistent profile.* field path (m210_baseline_tipo_deferred, m210_convenio_rate_missing, representante_fiscal_required) at their real schema paths (taxpayer_type.country_of_fiscal_residence, taxpayer_type.representante_fiscal_nif) through the same schema-derived-label mechanism P08/P09/P10 use, verified by the same operator-label-not-raw-path assertion pattern those Steps use.; `src/cadrumo/locales/en.yml, src/cadrumo/application/modelo (finding message sites), src/cadrumo/application/modelo/tests`.
- [x] `P11.S44` - Add a terminal re-verification Step re-running the sequential suite (S17), locale parity (S18) and a fresh honesty review (S19-shaped) against the tree as it stands after every Phase through P11 has landed, since the original P04 verification triple ran before P05-P11 (roughly half this campaign) existed and cannot certify work it predates. Do not declare this campaign complete until this Step is green.; `no production files, verification only`.

### Phase `P12` - Date-binding calculate guidance

Name the profile fact behind an unsatisfied date-valued profile binding, rather than instructing the operator to set a registry binding id on their profile.

- [x] `P12.S41` - Resolve the unsatisfied date binding to the profile facts it consumes and name those in the calculate guidance, degrading to the binding id when it cannot be resolved; `src/cadrumo/entrypoints/cli/_modelo.py`.
- [x] `P12.S42` - Add real tests asserting the date-binding guidance names the profile fact and degrades safely for an unresolvable binding; `src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py`.

### Phase `P13` - Correct binding-key rendering from selector lookup to path lookup

Registry binding profile keys are schema paths, not model_selectors tokens, so the selector-based renderer passed them through unchanged and the modelo requires enrichment was a silent no-op. Add the path-based renderer and route both binding-key sites through it.

- [x] `P13.S45` - Add a path-based requirement renderer beside the selector-based one and export it; `src/cadrumo/application/user_profile/_preflight.py`.
- [x] `P13.S46` - Route the modelo requires unresolved-coefficient warning through the path-based renderer; `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`.
- [x] `P13.S47` - Route the date-binding calculate guidance through the path-based renderer; `src/cadrumo/entrypoints/cli/_modelo.py`.
- [x] `P13.S48` - Add tests proving both binding-key sites render a real operator label and that the selector-based renderer would not have; `src/cadrumo/application/user_profile/tests/test_requirement_rendering_paths.py`.

### Phase `P14` - Process metadata in shipped operator text

Remove the issue reference and phase language from an operator-facing finding message, which this project's source-hygiene rule forbids in user-facing surfaces.

- [x] `P14.S49` - Replace the issue reference and phase language in the deferred-baseline finding message with a statement of the underlying technical fact, in all four catalogues; `src/cadrumo/locales/en.yml`.

### Phase `P15` - Measure the prose-named field class both reviews left unmeasured

Both honesty reviews named one class as explicitly unmeasured: a message naming a profile field in prose with no dotted identifier, which neither census could detect. Measure it behaviour-scoped, and dispose of every hit.

- [x] `P15.S50` - Census every operator-facing message that instructs the operator to supply a profile value, independently of whether it names an identifier, and classify each hit; `src/cadrumo/locales/en.yml`.
- [x] `P15.S51` - Record the deliberate decision not to ground the two censal fiscal-ID refusals, whose grounded label would propagate a known-wrong legal citation; `src/cadrumo/application/user_profile/_censo_sync.py`.
- [x] `P15.S52` - Record the registered profile-preflight-missing error that carries an unactionable message and has no raise site anywhere in production; `src/cadrumo/core/errors/registry/_domain_part3.py`.

### Phase `P16` - Move the date-binding resolution out of the CLI root

The date-binding profile-fact resolution added registry-authority reads to the legacy modelo CLI root, which an architecture gate budgets at zero. Move the resolution into the application layer, where the binding definitions already live.

- [x] `P16.S53` - Move the date-binding profile-fact resolution into the application layer and expose it through the package facade; `src/cadrumo/application/modelo/_data_inventory.py`.
- [x] `P16.S54` - Reduce the CLI root to a thin call into that application helper, restoring the zero registry-authority-read budget; `src/cadrumo/entrypoints/cli/_modelo.py`.
- [x] `P16.S55` - Repoint the date-binding guidance tests at the application helper and confirm the architecture budget gate is green; `src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py`.

## Parallelization

`P01` is a hard prerequisite for `P02` and `P03`: both consume the resolver it
adds. Within `P02` the three verb Steps touch one module and are sequenced to
avoid contending on it. `P03`'s two Steps are independent of each other. `P04`
runs last.

## Verification

The plan is complete when every Step is closed, the affected test modules pass
in a sequential run, `python -m dev.locales scaffold --check` reports no drift
across all four catalogues, and the fresh-context honesty review has been run
against the closure summary with its findings actioned or explicitly deferred.
