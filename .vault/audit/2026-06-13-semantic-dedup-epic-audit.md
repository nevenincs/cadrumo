---
tags:
  - '#audit'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
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

# `semantic-dedup-epic` audit: `Semantic Deduplication Discovery Pass 1`

## Scope

First discovery-and-confirmation pass of the codebase semantic-deduplication
epic. Goal: rid the codebase of duplicate functionality, semantic shadows,
overlapping and competing tax/functionality implementations toward a verified
clean and lean codebase.

Method (RAG-discovers, `rg`-confirms): 24 functional-concept semantic queries
were run against the resident `vaultspec-rag` code index (`--port 8766`,
score floor 0.45, locale rows filtered), producing 280 candidate hits. Hits
were clustered per concept; concepts with two or more distinct production
files implementing the concept were promoted to candidate clusters. Each
candidate was confirmed by `rg`/source inspection under the **substitutability
pre-filter**: a site is only actionable as removable-in-favour-of-canonical
when the canonical site's constraint shape is a superset of (as-permissive-or
more than) the candidate's. Prior closed campaigns `semantic-cluster-hardening`
(37/37) and `code-duplication-sweep` (superseded) were treated as settled; this
pass audits the current post-fix state.

This is Pass 1 of a continuing cadence. The concept list (24) is a small
fraction of the codebase's functional surface; subsequent passes extend
coverage. Findings are tracked per-file as plan steps in the sibling plan.

## Findings

Severity reflects deduplication confidence and blast radius, not user harm.

### F1 (HIGH) — Spanish tax-id validation is implemented twice

`core/identity/_tax_id.py` and `core/identity/_documents.py` both implement
NIF/NIE/CIF validation and the AEAT control-letter computation. `_tax_id.py`
defines `nif_check_letter` and documents it as *"the single source of the
table `TRWAGMYFPDXBNJZSQVHLCKE` indexed by number % 23"*, yet
`_documents.py` independently defines `_compute_nif_check_letter` over a
parallel `_NIF_LETTERS` constant using the same `% 23` algorithm, plus its own
`_validate_nif` / `_validate_nie` / `_validate_cif`. A single consumer,
`domain/calculations/registry/_schema_scalars.py`, already imports from
**both** modules (`IdentityError` from `_documents`, `validate_spanish_tax_id`
from `_tax_id`), proving the split is incidental rather than layered. This is a
semantic shadow: one module asserts canonical authority while a second copy
exists. Consumers: `_tax_id` exports feed `_schema_scalars` and test helpers;
`_documents` exports (`validate_identity`, `IdentityDocument`, `IdentityError`)
feed `application/wizard/_widgets.py`.

### F2 (MEDIUM-HIGH) — fichero-BOE money-format `_formats` stack is an unconsumed parallel implementation

`adapters/outbound/aeat/export/_formats/` carries a complete currency
encode/serialise/deserialise stack (`encode_currency` in `_record_spec.py`,
`_encode_currency_field` in `_serialise.py`, the `_deserialise.py`
counterpart). Its leaf formatter computes the identical numeric result as
`application/filing/_export.py:_format_money`
(`round_half_up(abs(value), 2dp) * 100`, zero-padded, optional sign byte). The
confirming sub-agent found the entire `_formats` stack has **zero production
consumers** outside its own package and tests: every registry modelo
`application_links` TOML declares `consumer = "aeat.application.filing.export_draft"`
(routing through `_format_money` + `_render_layout`), and the verify path
decodes through `domain/calculations/registry/_export_parse.py`, not the
`_formats._deserialise` counterpart. At the concept level this is real
duplication (one algorithm, two homes); the substitutability pre-filter blocks
a one-line redirect because the two formatters are driven by different layout
definitions, so the resolution is removal-or-justification of the dormant
stack, not a merge.

### F3 (MEDIUM) — per-domain repository bucket-id resolution is copy-pasted boilerplate

`resolve_filing_repository_bucket_id` (`domain/filing/_runtime_repository.py`),
`resolve_modelo_repository_bucket_id` (`domain/modelos/_runtime_repository.py`)
and sibling per-domain resolvers repeat the same explicit-or-active-bucket
body (`if bucket_id is not None: trimmed = bucket_id.strip(); if trimmed:
return trimmed; ... fall back to active bucket`), differing only by the typed
`error_type`. The structural logic is one algorithm copied across domain
runtime-repository modules; it can be expressed once as a shared helper
parameterised by `error_type` (the modelo resolver already takes `error_type`).

### F4 (MEDIUM) — Spanish/European decimal-format parsing is reimplemented inline across six files (Pass 2)

The European number-format normalisation that maps a Spanish-formatted numeric
string (thousands dot, decimal comma) to a `Decimal` is open-coded inline in six
production files, with no canonical helper: `sede/_iva_compensation_wallet_parsing.py`,
`sede/_censo.py`, `ledger/_evidence_advisory.py` (`_parse_amount`),
`registry/_export_parse.py` (two sites), `registry/_renta_web_open_oracle.py`,
and `inbound/pdf/_label_regex.py` (two sites). Two variants exist and are NOT
interchangeable: the full form `.replace(".", "").replace(",", ".")` (strips
thousands dots) and the comma-only form `.replace(",", ".")` (assumes no
thousands separators). A value like `"1.234"` parses to `1234` under the full
form and `1.234` under the comma-only form, so a naive merge would change
behaviour. The actionable consolidation is one canonical helper with an explicit
thousands-separator mode, plus a per-site substitutability check before each
redirect (some sites also strip currency symbols or signs and must keep that).
This is a clean cluster (a true shared primitive is missing) but a careful one;
it is tracked as plan Wave W02 with one step per site.

### Ruled out under the substitutability pre-filter (no action)

- **Decimal cent-rounding** — `domain/calculations/registry/_formula_runtime.py:_apply_rounding`
  already imports and delegates to the canonical
  `core.money.round_to_cents`; its `integer` branch is a distinct rounding mode.
  Not duplication.
- **Decimal coercion** — `adapters/outbound/google/_calc_sheets_pull.py`
  already imports and calls the canonical `core.decimal.coerce_decimal`;
  `_coerce_edit_value_to_decimal` is a thin shape-specific wrapper. Not
  duplication.
- **IVA invoice classification** — `domain/iva/_classification.py:classify_iva`
  (full closed decision-table over 7 axes) and
  `_invoice_classification.py:classify_invoice_line_for_iva` (narrow
  domestic-only helper, different input/output contract that explicitly defers
  complex cases) are layered, not competing; `invoices/_models.py` is a pure
  delegating consumer. Constraint shapes are non-substitutable.
- **Renta ledger aggregation** — `_renta_ledger.py` (expense, annual, OUTGOING)
  and `_renta_income_ledger.py` (income, quarterly cumulative YTD, INCOMING)
  have disjoint input domains and non-overlapping casilla outputs; shared
  concerns are already extracted. Not duplication.
- **IVA cuota math** — `domain/iva/_saturation.py:split_gross_at_rate`
  (inverse split of an IVA-inclusive gross) versus
  `aggregation/_oss_ioss.py:_expected_iva_amount` (forward base × rate) are
  different operations; both correctly use `round_to_cents`. Not duplication.
- **Attachment/evidence persistence** — `AttachmentStore` (storage primitive),
  `domain/attachments/_service.py` (domain service over the store protocol)
  and `application/ledger/_evidence.py` (composes the store for evidence) are a
  clean hexagonal/composition layering. Not duplication.

## Recommendations

Track each confirmed finding (F1–F3) as a plan phase whose steps name the
exact per-file site and its action (delete / redirect-to-canonical /
merge-into-canonical / extract-shared-helper) plus a verification gate, in the
sibling `semantic-dedup-epic` plan. Execute each as an atomic explicit-path
relocation commit with a clean `pytest --collect-only` immediately before
commit, per the architecture-boundaries relocation discipline.

- **F1:** make `_documents._compute_nif_check_letter` delegate to the declared
  single source `_tax_id.nif_check_letter`; consolidate the duplicated
  `_validate_nif/_nie/_cif` core into one owning module; keep the two public
  surfaces (`validate_spanish_tax_id` returning a normalised `str`;
  `validate_identity` returning a typed `IdentityDocument`) re-expressed over
  the single core; migrate `_schema_scalars` to a single import site.
- **F2:** confirm zero production consumers tree-wide, then delete the dormant
  `_formats` currency encode/serialise/deserialise path (per the
  no-dormant-source-resolvers and no-legacy-compatibility disciplines), or
  record an explicit retention rationale if a near-term consumer is planned.
- **F3:** extract one shared `resolve_repository_bucket_id(bucket_id, *,
  error_type)` helper and redirect the per-domain copies to it.

The ruled-out clusters are recorded so a later pass does not re-flag them; the
substitutability pre-filter verdict for each is the durable result.

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
