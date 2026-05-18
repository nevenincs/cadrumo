---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace developer-leakage-emergency with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#developer-leakage-emergency'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-18'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related: []
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# developer-leakage-emergency audit: codebase-wide dev/process leakage into operator-facing surface

## Scope

User flagged a critical regression: AEAT operator-facing surfaces (registry TOML header keys, code identifiers, locale strings, CLI surface) carry development/process metadata that conflates two distinct domain entities. Confirmed exemplar: `header_key = "developer_nif"` falsely maps AEAT's `NIF del presentador` (operator who files the declaration) to "software developer NIF". The audit runs six parallel read-only sweeps (registry TOMLs, domain, application, adapters, CLI, locales+core) plus iterative re-sweep cycles. Two of six surfaces have reported. Remaining four still running.

## Findings

### Surface: registry TOMLs (`src/aeat/_data/registry/aeat/modelos/`)

Sweep covered all 32 TOMLs (26 single-file + Modelo 100 manifest with 6 yearly revisions). Greppedfor `developer|dev_|wip|todo|tmp|temp|staging|phase|wave|step|W##|P##|S##|ADR|claude|codex|haiku|sonnet|gpt|agent` across `id`, `header_key`, `binding_id`, `label`, `notes`, `description`, `quote`, `reference`, `locator` fields.

**Counts: real-AEAT-field 0, leaked-dev-metadata 10, ambiguous 0.**

#### `111.toml:616` — `header_key = "developer_nif"` — leaked-dev-metadata
#### `115.toml:286` — `header_key = "developer_tax_id"` — leaked-dev-metadata
#### `123.toml:418` — `header_key = "developer_nif"` — leaked-dev-metadata
#### `123.toml:1473` — `header_key = "developer_nif"` — leaked-dev-metadata
#### `130.toml:697` — `header_key = "developer_nif"` — leaked-dev-metadata (originating exemplar)
#### `202.toml:1253` — `header_key = "developer_nif"` — leaked-dev-metadata
#### `202.toml:4984` — `header_key = "developer_nif"` — leaked-dev-metadata; also carries generator-slug debris (`-header-header-...-po`) flatten required
#### `202.toml:6498` — `header_key = "developer_nif"` — leaked-dev-metadata
#### `232.toml:256` — `header_key = "developer_nif"` — leaked-dev-metadata
#### `232.toml:3131` — `header_key = "developer_nif"` — leaked-dev-metadata

**Remediation:** Every instance lives at fichero-header position offset 101 / length 9 — BOE/AEAT documentation labels this "NIF del presentador" (declarant operator). Rename `header_key = "presenter_nif"` and matching `id = "modelo-XXX-envelope-presenter-nif"` in lockstep with the caller-binding updates. Add a fichero-envelope roundtrip test that forces save→load equality on `presenter_nif` so silent rebind from `developer_nif` is caught structurally.

**Non-findings confirmed:** every other vocabulary hit resolved to legitimate Spanish AEAT text (`todo el año`, `Programa de preparación deportistas`, `programas de apoyo a acontecimientos…`), legitimate BOE design-record selectors (`page_NN`, `vinculada-N-metodo-valoracion`), or AEAT type codes (`P102`). No TODO/FIXME/agent-name/ADR-ref/plan-ref/audit-ref strings in `label`, `notes`, `description`, `quote`, `reference`, `locator`.

### Surface: domain (`src/aeat/domain/`)

**Counts: real-aeat-concept 5, leaked-dev-metadata 11, ambiguous-needs-adjudication 3.**

#### `domain/calculations/registry/test_modelo_232_registry.py:275` — `"envelope-developer-nif": (101, 9, "header"),` — leaked-dev-metadata
BOE 232 envelope offset 101-109 carries the *presentador* NIF. Rename to `envelope-presentador-nif`; matching registry TOML segment id must follow.

#### W##/S##/P##/ADR/plan/audit refs in production comments + test prose — all leaked-dev-metadata
- `domain/buckets/_event.py:85` — `# 036 census live-sync (W85.S2349 ADR amendment 2026-05-16)` (production code marker, must strip)
- `domain/user_profile/test_census_schema_fields.py:3,44,46,99` — `Backs W85.S2349 census-sync wave.` / `The W85 ADR amendment requires...` / `validator added in this wave` / `the dead-field bug surfaced by the W85 mapping`
- `domain/categories/test_proportionality.py:150` — `Backs the W85 ADR amendment legal-grounding contract.`
- `domain/deadlines/test_activity_window_gate.py:73` — `pre-dates the W85 census fields`
- `domain/calculations/registry/test_referential_integrity.py:720` — `the registry-wide invariant added in S33`
- `domain/calculations/registry/test_modelo_100_autonomic_chain.py:94` — `op (introduced in the autonomic-scale wave)`
- `domain/calculations/registry/test_schema_hygiene.py:244,342` — `Phase H6 of the Renta full-coverage plan...` / `Phase H6 mandates per-formula oracle grounding.`
- `domain/rental/_test_threshold_registry_grounded.py:3` — `Phase #50/#78: the prior-rent-rebaja threshold...` (filename also starts `_test_` so pytest never discovers it — separate hygiene concern)

#### Hardcoded LLM model id in unrelated domain fixtures — leaked-dev-metadata
- `domain/manuals/test_schema.py:34` — `model="claude-opus-4-6"`
- `domain/manuals/test_loader.py:76` — `"model": "claude-opus-4-6"`
Replace with neutral `"test-model"`.

#### LLM vendor/CLI names in `domain/transactions/` — ambiguous-needs-adjudication
- `domain/transactions/_model_tier.py:5-159` — `provider="claude"`, `alias="claude-haiku"`, `model_id="claude-opus-4-7"`, `provider="codex"`, etc.
- `domain/transactions/_llm.py:478-608` — `build_claude_classifier`, `build_codex_classifier`, registry dict mapping `"claude"` / `"codex"` to factories
- `domain/transactions/test_model_tier.py:37,48,58-93` — iterates `("claude", "gemini", "codex")`
Recommend ADR to confine to this subpackage rather than rename.

**Confirmed false positives (real-aeat-concept, leave intact):**
- `domain/calculations/registry/test_schema_hygiene.py:43-44` — `"phase "`, `"wave "` inside `_FORBIDDEN_TEST_NARRATIVE` (enforcement list)
- `domain/profile/test_model.py:91-92` — `match="XXX"` is the ISO-3166 placeholder code, not the FIXME marker
- `domain/transactions/_llm.py:9` — "requires a developer to decide" (maintainer prose)
- `domain/calculations/registry/test_relation_consistency.py:152` — "so the developer can fix" (maintainer prose)
- `domain/transactions/test_catalogue.py:424,431` — `classified_by="llm:gpt-4"` (real provenance field, representative fixture)

No matches for `wip`, `tmp_`/`_tmp`, `staging`, `sprint`/`cycle`, `TODO`/`FIXME`, or canonical `W##`/`P##`/`S##` outside the items above. No imports of dev-process-named symbols.

### Surface: application (src/aeat/application/)

Sweep scope: every file under `src/aeat/application/` excluding `__pycache__/`. Greps: developer / dev / wip / TODO / FIXME / XXX / staging / tmp / temp / phase / wave / step / W##/P##/S## / claude / codex / haiku / sonnet / gpt / ADR-refs / plan-refs / agent-name / actor-helper patterns. All matches read in context.

**Counts: real-aeat-concept 5, leaked-dev-metadata 12, ambiguous-needs-adjudication 1.**

#### `application/filing/test_export.py:93` -- verbatim `"developer_nif": "A12345678",` -- real-aeat-concept -- synchronised rename with registry
Modelo 130 export-header fixture; mirrors registry header_key. Echoes the canonical regression but the source-of-truth is the registry TOML (already reported). Rename in lockstep with `presenter_nif`.

#### `application/filing/test_export.py:236` -- verbatim `"developer_nif": "A12345678",` -- real-aeat-concept -- synchronised rename with registry
Modelo 111 export-header fixture.

#### `application/filing/test_export.py:264` -- verbatim `"developer_tax_id": "A12345678",` -- real-aeat-concept -- synchronised rename with registry
Modelo 115 export-header fixture.

#### `application/filing/test_export.py:297` -- verbatim `"developer_tax_id": "A12345678",` -- real-aeat-concept -- synchronised rename with registry
Modelo 123 export-header fixture.

#### `application/filing/test_export.py:329` -- verbatim `"developer_tax_id": "A12345678",` -- real-aeat-concept -- synchronised rename with registry
Modelo 123 (2019 variant) export-header fixture.

#### `application/storage/calc_sheets/_records.py:421` -- verbatim `Stored both in the workbook's developer metadata (so the pull` -- ambiguous-needs-adjudication -- reword
"developer metadata" is the OOXML / xlsx feature name (custom-properties dictionary used for round-trip stamping), not process leakage; but the wording is ambiguous on first read. Reword to "workbook's custom OOXML properties (a.k.a. developer metadata)".

#### `application/diagnostics.py:507` -- verbatim `name="dev_environment.uv_sync",` -- leaked-dev-metadata -- rename to operator-facing label
Diagnostic row name surfaces through CLI output; an operator running diagnostics on a shipped install does not have a "dev environment". Rename to `runtime_environment.venv_sync` / `install.uv_sync` / `runtime.dependency_sync`.

#### `application/diagnostics.py:512` -- verbatim `name="dev_environment.uv_sync",` -- leaked-dev-metadata -- rename to operator-facing label
Warn-branch emission; must rename in lockstep with line 507.

#### `application/profile/__init__.py:4` -- verbatim `census live-sync (W85.S2349), and future profile-cross-AEAT` -- leaked-dev-metadata -- strip wave identifier
Module-level docstring on a public package surface embeds `W85.S2349`. Replace with domain description (e.g. "census live-sync against the sede Mis Datos Censales endpoint").

#### `application/profile/_census_errors.py:3` -- verbatim `Backs the W85.S2349 census-sync wave per the 2026-05-16 amendment to` -- leaked-dev-metadata -- strip wave + amendment date
Drop plan / ADR coordinates; describe what the errors signal and which CLI verb raises them.

#### `application/profile/_census_sync.py:23` -- verbatim `FilingRecord as CENSUS_STALE on apply) is the P05 follow-on; this` -- leaked-dev-metadata -- strip phase reference
Replace "P05 follow-on" with the behavioural name (stale-cascade walker).

#### `application/profile/_census_sync.py:287` -- verbatim `catalogue so the stale-cascade walker (P05.S54) can react.` -- leaked-dev-metadata -- strip phase / step reference
Drop the parenthetical.

#### `application/live/_census.py:14` -- verbatim `The CLI-facing CensusSyncService (P04) is the only caller; the` -- leaked-dev-metadata -- strip phase reference
Production module docstring; drop `(P04)`.

#### `application/live/_census.py:15` -- verbatim `sede G313 adapter (P03) populates census_facts from the live` -- leaked-dev-metadata -- strip phase reference
Drop `(P03)`. Keep `sede G313` (AEAT endpoint identifier).

#### `application/workflow/_bucket_pointer_io.py:32` -- verbatim `file is absent. The higher-level resolver (P04) treats None` -- leaked-dev-metadata -- strip phase reference
Public-function docstring; replace `(P04)` with the resolver's domain name.

#### `application/setup/test_service_provisions_bucket.py:3` -- verbatim `Pins the contract added in P02.S19: after a successful workspace` -- leaked-dev-metadata -- strip phase + step
Replace with behavioural statement of what the test pins.

#### `application/test_diagnostics_dispatch.py:143` -- verbatim `row carries the ADR-canonical 'aeat config init' literal so` -- leaked-dev-metadata -- reword
Reword "ADR-canonical" to "canonical".

#### `application/wizard/test_dependency_import.py:27` -- verbatim `Installed 'questionary' distribution must be at the ADR-pinned floor.` -- leaked-dev-metadata -- reword
Reword to "must be at version 2.1.1 or later (the floor pinned by pyproject.toml)".

#### Non-findings (verified, not leaks)

`_actor` parameters across `ledger/_actions.py`, `modelo/_actions.py`, `live/_census.py` (real audit-trail operator-identity concept, not process); `LIFECYCLE_*` constants in `operator_surface/` (real AEAT noun-group taxonomy); `tmp_path` (pytest fixture); `client.p12` (certificate paths); `presentador` / `declarante` Spanish terminology where present. Searched for `_resolve_default_actor` and any "actor"-as-technical helper: none found in `application/`. No `TODO` / `FIXME` / `XXX` / `HACK` / `WIP` markers. No agent names (claude / codex / haiku / sonnet / gpt) anywhere in `application/`.

application: real=5, leaked-dev-metadata=12, ambiguous=1

### Surface: adapters — *pending*
### Surface: CLI entrypoints — *pending*
### Surface: locales + i18n + core — *pending*

## Recommendations

1. **TOML rename sweep first:** all 10 `developer_nif` instances → `presenter_nif`, plus `developer_tax_id` (115.toml). Run as one atomic commit so the caller-binding ripple is contained.
2. **Production comment strip:** `domain/buckets/_event.py:85` carries a W##.S## comment in canonical production code. Strip; the ADR reference goes in the commit message + vault doc, not the code.
3. **Test prose strip:** 8 test docstrings carry W##/S##/Phase H# refs. Move the process context to vault audit / plan docs; the test docstring should describe the invariant, not the project artefact that motivated it.
4. **LLM model id placeholders:** swap `claude-opus-4-6` literals in unrelated fixtures for `test-model`.
5. **ADR for the LLM-vendor namespace:** `domain/transactions/` legitimately interacts with multiple LLM providers; the question is whether the vendor names belong in the domain layer at all (the rule `no_transient_dev_metadata_in_code` would say no — push vendor IDs to an adapter and reference an abstract provider tier in domain).
6. **Add memory rule:** the maintainer prose pattern ("so the developer can fix") is legitimate but borderline; if it grows it will rot into the operator surface. Worth a stylistic-guidance note.

