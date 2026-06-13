---
tags:
  - '#audit'
  - '#dead-code-purge'
date: '2026-06-13'
modified: '2026-06-13'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace dead-code-purge with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

## Recommendations

Delete each confirmed-dead symbol, grouped by domain, as explicit-path commits
with `ruff --fix` (to prune now-unused imports) and a clean `pytest
--collect-only` immediately before commit, per the relocation/deletion
discipline. Track per-file in the sibling plan. Process the 95 methods and 28
classes through the same vulture→AST→cross-reference confirmation in a follow-on
batch (methods need extra care for protocol/ABC/override membership).

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
