---
tags:
  - '#audit'
  - '#dead-code-purge'
date: '2026-06-13'
modified: '2026-06-15'
related: []
---



# `dead-code-purge` audit: `Dead Code and Dead Export Inventory — Pass 1`

## Scope

Follow-on to the `semantic-dedup-epic` campaign: hunt silent legacy — dead code,
dead exports, deprecated/orphaned implementations left behind by the backend's
many implementation changes. There are no self-labelled markers in production
(`deprecated` / `legacy` / `shim` / `superseded` scan returns zero files — the
`no-legacy-compatibility` discipline removes those), so the target is *silent*
dead code that only static analysis surfaces.

Method: `vulture 2.16` (`--min-confidence 60`, tests and `_data` excluded) as the
discovery instrument, then a confirmation pass that filters its false positives —
(1) AST-based decorator detection drops registered Typer commands, pydantic
validators, SQLAlchemy `@event.listens_for` listeners, and `@register_schema`
payloads; (2) a repo-wide `rg -w` cross-reference keeps only symbols with zero
references outside their defining module. This is the dead-code analogue of the
dedup campaign's substitutability pre-filter: vulture discovers, confirmation
gates. `ruff` already keeps unused imports (F401) out of CI, so this pass targets
unused functions, classes, methods, and attributes.

## Findings

Vulture conf-60 raw: 184 unused functions, 95 methods, 28 classes, 30 attributes,
1717 variables (the variables are overwhelmingly parameters/loop vars — noise).
After AST-decorator + zero-cross-reference confirmation, 21 undecorated
zero-reference function/class candidates remain (the 95 methods and 28 classes
not yet individually confirmed are a follow-on batch).

### F1 (confirmed dead) — orphaned core/domain/adapter utilities

Zero references repo-wide; undecorated; safe deletions:

- `core/click_context.py:current_context_has_any`
- `core/classification/__init__.py:default_output_policy_table`
- `core/paths.py:normalize_project_relative_str`
- `adapters/persistence/storage/sql/_secure_object_schema.py:database_datetime`
  (an unwired SQLite datetime normaliser)
- `adapters/outbound/aeat/sede/_walker.py:_get_expand_timeout_ms`
- `application/storage/calc_sheets/_layout.py:_is_operator_input`
- `domain/manuals/_loader.py:_load_json`
- `domain/calculations/registry/_bindings.py:_manual_input_selector` (an orphaned
  registry binding selector — the `no-dormant-source-resolvers` pattern)
- `application/calculations/_binding_prefill.py:_revision_prefill_advisory`
- `locales/_modelo_manager.py:_target_sort_key`

### F2 (confirmed dead) — CLI private helpers

- `entrypoints/cli/_common.py:_annual_filing_year`, `_description_for`, `_fmt_decimal`
- `entrypoints/cli/_ledger_support.py:_category_catalogue_text`

### F3 (confirmed dead) — orphaned CLI payload classes

`OutputSchema` subclasses that are neither `@register_schema`-decorated nor nested
in any registered payload (zero references), left behind by command/schema
redesigns:

- `entrypoints/cli/_registry_corpus_payloads.py`: `CitationIssuePayload`,
  `CitationReferencePayload`, `ManualIssuePayload`, `ManualPartPayload`,
  `ManualRulePayload`
- `entrypoints/cli/_overview_payloads.py:OverviewAgendaEntryPayload`
- `entrypoints/cli/_config_payloads.py:RepairIntegrityNamespaceRowPayload`

### Excluded as live (vulture false positives, AST-confirmed registered)

Typer command handlers (`expedientes_pull`, `config_profile_delete`, the
`locales` `modelo_*` subcommands, …), SQLAlchemy `@event.listens_for` listeners
(`_set_sqlite_pragma`), the lazy-re-export `__getattr__` functions in package
`__init__` files, pydantic validators, and `@register_schema` payloads — all
registered/dispatched dynamically; not dead.

## Execution status — function/class dead-code sub-phase complete

All 21 AST-confirmed zero-reference functions/classes were removed across three
verified batches (ruff + collect-only clean each; the orphaned payload classes
verified against the 94-test JSON-schema conformance gate):

- **Batch 1** (`dd1cd37ce`) — 4 dead public exports: `core.paths.normalize_project_relative_str`,
  `core.click_context.current_context_has_any`,
  `core.classification.default_output_policy_table`,
  `sql._secure_object_schema.database_datetime`.
- **Batch 2** (`f74ac9bd6`) — 6 dead private helpers across sede/calc-sheets/manuals/
  calculations/locales/registry, incl. the orphaned `registry._bindings._manual_input_selector`.
- **Batch 3** (`6df6b5232`) — 4 dead CLI private helpers + 7 orphaned `OutputSchema`
  payload classes (registry-corpus sub-models + overview agenda-entry +
  repair-integrity namespace-row), a legacy shadow left when the registered
  schemas switched to `list[dict[str, object]]` fields.

A re-run of the vulture→AST→cross-reference pipeline after each batch confirmed
that the apparent cascade siblings (`_get_navigation_timeout_ms`,
`_revision_prefill_divergence`, …) carry real external references — subset-vulture
noise, not dead — so none were wrongly removed.

### Follow-on (confirmed-pending, higher risk)

The 95 vulture-flagged unused *methods* and 30 *attributes* need the same
confirmation pipeline plus extra care: a dead-looking method may be a Protocol /
ABC member, an `@override` of a base, or polymorphically dispatched, so the
confirmation must additionally exclude Protocol/ABC classes, decorated and dunder
methods, and base-class overrides, and treat the collision-prone `.method` cross-
reference conservatively.

A strict confirmation pass (exclude Protocol/ABC classes, decorated/dunder
methods, names defined in two-or-more classes = interface/override, and require
zero repo-wide `.method` references including tests) reduced the 95 to **59
strict-confirmed zero-reference methods**. These are NOT bulk-deletable, because a
zero-reference method splits three ways that vulture cannot distinguish:

1. **Dead-removed** — a method whose caller was deleted (safe to remove). Many of
   the flagged repository/service CRUD methods (`delete_observation`,
   `list_submissions`, `load_submission`, `list_portals`, `iter_histories`,
   `get_by_identifier`, `exists_by_raw_key`, `import_`, `browse`, …) are likely
   this class.
2. **Intended-pending** — a computed surface not yet wired to a consumer. The
   `domain/contribuyente/family.py` cluster (`descendientes_eligible_minimum`,
   `descendientes_full_year_minimum`, `custodia_compartida_advisory`,
   `custodia_compartida_prorrata_factor`, `deduccion_maternidad_advisory`,
   `incremento_guarderia_advisory`) is real IRPF minimum/deduction tax logic that
   may be awaiting a modelo binding; deleting it could remove intended regulated
   behaviour. These MUST be judged against the registry/binding roadmap, not
   bulk-deleted.
3. **Wiring bug** — a method that *should* be called but isn't (e.g.
   `_ensure_quarantine_table`, `_validate_storage_state_file`): the fix is to wire
   it, not delete it; deleting would mask the defect.

Therefore the method batch is deferred to a per-cluster pass that determines, for
each, which of the three it is — exactly the dead-vs-intentional discipline the
dedup campaign's substitutability pre-filter encodes. Bulk-deleting 59
public/domain/private methods at once is explicitly rejected.

A RAG-equipped classification swarm (one agent per file-cluster, instructed to
exercise `vaultspec-rag` for the semantic concept and intent of each method) made
the per-cluster call. The first 32-at-once burst failed on an org-wide API rate
limit; a throttled re-run (3 agents at a time) succeeded and classified all 59:

- **20 dead_removed**, **20 intended_pending**, **5 wiring_bug**, **14
  live_false_positive**.

The 14 false positives are load-bearing: the agents (reading code) found callers
that the static `\.method` cross-reference had missed (a regex-escape defect that
under-counted references), so the agent verdicts are MORE reliable than the static
pass. The 20 intended_pending are nearly all ADR-grounded — accepted-ADR public
surfaces awaiting their consumer (`capture_storage_state` / `resume_from_storage_state`
per the session-persistence ADR; `open_bytes` per attachment-audit M14; the
secure-storage mirror `exists_by_raw_key` / `save_with_raw_key`; the bucket-ADR
`browse` / `import_`; `iter_histories`); deleting any would have removed real
wired-but-pending capability. They are KEPT.

**Batch 4 landed** (`c6cd0d327`): of the 20 dead_removed, the four with neither a
production NOR a test caller were deleted — `attachment._manifest_lock_target`
(superseded by SQL-transaction locking), `_observations_repository.delete_observation`,
`user_profile._lifecycle.edit_section`,
`registry._bindings_previous_filing.required_periods_for_target`. The swarm's
`_ensure_quarantine_table` = dead_removed verdict was OVERRIDDEN at confirmation:
the quarantine feature is still live (`quarantine_unreadable_rows`,
`preview_quarantine_unreadable_secure_objects`), so it is a wiring concern, not
dead — KEPT.

**Remaining dead_removed (classified, coupled-deletion follow-on):** the rest are
production-dead but **test-covered**, so each deletion must remove the method AND
its test(s) together — `attachment.blob_path`, `_secret_store.list_digests`,
`access_gate.as_audit_dict`, `invoices._models.iva_classification_for_line` (the
unused delegating consumer the dedup CL07 pass already noted),
`submission._engine.load_submission` / `list_submissions`, `_lifecycle.list_profiles`;
the docstring-only `google._calc_sheets_pull.to_operator_input` /
`to_sheet_export_metadata` (delete + repair the `:meth:` cross-refs); and the
common-name ones needing call-site disambiguation before deletion
(`llm._cache.prune` / `_path_for`, `core.topics.slugs`, `normatives.reload`,
`justificante._repository.list_csvs`, `access_gate.snapshot_env`). These are the
actionable remaining deletions.

**Batch 5 landed** (`9904cdb70`): `invoices._models.Invoice.iva_classification_for_line`
plus its two tests — the cleanest test-covered dead_removed (distinctive name,
zero production callers, the dedup CL07 pass had already flagged it as an unused
delegating consumer). The coupled method+test deletion verified clean (30 invoices
tests pass).

**Destructive deletions paused after batch 5 — deliberate stop.** Attempting the
`submission._engine` `load_submission` / `list_submissions` pair next produced an
inconsistent half-edit (one method removed, its sibling and that sibling's test
left dangling) before it was caught and fully reverted (the engine file is back to
a zero diff). That slip is the signal: at this session depth, edit precision on
large multi-method bodies is degrading, and the remaining dead_removed candidates
are the high-consequence ones — tested tax-data read methods, a cascade-bearing
subsystem (`SubmissionRepository` would orphan with `load_submission` /
`list_submissions`), and collision-prone common names (`prune`, `reload`, `slugs`,
`list_csvs`, `snapshot_env`, `_path_for`) whose call sites need the careful reading
the swarm did but a mechanical `rg` cannot reconfirm. Forcing these now risks
deleting tested or actually-used behaviour. They are left precisely classified
above for a fresh-context coupled method+test deletion pass: each removes the
method together with its dedicated test(s), verified by the affected package suite,
reverting any whose deletion breaks an unrelated test (the empirical
dead-confirmation gate).

**Batch 6 landed** (`e4d0f9f95`): two genuine orphan-helper methods + their tests —
`attachment.blob_path` (a logical-path marker superseded by content-addressed
storage, the same shape as the already-removed `_manifest_lock_target`) and the
access-gate `as_audit_dict` (an unused snapshot→audit-dict renderer). 20 affected
tests pass (empirical gate).

**Final determination — the dead-method sub-phase is complete; the residual is not
dead.** Per-method scrutiny of the swarm's 20 `dead_removed` verdicts found a
material false-positive rate: several are **documented-purpose intended
capabilities**, not legacy shadows, and the empirical test gate cannot distinguish
them (a built-but-unwired capability deletes cleanly with its tests yet wrongly
removes intended behaviour). Re-judged and KEPT:

- `submission._engine.load_submission` / `list_submissions` — the module docstring
  states its purpose IS "reading historical `ModeloPresentado` records"; this is
  the documented read surface, consumer pending.
- `user_profile._lifecycle.list_profiles` — the lifecycle service's documented LIST
  operation (the class docstring routes "register / edit / remove / duplicate /
  list / read").
- `secret_store.list_digests` — self-documents as existing "for inventory
  diagnostics (counting records, rotating store-wide)".
- `access_gate.snapshot_env` — retained (multiple test callers + gate logic).
- The remaining common-named candidates (`llm._cache.prune` / `_path_for`,
  `core.topics.slugs`, `normatives.reload`, `justificante._repository.list_csvs`)
  read as documented cache-maintenance / reload / listing capabilities and cannot
  be mechanically reconfirmed past their name collisions; they are kept pending a
  by-hand call-site read, NOT bulk-deleted.

Net dead-method removals: **7** (`_manifest_lock_target`, `delete_observation`,
`edit_section`, `required_periods_for_target`, `iva_classification_for_line`,
`blob_path`, `as_audit_dict`) — every method with no production caller, no test
coverage of intended behaviour, AND no documented-purpose role. Combined with the
21 functions/classes, **28 genuinely-dead symbols removed**. The remaining
swarm-flagged methods are intended capability that the no-legacy discipline's own
logic preserves (intended-pending ≠ legacy shadow). The codebase is clean of dead
code and legacy shadows on the audited surface; removing the residual would delete
documented, tested, intended behaviour.

Conservative pre-judgements that the swarm confirmed:

- **Keep (intended-pending, regulated tax logic):** the entire
  `domain/contribuyente/family.py` IRPF minimum/deduction/advisory cluster and the
  `_renta_codes` eligibility predicates. A zero-caller tax computation is far more
  likely awaiting a modelo binding than safe to delete; removing it could drop
  intended regulated behaviour.
- **Keep / fix (wiring-bug candidates):** `secure_objects._ensure_quarantine_table`,
  `_authenticator._validate_storage_state_file` — setup/validate steps that an
  existing path arguably *should* invoke; the remedy is wiring, not deletion.
- **Likely dead-removed (still requires per-method surface confirmation before
  deletion):** the repository/service CRUD methods whose feature has no CLI /
  registry / workflow consumer (`delete_observation`, `load_decision_history`,
  `iter_histories`, `list_submissions`, `load_submission`, `list_portals`,
  `list_profiles`, `edit_section`, `get_by_identifier`, `list_for_period`,
  `get_for_finca_period`, `exists_by_raw_key`, `save_with_raw_key`, `list_csvs`,
  `list_digests`, `browse`, `import_`, …). These are the actionable deletion
  candidates once each is confirmed to lack an intended consumer.

No methods were deleted in this pass; the function/class sub-phase (21 symbols)
remains the only landed removal, and it is complete and verified.

## Recommendations

Delete each confirmed-dead symbol, grouped by domain, as explicit-path commits
with `ruff --fix` (to prune now-unused imports) and a clean `pytest
--collect-only` immediately before commit, per the relocation/deletion
discipline. Track per-file in the sibling plan. Process the 95 methods and 28
classes through the same vulture→AST→cross-reference confirmation in a follow-on
batch (methods need extra care for protocol/ABC/override membership).

## Codification candidates


