---
tags:
  - '#research'
  - '#profile-setup-flow'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:2b0f7ead63ed20cb37c8fe760e5b5fc1d3d2138e4bb6ad7add8ce43d685d8dcc'
related:
  - "[[2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research]]"
  - "[[2026-07-23-tui-wizard-substrate-research]]"
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-07-25-censal-profile-autofill-adr]]"
---

# `profile-setup-flow` research: `Current profile manager information architecture and population pathways`

The current profile manager exposes a 152-field legal and operational data model as one fully expanded scrolling surface. The schema has real section hierarchy and stores fact provenance, but the manager flattens both meaning and origin: it shows every field, marks only globally required rows, and omits each value's source and validity. Automatic population exists, but only as disconnected pathways whose coverage is not explained in the interface. The evidence favors progressive disclosure driven by requiredness, filing relevance, confidence, and source coverage, with automatic candidates reconciled before manual questions; an ADR must settle the projection contract and interaction model.

## Findings

### The schema is hierarchical, but the manager is one fully expanded inventory

The canonical model is `sections -> fields`, while stored addresses use flat dotted paths. The manager composes one action panel followed by one panel and table for every projected section inside a single scroll container; there is no collapsible, accordion, tree, or staged-navigation construct in that path. The overview deliberately walks the schema rather than the record, so every declared editable field becomes a row whether filled or blank. Repeatable sections expand from stored row indexes; engine-derived selectors are hidden. `src/cadrumo/domain/user_profile/_schema.py:170`, `src/cadrumo/domain/user_profile/_schema.py:306`, `src/cadrumo/adapters/inbound/tui/_manager_screen.py:323`, `src/cadrumo/adapters/inbound/tui/_manager_screen.py:343`, `src/cadrumo/application/user_profile/_overview.py:623`, `src/cadrumo/application/user_profile/_overview.py:654`.

The current working-tree schema contains 26 sections and 152 declared fields: 16 `required = true`, 136 optional, and five repeatable sections. This is a current-tree measurement, not a stable release count, because the schema is concurrently modified. The rendered manager replay at 120x38 showed the required summary, the action block, and only the first three of 26 section tables before the viewport ended; its focus chain contained 26 tables. Re-fetch with `uv run --no-sync python -m dev.tui show` and the schema-count command in Sources.

### Requiredness exists, but priority and applicability do not

`ProfileFieldDefinition` provides one `required` boolean alongside type, sensitivity, effective-dating, selectors, and legal references. It has no optional/advisory/importance tier, no conditional applicability expression, and no declaration of an automatic source. `src/cadrumo/domain/user_profile/_schema.py:113`.

The global completeness rule requires ordinary required fields, but requires cells in a repeatable section only when a row exists; an empty repeatable section demands nothing. Consequently, the current replay reported three missing required values even though 16 field declarations carry `required = true`. `src/cadrumo/application/user_profile/_completeness.py:160`, `src/cadrumo/application/user_profile/_overview.py:324`.

The manager exposes this distinction only as a top summary and an asterisk on required rows. Optional blanks, irrelevant blanks, potentially useful facts, and advisory-only facts otherwise look alike. Typed `Notice` objects are a separate profile-level band rather than per-field semantics. `src/cadrumo/adapters/inbound/tui/_manager_screen.py:450`, `src/cadrumo/adapters/inbound/tui/_manager_screen.py:489`, `src/cadrumo/application/user_profile/_overview.py:303`.

Filing preflight supplies a second, contextual notion of need: it filters required fields by `modelo_` selectors and can add registry grounding for a concrete filing. That useful context is not the manager's organizing principle, and an unassessed operation is distinct from a healthy one. `src/cadrumo/application/user_profile/_preflight.py:220`, `src/cadrumo/application/user_profile/_preflight.py:270`.

### Provenance is persisted and then dropped before the manager renders a row

Every `UserProfileFact` carries `source`, `valid_from`, and `valid_to`; the default source is `manual_cli`, and accepted source tokens are schema-declared. The current schema declares `manual_cli`, `setup_wizard`, `modelo_036_import`, `aeat_censo_read`, `registry_inference`, and `censo_artefact_g313`. `src/cadrumo/domain/user_profile/_values.py:181`, `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1859`.

`ProfileFieldView`, which feeds the manager table, carries path, label, display value, presence, requiredness, type, choices, sensitivity, and row index, but not fact source or validity. The interface therefore cannot answer whether a visible value was typed, imported, inferred, read from AEAT, or retained from an earlier reconciliation. Rendering the separate editable `provenance` schema section does not restore per-value lineage. `src/cadrumo/application/user_profile/_overview.py:228`, `src/cadrumo/adapters/inbound/tui/_manager_screen.py:489`.

### Automatic population is real but narrow, disconnected, and under-explained

The current production paths discovered for profile seeding are:

| Pathway | Verified profile coverage | Reconciliation behavior | Manager disclosure before action |
|---|---|---|---|
| Existing profile/checkpoint | Reuses already stored answers when setup resumes | Existing record remains the authority | Values appear, but no source is shown |
| Authentication setup | Defaults provider/route and may suggest NIF from identity, auth facts, or certificate subject | Operator confirms the form | No source or confidence shown |
| Live AEAT censal read | Exactly fiscal address, postcode, and cadastral reference | Adopts blanks, refreshes prior AEAT-read values, preserves manual values and explicit clears as divergences | One generic “Fill in from AEAT censal data” action; no coverage preview |
| G313 censal certificate | Only unambiguous certificate axes become candidate profile facts | Selected values route through the cotejo authority; ambiguous certificate text stays evidence | Not represented as a field-level source map |
| Filed-history pull | Filing observations and reconciliation state, not general profile facts | Preserves filed evidence | Adjacent action can be mistaken for profile autofill |

The live censal projection intentionally excludes identity, combined names, residence prose, representative identity, tax situation, and periodic obligations where an authoritative mapping is absent. `src/cadrumo/application/user_profile/_censo_sync.py:50`, `src/cadrumo/application/user_profile/_censo_sync.py:233`, `src/cadrumo/application/user_profile/_censo_sync.py:275`, `src/cadrumo/domain/censo/_certificado.py:1`, `src/cadrumo/domain/censo/_certificado.py:88`, `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:134`, `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:361`.

No generic sensor-pool abstraction or broad reconciled-text-to-profile ingestion path was found by semantic RAG followed by exact search. That is an evidence boundary, not proof that every possible producer is absent: the targeted exact search returned zero `sensor_pool`, `sensor-pool`, or `sensor pool` matches under `src/cadrumo`, while concrete censo and checkpoint paths were found and read. The ADR should not assume the missing abstraction exists under another name without a producer-to-consumer inventory.

### Locale machinery is centralized, but fallback makes mixed language a live failure mode

Normal manager chrome and schema labels resolve through `tr()`. Locale keys are derived for every schema section and field, while the schema's title or description is the fallback. Those fallback descriptions are deliberately mixed-language authority prose, so a missing catalogue entry can turn a concise translated label into a long label in another language. `src/cadrumo/domain/user_profile/_labels.py:1`, `src/cadrumo/domain/user_profile/_labels.py:87`, `src/cadrumo/domain/user_profile/_labels.py:101`.

The manager's F2 language action rebuilds the projection, which is necessary because labels are bound at overview construction. The 2026-08-11 replay successfully switched chrome from Spanish to English, but the stored `Output language` value still displayed `Spanish` under the replay override; this is correct state display but easy to misread without an explanation of override precedence. `src/cadrumo/adapters/inbound/tui/_manager_screen.py:1021`, `src/cadrumo/application/user_profile/_overview.py:654`.

The current shared-tree `dev.locales audit` is red: each of `ca`, `es`, and `hu` reports 51 missing keys, while `en` reports 52. At least nine missing keys in each catalogue are directly in the profile/setup surface. Concurrent registry and locale work means this is a current-tree condition, not an attributable regression; it nevertheless proves that the schema fallback path can be exercised today.

### The interface exposes actions, but not a population plan

The action block makes two real data-acquisition capabilities discoverable: censal read and filing-history pull. It does not state prerequisites, which profile fields each action can populate, whether the action previews or commits, what source stamp will be recorded, or how conflicts are handled. In the same viewport, every blank row remains editable and visually equal apart from the required asterisk. The user therefore sees automation and manual entry as unrelated controls instead of one ordered acquisition and reconciliation process. `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:134`, `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:153`, `src/cadrumo/adapters/inbound/tui/_manager_screen.py:535`.

The evidence separates four states that a future projection needs to express without inventing legal conclusions: required now, relevant later or for a specific filing, available from a trusted source, and manual/advisory. These are independent axes; collapsing them into one `required` flag would misstate the schema.

### Progressive disclosure is better supported than either a larger flat table or a wizard-only replacement

Three options remain for an ADR:

1. Keep the fully expanded manager and add badges/help. This preserves implementation shape but leaves 136 optional fields competing with the required core and cannot make source acquisition the primary path.
2. Replace the manager with a sequential wizard. This reduces initial density but makes ongoing correction, provenance comparison, conditional filing needs, and repeated rows harder to inspect; the existing one-question-at-a-time substrate was already being retired for bounded forms.
3. Keep the schema and editable manager authority, but introduce a task-led overview with progressive disclosure: required-now and unresolved-conflict groups open first; populated and filing-relevant groups summarized; optional/advisory sections collapsed; automatic sources offered before manual questions; every value carries source, validity, and reconciliation state. This fits the existing section hierarchy, typed notices, preflight reports, source-stamped facts, and action doors without making the TUI a second tax authority.

The evidence favors option 3. The ADR must still settle: the canonical field-state projection; whether applicability is schema-, registry-, or operation-derived; source candidate precedence and consent; collapse defaults and persistence; how provenance appears without exposing secrets; how live pulls preview versus commit; and how locale fallback is prevented from reaching the operator.

### Investigation boundaries

This research inspected the current working-tree schema, projections, manager composition, censal/certificate reconciliation, locale resolution, and deterministic replay harness. It did not change production code, exercise a real taxpayer account, pull live AEAT data, validate a genuine G313 specimen, or prove the console entrypoint in a human TTY. The schema and several profile files contain concurrent peer work, so counts and locale-audit totals must be refreshed when the ADR is authored.

## Sources

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1859`
- `src/cadrumo/domain/user_profile/_schema.py:113`
- `src/cadrumo/domain/user_profile/_schema.py:170`
- `src/cadrumo/domain/user_profile/_schema.py:306`
- `src/cadrumo/domain/user_profile/_values.py:181`
- `src/cadrumo/application/user_profile/_completeness.py:160`
- `src/cadrumo/application/user_profile/_overview.py:228`
- `src/cadrumo/application/user_profile/_overview.py:303`
- `src/cadrumo/application/user_profile/_overview.py:623`
- `src/cadrumo/application/user_profile/_overview.py:654`
- `src/cadrumo/application/user_profile/_preflight.py:220`
- `src/cadrumo/application/user_profile/_preflight.py:270`
- `src/cadrumo/application/user_profile/_censo_sync.py:50`
- `src/cadrumo/application/user_profile/_censo_sync.py:233`
- `src/cadrumo/application/user_profile/_censo_sync.py:275`
- `src/cadrumo/domain/censo/_certificado.py:1`
- `src/cadrumo/domain/censo/_certificado.py:88`
- `src/cadrumo/domain/user_profile/_labels.py:1`
- `src/cadrumo/domain/user_profile/_labels.py:87`
- `src/cadrumo/domain/user_profile/_labels.py:101`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:323`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:450`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:489`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:535`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:1021`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:134`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:153`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:361`
- Current-tree schema measurement: `uv run --no-sync python -c "import tomllib,pathlib; d=tomllib.loads(pathlib.Path('src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml').read_text(encoding='utf-8')); print(len(d['sections']), sum(len(s['fields']) for s in d['sections']), sum(bool(f.get('required')) for s in d['sections'] for f in s['fields']))"`
- Deterministic TUI replay: `uv run --no-sync python -m dev.tui show`; `uv run --no-sync python -m dev.tui size 120x38`; `uv run --no-sync python -m dev.tui locale en`
- Locale audit: `uv run --no-sync python -m dev.locales audit`
- Sensor-pool absence check: `rg -n -i "sensor[_ -]?pool" src/cadrumo`
