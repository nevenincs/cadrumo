---
tags:
  - '#audit'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
related: []
---



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

### F4 (LOW — reclassified after source confirmation) — scattered European-decimal idiom, but the parsers are not substitutable

Initial Pass-2 framing flagged the European number-format idiom
(`.replace(".", "").replace(",", ".")` → `Decimal`) across six production files
as a clean cluster missing a shared primitive. Source-level confirmation (the
per-site substitutability check the plan steps mandated) reverses that: the six
sites share only a trivial one-to-two-line separator-replacement kernel, each
wrapped in genuinely different, non-shared logic that the substitutability
pre-filter forbids merging:

- `sede/_iva_compensation_wallet_parsing._parse_spanish_decimal` — NBSP
  normalisation + full-Spanish + `re.sub(r"[^0-9.\\-]", "")` currency/symbol
  stripping + raises `SedeParseError` with a translated message on empty.
- `sede/_censo._parse_m2` / `_parse_withholding` — regex-`match`-gated on a
  pre-validated capture group, comma-only, one returns `str` not `Decimal`,
  raises `CensoParseError`.
- `registry/_export_parse._parse_xml_decimal` / `_parse_decimal` — comma-only,
  empty defaults to `Decimal("0")`, raises `RegistryValidationError`.
- `registry/_renta_web_open_oracle._parse_decimal_text` — conditional Spanish
  (only when a comma is present), returns `None` on failure.
- `inbound/pdf/_label_regex` — the most sophisticated: detects which separator
  is decimal via `rfind(",") > rfind(".")`, strips all whitespace, handles `-`,
  returns `None` on failure.

The shared kernel is trivial; the defaults (raise / `None` / `Decimal("0")`),
pre-validation, symbol stripping, locale detection, and error types are all
site-specific and load-bearing. Extracting only the kernel would dedupe one or
two lines per site at real risk of subtly changing AEAT-data parsing — a poor
trade. F4 is reclassified LOW and not actioned; like F1 it is intentional
site-specific divergence around a trivial common idiom, recorded so a later pass
does not re-flag it. The originating Pass-2 framing is left visible above as the
worked example of the lexical-idiom false positive the pre-filter catches.

**Meta-finding:** after the prior `semantic-cluster-hardening` and
`code-duplication-sweep` campaigns, the codebase's residual "duplication" is
overwhelmingly intentional divergence or trivial-idiom sharing; genuinely clean,
substitutable competing implementations (F3) are now rare. Future passes should
weight the substitutability pre-filter heavily and expect a high ruled-out rate.

### F5 (MEDIUM) — `storage_validation_error` factory copy-pasted across seven storage modules (Pass 3, landed)

Surfaced by a whole-tree structural sweep (production-only function names defined
in three or more files) rather than semantic concept search. The
`_storage_validation_error(message)` factory and its
`_STORAGE_VALIDATION_MESSAGE_KEY` constant
(`"errors.integrity.integrity_storage_validation"`) were **byte-identical** in
seven persistence-storage submodules: `crypto/_encrypted_columns.py`,
`envelope/_envelope.py`, `runtime.py`, `secret_store/_secret_store.py`, and the
three `master_key/` helpers (`_bucket_session.py`, `_idle_timeout.py`,
`_recovery.py`). Every copy constructs the same `StorageValidationError` with the
same translated-message key — a clean, fully-substitutable duplication (the F3
shape). Resolved: one canonical `storage_validation_error` promoted to
`storage/errors.py` (beside the error class), imported under each module's
existing private name; the seven duplicate defs and seven duplicate constants
removed. Behaviour-preserving — 842 storage tests pass, ruff and collect-only
clean. The structural sweep is recorded as the higher-yield discovery instrument
for this class (identical small helpers across modules), complementing the
semantic RAG passes.

### Structural-sweep candidates queued for a focused pass (confirmed, marginal)

The structural symbol sweep surfaced further same-named production helpers whose
consolidation is genuine but low-value; they are recorded here so a fresh-context
pass can decide them without re-discovery, rather than churn-landed at marginal
gain:

- `_metric_line` — byte-identical one-line `f"{key}={value}"` in
  `cli/_app_live_auth_preflight.py`, `cli/_app_live_expedientes_cli.py`,
  `cli/_app_live_rendering.py` (the `cli/registry.py` copy diverges: it translates
  the key). A one-line formatter; a shared helper adds import indirection for
  near-zero dedup.
- `_run_auth_preflight` — a four-line registration guard in
  `cli/_app_live_expedientes_cli.py`, `_app_live_justificante_cli.py`,
  `_app_live_notifications_cli.py`, identical except the command-family name in the
  error message and coupled to each module's `_auth_preflight` global; a shared
  helper would need both threaded through.
- `_active_bucket_id` (6 CLI modules), `_bucket_id` (4), `_drive_service` (3,
  divergent return/service), `_snapshot_from_record` (3 live modules) — not yet
  source-confirmed; next structural pass.

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
- **Enum-to-string coercion family (Pass 3)** — `_enum_value` in
  `aggregation/_ledger_filing_snapshot.py` (`str | None`, `None` → `None`) and in
  `domain/submission/_preflight.py` (`str`, `None` → `""`) share a name but have
  divergent return/null contracts; `review/_filter.py:_enum_value_or_raise`
  raises, and `terminology/_schema.py:_coerce_str_enum` runs the reverse
  direction (string → enum). A divergent family, not one substitutable helper.
- **Per-package secure-objects factories (Pass 3)** —
  `secure_objects_for_modelo_bucket`, `secure_objects_for_filing_bucket`,
  `secure_objects_for_application_filing_bucket` are byte-identical deferred-import
  delegations to the adapter `secure_object_repository_for_bucket`. They exist to
  hold the deferred adapters import at each package boundary; the canonical lives
  in the adapters layer, so no shared home exists that the `.importlinter` layer
  contracts permit (core cannot import adapters). Legit per-package boundary
  pattern, not actionable duplication.

## Verification status (Passes 1–3)

Three discovery passes have swept ~40 functional concepts via `vaultspec-rag`,
plus one whole-tree structural symbol sweep, each candidate confirmed at source
under the substitutability pre-filter. Two clusters were cleanly-actionable,
behaviour-preserving consolidations and are landed: F3 (repository bucket-id
resolvers) and F5 (the `storage_validation_error` factory, found by the
structural sweep). Every other candidate is intentional divergence, a trivial
shared idiom wrapped in non-shared logic, an architectural boundary shim, or a
canonical-plus-consumers shape — none safely removable without changing
behaviour or breaching layer contracts. The structural symbol sweep proved the
higher-yield instrument for the identical-small-helper class and should lead each
future pass, with semantic RAG covering the cross-vocabulary concept space. This is the expected post-hardening
profile (the prior `semantic-cluster-hardening` and `code-duplication-sweep`
campaigns removed the bulk of true duplication). The codebase is, on the swept
surface, verifiably lean: the remaining lexical/semantic clustering is
documented here so future passes do not re-flag it. The campaign continues as a
standing cadence over the still-unswept functional surface, not as open
remediation debt — F2's owner-gated `_formats` deletion is the one tracked
open decision.

## Execution update — behavior-preserving consolidations landed (F4, F6, F7)

A directive correction reframed the campaign's action threshold: the
substitutability pre-filter blocks only **behavior-changing** merges (F1's
documented CIF legacy tolerance, F2's safety-critical encoder); every
**behavior-preserving** consolidation — even of a trivial idiom — is to be
landed, not deferred as "marginal." Under that corrected stance the following
clusters, earlier recorded as ruled-out or queued, were consolidated and landed:

- **F4 (now landed)** — `core.decimal.normalize_decimal_separators` (explicit
  `strip_thousands` mode) promoted; the eight inline comma/dot separator sites in
  `sede/_iva_compensation_wallet_parsing.py`, `sede/_censo.py`,
  `registry/_export_parse.py`, `registry/_renta_web_open_oracle.py`, and
  `inbound/pdf/_label_regex.py` redirected, each keeping its own validation,
  symbol-stripping, locale-detection and error handling. 1080 parsing tests pass.
- **F6 (landed)** — the live-CLI `_metric_line` formatter (3 identical copies)
  and the auth-preflight registration guard (3 copies) consolidated onto
  `_app_live_auth_preflight._metric_line` and a shared
  `run_auth_preflight(preflight, *, family)`.
- **F7 (landed)** — the live-CLI `_bucket_id` active-bucket guard (4 identical
  copies: expedientes, justificante, notifications, verify) consolidated onto a
  shared `resolve_active_bucket(active_bucket_id, *, family)`; the per-module
  wrappers delegate, leaving 24 call sites unchanged.

- **F8 (landed)** — the two byte-identical `_require_transaction` guards in
  `application/ledger/_review_projection.py` and `_actions_common.py` consolidated
  onto the canonical in `_actions_common`; the domain-layer
  `_service._require_transaction` (no application context) stays separate.

Running total: **six clusters** consolidated and landed (F3, F4, F5, F6, F7, F8),
removing roughly thirty duplicate definitions/idioms, all behavior-preserving and
individually tested. Still genuinely not actionable without a behavior change:
**F1** (the strict-vs-legacy-tolerant tax-id surfaces diverge on the CIF leader
set and return type) and **F2** (the dormant fichero `_formats` stack — an
owner/ADR decision because it is the AEAT submission wire-format encoder).

**Structural sweep exhausted.** A whole-tree scan of production function/class
names defined in three or more files was driven to completion. Every remaining
same-named cluster resolves to one of: already-consolidated thin wrappers that
delegate to a shared canonical (`_parse_date`, `_bucket_id` post-F7, the
per-domain repository factories), divergent same-named implementations with
distinct contracts (`_snapshot_from_record`, `_drive_service`, `_load`,
`_enum_value`, the tax-id and decimal-parse wrappers), trivial one-line aliases of
an already-canonical function (`_repository`), or test fixtures. No further clean,
behavior-preserving, substantial duplication remains on the swept surface; the
codebase is verifiably lean against both the semantic-concept and structural-name
discovery instruments, with F1 and F2 the two documented, intentionally-retained
exceptions.

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


