---
tags:
  - '#audit'
  - '#developer-leakage-emergency'
date: '2026-05-18'
modified: '2026-05-18'
related: []
---



# developer-leakage-emergency audit: codebase-wide dev/process leakage into operator-facing surface

## Scope

User flagged a critical regression: AEAT operator-facing surfaces (registry TOML header keys, code identifiers, locale strings, CLI surface) carry development/process metadata that conflates two distinct domain entities. Confirmed exemplar: `header_key = "developer_nif"` falsely maps AEAT's `NIF del presentador` (operator who files the declaration) to "software developer NIF". The audit ran six parallel read-only sweeps (registry TOMLs, domain, application, adapters, CLI, locales+core). All six reported.

## Aggregate counts (cycle 1)

| Surface | Real | Leaked | Ambiguous |
|---|---|---|---|
| Registry TOMLs | 0 | 10 | 0 |
| Domain | 5 | 11 | 3 |
| Application | 5 | 12 | 1 |
| Adapters | 1 | 12 | 3 |
| Locales + core | 4 | 7 + ≈680 translation placeholders | 2 |
| CLI entrypoints | 1 | 8 | 1 |
| **Total** | **16** | **60 + ≈680 placeholders** | **10** |

**Headline:** the operator-visible CLI verb/option/help surface is clean (no operator-facing leaks). The leaks cluster in:
1. **Registry TOML header_keys** — 10 instances of `developer_nif`/`developer_tax_id` that should be `presenter_nif`/`presenter_tax_id` per AEAT's "NIF del presentador" labelling. These propagate downstream into 5 test fixtures in `application/filing/test_export.py` and 2 in `adapters/outbound/aeat/sede/test_declarations.py`.
2. **W##/P##/S##/Phase H#/ADR-row-ID references in docstrings, comments, and test prose** — 30+ instances across domain, application, adapters, and CLI. One sits in canonical production code (`domain/buckets/_event.py:85`). Violates the `no_transient_dev_metadata_in_code` rule.
3. **Catastrophic locale placeholder ship** — 113 (en) / 233 (es) / 234 (ca) / 234 (hu) `cli.*.*_help` values that literally echo the keypath; plus 17×4 = 68 random-digit scaffold keys (`t_135562`); plus 4 self-referencing `unsupported_modelo`/`invalid_period_format` strings. Operators running `aeat --help` see raw key names. **This is worse than the developer_nif leak.**
4. **Diagnostic surface leak** — `application/diagnostics.py:507,512` emits a row named `dev_environment.uv_sync` through CLI output. Operators on a shipped install have no "dev environment".
5. **Unrelated-fixture LLM model literals** — `domain/manuals/test_*.py` hardcode `claude-opus-4-6`. Should be `test-model`.
6. **Three ADR-needed adjudications**: LLM vendor namespace in `domain/transactions/`, `FAIL_STORAGE_MIGRATION` / `REFUSED_STORAGE_BUCKET_LEGACY_LAYOUT` error codes (operator-visible upgrade lingo).

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

### Surface: adapters (`src/aeat/adapters/`)

**Counts: real-aeat-concept 1, leaked-dev-metadata 12, ambiguous-needs-adjudication 3.**

#### `adapters/outbound/aeat/sede/test_declarations.py:105,121` — `"developer_tax_id": "A12345678"`, `"developer_nif"` peer — leaked-dev-metadata
Downstream of the registry TOML leak. Rename in lockstep with `presenter_tax_id` / `presenter_nif`. Also affects `user_profile/schema.toml:499,504`.

#### `adapters/persistence/storage/bucket/_keystore_paths.py:15` — `the cryptographic core / (P03) owns provisioning when an enrolment first lands.` — leaked-dev-metadata
Drop `(P03)`.

#### `adapters/outbound/storage/_google_drive.py:14` — `push by P03's coordinator, not by this provider).` — leaked-dev-metadata
Name the coordinator type.

#### `adapters/outbound/aeat/sede/_census.py:12` — `comprehensive census schema delta landed in / P01:` — leaked-dev-metadata
Drop `P01`.

#### `adapters/outbound/aeat/sede/test_renta_web_open_capture_replay.py:11,296` — `Phase H6 (oracle linkage)` / `Phase H6 oracle-linkage gate` — leaked-dev-metadata
Drop `Phase H6`.

#### `adapters/persistence/storage/master_key/_zeroise.py:21` — `out of scope for the present / phase.` — leaked-dev-metadata
Reword to "out of scope for this module".

#### `adapters/persistence/storage/envelope/_envelope.py:245` — `Per-step debug logging records the attempted chain (vs-M-6); … (sec-M-5)` — leaked-dev-metadata
Drop ADR-row IDs.

#### `adapters/persistence/storage/bucket/__init__.py:3` — `and (in later phases) the` — leaked-dev-metadata
Describe scope without phases.

#### `adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py:92,103,125,153` — `# Phase 1: original saves under natural keys.` (+3 peers) — ambiguous-needs-adjudication
Rename to `# Stage N` or numeric markers.

#### `adapters/outbound/aeat/auth/_authenticator.py:843,847,851` — `# Step 1: latch _closing under the lock` (+2 peers) — ambiguous-needs-adjudication
Numeric markers `# 1.` / `# 2.` or single docstring.

#### `adapters/persistence/storage/test_sensitive_persistence_policy.py:163,168` — `"developer registry parity tape generation"` (×2) — leaked-dev-metadata
Reword to `"registry parity tape generation (build-time artefact, not operator data)"`.

#### `adapters/persistence/storage/test_sensitive_persistence_policy.py:183` — `"explicit developer registry verification report export through the registry service"` — leaked-dev-metadata
Reword to `"explicit registry verification report export (build-time artefact)"`.

#### `adapters/persistence/storage/test_sensitive_persistence_policy.py:188` — `"developer translation scaffold generation"` — leaked-dev-metadata
Reword to `"locale translation scaffold generation (build-time artefact)"`.

#### `adapters/persistence/storage/master_key/_test_master_key.py:46` — `without touching the developer's real` — leaked-dev-metadata
`operator's`.

#### `adapters/outbound/aeat/auth/test_clave_movil.py:227` — `a developer who ran 'aeat config auth configure'` — ambiguous-needs-adjudication
Rename to `a contributor who ran`.

#### `adapters/outbound/aeat/sede/test_renta_web_open_explore_dom.py:478` — `.vault/audit/ for the developer to inspect` — leaked-dev-metadata
`for a contributor to inspect`.

#### `adapters/outbound/google/_calc_sheets_apply.py:560,594-595` and `_calc_sheets_pull.py:276-290,406` — `_build_developer_metadata_requests` / `"createDeveloperMetadata": {"developerMetadata": {…}}` — real-aeat-concept (Google Sheets API)
No rename; add inline note that this is Google's API surface, not AEAT.

**Negative axes (clean):** no `wip|todo|staging|tmp|temp` production identifiers (`.tmp` is POSIX atomic-rename, keep); no `W##/P##/S##` in identifier names (only in docstrings); no agent names; no `aeat.application.waveN.*` HKDF namespaces (`aeat.application.filing.{draft,amendment,history}.v1` + `.workflow.run.v1` in `_rotation.py:386-417` is durable hexagonal vocabulary, correct); no browser-driver dev-process selectors; justificante regex at `inbound/justificante/_extract.py:67,124-139` correctly separates AEAT label `PRESENTADOR` from `NIF` value.

### Surface: CLI entrypoints — *pending*

### Surface: locales + i18n + core (`src/aeat/locales/`, `src/aeat/core/i18n/`, `src/aeat/core/errors/`, `src/aeat/core/paths.py`, `src/aeat/core/resources/`, `src/aeat/core/config.py`)

**Counts: real-operator-surface 4, leaked-dev-metadata 7, ambiguous-needs-adjudication 2.**

**This surface has the worst finding so far — hundreds of untranslated keys ship as their own keypath.**

#### `src/aeat/locales/{en,es,ca,hu}.yml:68-198, 292-368, 538-543, 785` — `*_help: cli.app.ledger.collectible_invoice.add_help` (self-referencing) — leaked-dev-metadata
**113 (en) / 233 (es) / 234 (ca) / 234 (hu)** `*_help` values in the `cli.*` namespace are pure keypath placeholders. Runtime `_humanise_key` only rescues when callers omit `default`; catalogue still ships unwritten copy. Operators run `aeat --help` and see `cli.app.ledger.collectible_invoice.add_help` literally. **Either complete every translation or delete the keys.**

#### `src/aeat/locales/{en,es,ca,hu}.yml:1163-1179` — `t_135562: review.adapters.t_135562` (17 keys × 4 locales = 68 placeholders) — leaked-dev-metadata
Random-digit scaffold keys; values mirror keypath. Rename to operator-facing adapter labels (e.g. `caixabank_norma43`) and write real copy.

#### `src/aeat/locales/{en,es,ca,hu}.yml:1280-1283` — `message_053465: Duplicate transaction detected within imported file.` — leaked-dev-metadata
Random IDs (`053465/082074/185962/829073`). Rename to `duplicate_in_import`, `duplicate_in_ledger`, `no_valid_transactions`, `large_gap_between_transactions`.

#### `src/aeat/locales/{en,es,ca,hu}.yml:20` — `t_944805: Invalid period format...` — leaked-dev-metadata
Rename to `invalid_period_format`.

#### `src/aeat/locales/{en,es,ca,hu}.yml:23,26,27` — `unsupported_modelo: aggregation.per_modelo.errors.unsupported_modelo` (3 self-references) — leaked-dev-metadata
Write real translations.

#### `src/aeat/core/resources/_errors.py:8` — `"phases of the migration."` docstring — leaked-dev-metadata
Replace with steady-state description.

#### `src/aeat/core/resources/_keys.py:7-8` — `"For the foundation phase the union is intentionally empty; subsequent phases append..."` — leaked-dev-metadata
Replace with steady-state contract description.

#### `src/aeat/core/errors/registry/_adapters.py:594` — `code="FAIL_STORAGE_MIGRATION"` — ambiguous-needs-adjudication
Could be legitimate operator-visible "schema upgrade failed" or internal lifecycle leak. Adjudicate based on whether operators encounter and discuss "migration" directly.

#### `src/aeat/core/errors/registry/_adapters.py:1320` — `code="REFUSED_STORAGE_BUCKET_LEGACY_LAYOUT"` — ambiguous-needs-adjudication
Same shape — "legacy layout" describes a real pre-upgrade on-disk state but uses dev vocabulary.

**Confirmed clean (real operator surface, 4):**
- `core/config.py:688` — `default="claude-sonnet-4-6"` is a legitimate vendor-model identifier (provider-agnostic via `aeat_llm_provider`).
- `locales/{en,es,ca,hu}.yml:530/634/639` — `next_step` wizard copy; "Step N of M" is operator progress, not dev process.
- `locales/{en,es,ca,hu}.yml:239,242` — `override_help: Temporary binding override...` "Temporary" describes operator-controlled override lifetime.
- Error registries `_core.py`, `_application.py`, `_adapters.py`/`_domain.py`/`_entrypoints.py` — all `code=` and `message_key=` values use the operator-facing taxonomy (`REFUSED_*`, `FAIL_*`, `INTEGRITY_*`, `INTERNAL_*`, `LOCKED_*`, `AUTH_*`, `ERROR_*`).

`developer_nif` / `developer` / `presentador` do NOT appear in this surface — all confirmed instances live under registry TOMLs (sibling agent's surface). `core/config.py` field names operator-facing (`aeat_sede_*`, `aeat_llm_*`, `aeat_database_url`); no `dev`/`staging`/`tmp`/`wip` env vars.

## Recommendations

1. **TOML rename sweep first:** all 10 `developer_nif` instances → `presenter_nif`, plus `developer_tax_id` (115.toml). Run as one atomic commit so the caller-binding ripple is contained.
2. **Production comment strip:** `domain/buckets/_event.py:85` carries a W##.S## comment in canonical production code. Strip; the ADR reference goes in the commit message + vault doc, not the code.
3. **Test prose strip:** 8 test docstrings carry W##/S##/Phase H# refs. Move the process context to vault audit / plan docs; the test docstring should describe the invariant, not the project artefact that motivated it.
4. **LLM model id placeholders:** swap `claude-opus-4-6` literals in unrelated fixtures for `test-model`.
5. **ADR for the LLM-vendor namespace:** `domain/transactions/` legitimately interacts with multiple LLM providers; the question is whether the vendor names belong in the domain layer at all (the rule `no_transient_dev_metadata_in_code` would say no — push vendor IDs to an adapter and reference an abstract provider tier in domain).
6. **Add memory rule:** the maintainer prose pattern ("so the developer can fix") is legitimate but borderline; if it grows it will rot into the operator surface. Worth a stylistic-guidance note.

## Surface: CLI entrypoints (src/aeat/entrypoints/)

Read-only audit of `src/aeat/entrypoints/` (excluding `__pycache__/`) for
operator-facing surface leaks of development / process concepts: verb names,
sub-verb names, option flags, help text, error / refusal messages, payload
keys emitted via `_emit`, and text-mode output line labels. Reference
regression: `developer_nif` (operator NIF conflated with software-developer
NIF). The sibling registry-TOML audit logged 10 instances; this audit
verifies whether the CLI surface re-exposes any analogous leak.

### `src/aeat/entrypoints/cli/_config/_profile_census.py:10` - module docstring leaks `P03.S27` + driver code `G313`

Verbatim: "`refresh` is mounted but refuses with a typed CLI boundary error
until the sede G313 driver (P03.S27) lands - the verb is visible in `--help`
so operators see the canonical name now and get an explicit message about
what is missing rather than a silent absence."

Classification: leaked-dev-metadata. Module docstring leaks plan / step id
`P03.S27` and internal driver code `G313`. Not emitted at runtime, but
violates source-hygiene rule against phase / wave / step ids in production
source. Proposed: rewrite docstring to drop `(P03.S27)` and `G313`; describe
the refusal in operator-neutral domain terms.

### `src/aeat/entrypoints/cli/_overview.py:41-43` - verb docstring cites ADR + compatibility shim

Verbatim: "The deadline-calendar surface that used to live behind
`--calendar` is now the first-class `aeat app overview calendar` verb per
the app-overview-shape ADR Consequences section. No compatibility shim is
preserved; callers must use the dedicated verb."

Classification: leaked-dev-metadata. Proposed: drop the ADR citation and
the compatibility-shim sentence; keep only the operator fact that
`--calendar` is no longer accepted.

### `src/aeat/entrypoints/cli/_modelo.py:2023` - section comment cites `W72` + apex spec

Verbatim: "# History verb (W72 modelo-grammar-reconcile, apex 4.3)"

Classification: leaked-dev-metadata. Section comment embeds `W72`, the
`modelo-grammar-reconcile` cluster name, and an `apex 4.3` specification
reference. Proposed: replace with a stable domain comment (for example
"# History verb - chronological modelo lifecycle audit") or remove.

### `src/aeat/entrypoints/cli/_modelo.py:2186-2187` - verb docstring cites app-modelo-shape ADR amendment

Verbatim: "returns the verdict. The verb is local-only per the
app-modelo-shape ADR amendment."

Classification: leaked-dev-metadata. Proposed: drop the ADR clause; keep
local-only as a standalone operator fact.

### `src/aeat/entrypoints/cli/_config/_google.py:486` - private helper docstring cites phase `P04`

Verbatim: "sha256(namespace + object_key); a per-profile keyed HMAC for
unlinkability lands alongside P04 (snapshot escrow + HKDF)."

Classification: leaked-dev-metadata. Proposed: replace `P04` with the
durable feature name (snapshot escrow + HKDF rollout).

### `src/aeat/entrypoints/cli/_config/_google.py:918` - developer-metadata is real Google Sheets API terminology

Verbatim: "The workbook developer-metadata stamps must match the supplied
snapshot `(modelo, revision, period, year)` quadruple."

Classification: real-operator-surface. `developerMetadata` is the canonical
Google Sheets API field name; this is correct technical terminology for the
Google adapter surface, not a process leak. Proposed: no change. Optionally
backtick as `developerMetadata` to make API provenance explicit.

### `src/aeat/entrypoints/cli/_app_live.py:228` - comment not shipped here

Verbatim: "# capture verb (not shipped here) would invoke require_live_read."

Classification: ambiguous-needs-adjudication. Comment-only, not in output.
Mild process leak. Proposed: rephrase as the capture verb, when present,
would invoke `require_live_read`, or remove if no future verb is planned.

### `src/aeat/entrypoints/cli/test_profile_census_verbs.py:5-7,185` - test docstrings embed `P03.S27` + `P05.S54`

Verbatim (lines 5-7): "cleanly with the sede driver not wired message;
show/compare/apply directly (the production refresh path lands when
P03.S27 wires the". Verbatim (line 185): "stale-cascade walker (P05.S54)
has a typed event to react to."

Classification: leaked-dev-metadata. Test module docstrings embed `P03.S27`
and `P05.S54` plan references plus the phrase sede driver not wired.
Verified the assertions check operator-readable locale strings, not the
leaked phrases - but the test prose still violates source hygiene.
Proposed: rewrite both docstrings without phase / step identifiers.

### `src/aeat/entrypoints/cli/test_ledger_verb_spine.py:74` - test docstring cites `W72`

Verbatim: "The W72 trio is mounted directly under `aeat app ledger`, not"

Classification: leaked-dev-metadata. Proposed: replace W72 trio with a
stable domain phrase naming the actual three verbs being asserted.

### `src/aeat/entrypoints/cli/test_overview_explain_verb.py:46` - test identifier embeds `w81`

Verbatim: "def test_overview_verb_roster_locks_w81_five_verb_tree() -> None:"

Classification: leaked-dev-metadata. Test identifier embeds `w81` wave
reference. Proposed: rename to
`test_overview_verb_roster_locks_five_verb_tree`.

### Negative confirmations (no CLI runtime leak)

CLI verb names, sub-verb names, and option names (`--foo` flags + command
arguments) under `src/aeat/entrypoints/cli/` are clean: no `developer`,
`dev`, `wip`, `todo`, `staging`, `tmp`, `temp`, `phase`, `wave`, `step`,
`W##`, `P##`, `S##`, ADR / plan refs, or agent names. Help text passed to
`tr(...)` and rendered to operators is operator-readable Spanish / English
throughout (verified `_app_live.py`, `_modelo.py`, `_overview.py`,
`_ledger.py`, `_config/__init__.py`, `_config/_profile_census.py`,
`_config/_google.py`). Payload keys emitted via `_emit` use stable domain
vocabulary (`bucket_id`, `snapshot_id`, `actor`, `profile_id`,
`verification_state`, `findings`, `tax_id_present`, `iva_regime`,
`next_action`). Text-mode line labels match operator vocabulary (`actor`,
`profile`, `state`, `iva.regime`). The internal helper
`_resolve_default_actor` is underscored Python and never surfaces - the
on-the-wire key is `actor`, which is correct (parallel to the registry
TOML `developer_nif` -> `presenter_nif` recommendation, the CLI already
exposes the operator concept as `actor` / `--by`). The i18n keys
`cli.config.status.next_step`, `cli.overview.status.next_landing_command`,
`cli.overview.status.next_import_command`, and
`cli.overview.status.next_review_command` are internal lookup keys; the
rendered locale strings in `src/aeat/locales/{en,es,ca,hu}.yml` are
operator prose. landing is operator UX vocabulary (landing screen), not
process vocabulary. No not-implemented / TODO / placeholder / not-wired
string is emitted to operators from the CLI runtime path. The token `stub`
only appears in source-hygiene guard tests (`test_backend_boundary.py`),
not in operator output. No test asserts against a leaked dev string in a
way that would lock the leak in.

### Cross-reference to sibling registry-TOML audit

The sibling registry-TOML audit identified `developer_nif` ->
`presenter_nif` (10 confirmed leaks). The CLI surface does not re-expose
`developer_nif`: the closest concept (operator attribution on bucket
events) is already named `actor` (Python parameter, payload key, text
label) and `--by` (option flag). When the registry-side rename lands,
the CLI is not expected to require any verb / flag / payload changes;
the only follow-up is to confirm filing-export payloads still serialise
to the renamed field. Out of scope for this CLI-only audit; flagged for
the export-application audit.

cli: real=1, leaked-dev-metadata=8, ambiguous=1
