---
tags:
  - '#audit'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - "[[2026-06-13-semantic-dedup-epic-adr]]"
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
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

# `semantic-dedup-epic` audit: `Semantic Deduplication Discovery Pass 2 (RAG cluster sweep)`

## Scope

Pass 2 of the codebase semantic-deduplication epic, extending the 24-concept
coverage of Pass 1 (`2026-06-13-semantic-dedup-epic-audit`). Codebase-wide
sweep over the ~1,044 non-test Python modules of `src/aeat/`, driven by the
`vaultspec-rag` semantic index (120,929 code sections, fully rebuilt
2026-06-14 before the sweep). Six read-only Opus discovery agents covered
disjoint directory clusters: C1 `core/`; C2 `domain/calculations`,
`domain/modelos`, `domain/normatives`; C3 the `domain/` financial subtree
(`iva`, `renta`, `transactions`, `invoices`, `deadlines`, `filing`,
`iva_compensation`, `categories`, `usage_ratios`, `currency`, `contribuyente`,
`fincas`, `attachments`); C4 `application/`; C5 `adapters/`; C6
`entrypoints/cli/`.

Method (RAG-discovers, `rg`-confirms): each agent ran semantic queries by
functional concept, confirmed exact symbols with ripgrep, applied the
mandatory substitutability pre-filter (a candidate is only actionable when the
canonical target's constraint shape is a superset of the duplicate's — the
rule records a 96% false-positive rate without this gate), and re-verified
every survivor against HEAD. No production code was modified during discovery.

Pass 2 findings are additive and non-overlapping with Pass 1: F1 tax-id stays
centralized (reconfirmed, no finding); C1-3 below is a NEW `round_to_cents`
outlier distinct from F2's dormant `_formats` stack; Pass 1 F3 was the
domain/application repository resolver, whereas C6-1 below is the CLI-layer
guard; Pass 1 F4's European-decimal variants were correctly re-excluded by the
pre-filter. The headline holds across both passes: the tree is heavily
consolidated, and residual duplication is concentrated into ten well-defined
actionable clusters plus a constraint-divergent excluded set.

## Findings

Severity here is refactor risk, not correctness risk: every cluster is
quality cleanup, none is a live calculation bug.

### Actionable duplication clusters

- **C1-1 — `sha256_hex(bytes) -> str` (HIGH for named helpers, MED for tail).**
  Canonical: `src/aeat/core/hashing.py:17` (its docstring already instructs
  callers not to inline `hashlib.sha256(x).hexdigest()`). Byte-identical
  redeclarations: `src/aeat/adapters/persistence/storage/sql/_secure_object_crypto.py:11`
  (same name + signature), `src/aeat/application/storage/calc_sheets/_workbook_export.py:406`
  (`_sha256`). Plus a long inline tail of ~50 full-digest sites across
  `domain/`, `application/`, `adapters/` that are mechanical 1:1 swaps.
  Excluded: every truncated-digest `…hexdigest()[:16]`/`[:12]` site (different
  output shape).

- **C1-2 — chunked-read file SHA-256 (MED-HIGH).** Canonical:
  `src/aeat/core/hashing.py:26` (`hash_file`) / `:42` (`sha256_file`).
  Re-implemented 64 KiB-chunk loops: `src/aeat/adapters/inbound/pdf/_utils.py:22`
  (substitutable with error-wrap), `src/aeat/domain/calculations/registry/_sources.py:71`,
  `src/aeat/domain/manuals/_fetch.py:231`,
  `src/aeat/adapters/persistence/storage/attachment.py:222`,
  `src/aeat/adapters/inbound/sanitizer/_pipeline.py:225`.

- **C1-3 — inline euro-cent quantize (HIGH).** Canonical:
  `src/aeat/core/money/__init__.py:24` (`round_to_cents`). Lone outlier:
  `src/aeat/application/filing/_export.py:332` (`_MONEY_QUANT`) + `:563`
  re-derive `round_to_cents(abs(amount))` inline. The sibling fichero encoder
  `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py:315`
  already imports the canonical — proving the swap is behaviour-identical.

- **C2-1 — `selector_as_dict` binding-selector normalizer (HIGH).** Canonical:
  `src/aeat/domain/calculations/registry/_binding_selector_utils.py:12`
  (already `__all__`-exported and consumed by three modules). Byte-identical
  private clones: `src/aeat/domain/calculations/registry/_withholding_bindings.py:115`,
  `src/aeat/domain/calculations/registry/_bindings_previous_filing.py:224`,
  `src/aeat/domain/calculations/registry/_formula_initial_values.py:276`.

- **C2-2 — uppercase-alpha code validator + `_values_unique` (MED).** No shared
  home today; nominate a parameterized validator factory in
  `src/aeat/domain/calculations/registry/_binding_selector_utils.py`. The
  uppercase-alpha check is copied across ~7 observation models in the binding
  modules (`_invoice_bindings.py:81`, `_counterpart_bindings.py:66`,
  `_withholding_bindings.py:63`, `_detail_record_bindings.py:62/197/331/450`);
  the identical `_values_unique` tuple-uniqueness validator is copied 4×
  (`_invoice_bindings.py:141`, `_counterpart_bindings.py:122`,
  `_withholding_bindings.py:95`, `_bindings_previous_filing.py:43`). Only the
  error-message string varies — absorbable by a factory parameter.

- **C3-1 — `IvaRate -> IvaRateKind` mapping defined twice (HIGH).** Canonical:
  `src/aeat/domain/invoices/_enums.py:76` (`_IVA_RATE_TO_IVA_KIND`, exposed via
  `iva_rate_kind()` and already consumed cross-domain by
  `application/aggregation/_oss_ioss.py:250`). Duplicate dict rebuilt with
  lazy-import gymnastics: `src/aeat/domain/iva/_invoice_classification.py:85`
  (`_iva_rate_to_iva_kind`). Import direction invoices→iva already exists, so
  consuming the canonical adds no new dependency edge.

- **C4-1 — review payload duplicates base payload (HIGH; JSON-shape sensitive).**
  `src/aeat/application/ledger/_models.py:339` (`LedgerTransactionReviewPayload`)
  is a field-for-field copy of `:294` (`LedgerTransactionPayload`) plus one
  `review_status` field (incl. a copy-pasted `_validate_source_jurisdiction`);
  the builder `src/aeat/application/ledger/_actions_manual.py:301` likewise
  copies `:266`. Refactor: extract the common base, have the review shape
  extend it. Caveat: both are registered CLI `OutputSchema` payloads — the
  serialized JSON must stay byte-identical (`test_json_schema_conformance.py`
  guards drift).

- **C4-2 — `_display_decimal` triplication (HIGH).** Canonical:
  `src/aeat/application/ledger/_actions_common.py:557` (already reused by
  `_actions_manual.py:62`). Identical body re-declared at
  `src/aeat/application/ledger/_review_projection.py:198`.

- **C5-1 — content-hash integrity verification (MED).** No canonical home;
  the `sha256-`-prefix-strip + digest + compare + raise kernel is open-coded in
  `src/aeat/adapters/outbound/storage/_local.py:304` and
  `src/aeat/adapters/outbound/storage/_google_drive.py:609`. Extract only the
  shared compare-and-raise kernel; each backend keeps its own error message/context.

- **C6-1 — active-profile bucket-id guard (HIGH).** Canonical:
  `src/aeat/entrypoints/cli/_common.py:388` (`_active_bucket_id_or_bad`,
  delegating to the shared `_no_active_profile_refusal()` at `:132`).
  Per-file copies with identical bodies: `_ledger_inventory_cli.py:36`,
  `_ledger_ratios_cli.py:32` (+ `_ratios_bucket_and_profile` at `:43`),
  `_ledger_business_invoice_cli.py`, `_ledger_rules_cli.py`. Preferred shape:
  add a stateless `active_bucket_id_or_refuse()` to `_common` and route all
  through it.

### Constraint-divergent — correctly excluded (do NOT re-flag)

The pre-filter blocked these; each is recorded so a future pass does not
re-surface it as a false positive:

- **Period boundary math:** `domain/period.py:36/76` vs `core/_period.py:287/304`
  — `domain/period.py` handles instalment tokens `1P/2P/3P` that
  `core/_period.py` raises on, and uses a different monthly-end convention.
  A parallel boundary worth a future reconciliation ADR, not a mechanical dedup.
- **Decimal field validators:** base "reject bool/non-Decimal" vs the stricter
  "Decimal AND non-negative" superset in `_withholding_bindings.py:77`,
  `_detail_record_bindings.py:204/457` — the non-negative copies must NOT apply
  to signed-admitting fields.
- **File hardening:** atomic `os.open(..., 0o600)` create + dir `0o700` in the
  master-key/lock sites vs post-hoc `restrict_file_permissions` in
  `core/file_permissions.py:42` — atomic-create closes a race window a post-hoc
  chmod cannot.
- **NFKD text-normalize family (4 sites):** distinct transform shapes
  (case-preserving vs casefold vs ascii-drop vs whitespace-collapse); a
  consolidation needs a NEW parameterized core helper, not promotion.
- **Date parsers vs `core.parsing.parse_date`:** the boundary parsers return
  `datetime`/accept `%m/%d/%Y`; core returns `date` and is not a superset.
- **`_canonical_decimal_str` vs `_display_decimal`:** the former special-cases
  `is_zero() -> "0"` for content-address stability — different contract.
- **Truncated digests, USD-6dp pricing quantize, integer-quantize engine
  primitive, `_resolve_read_id` lineage-following vs live-row resolver,
  recargo-equivalencia vs late-filing-recargo, `IvaFlowDirection` vs
  `TransactionDirection`, `ModeloCode` shape-gate vs `Modelo` enum** — all
  semantically distinct despite vocabulary overlap.

### Zero parallel-write-path violations

C4 specifically hunted for services re-implementing single-writer primitives.
The one structural risk (observation persistence across `live` vs `modelo`)
was inspected and is a deliberate documented sibling pair — both delegate to
the single `CalculationObservationRepository.save_observation` writer with
intentionally different `source_kind` (official vs `app_filing`), which is
load-bearing safety semantics, not duplication.

## Recommendations

Action the ten clusters as atomic relocation commits per the
relocation-atomicity rule (one symbol = one canonical-site move + every
consumer update + `__all__`/`apidocs scaffold` updates + clean
`pytest --collect-only` = one commit tagged `relocation:<symbol>`).
Suggested ordering by risk/value, appended to the epic plan as Pass-2 waves:

1. **Lowest-risk, highest-confidence first (warm-up):** C4-2 (`_display_decimal`
   import), C2-1 (`selector_as_dict` clones), C1-3 (`round_to_cents` outlier),
   C3-1 (`iva_rate_kind`). Each is a delete-local + import-canonical with no
   public-shape change.
2. **CLI guard:** C6-1 — add stateless `active_bucket_id_or_refuse()` to
   `_common`, route the four `_ledger_*` copies through it.
3. **File-hash family:** C1-2 (delegate the five chunked loops to `hash_file`,
   pdf site keeps its error-wrap).
4. **Bulk sweep (mechanical, high volume):** C1-1 — first the two named helper
   redeclarations, then the ~50-site inline tail as a dedicated sweep; enumerate
   with `rg 'hashlib\.sha256.*hexdigest'` because RAG under-returns this tail.
5. **Factory extractions (design choice):** C2-2 (validator factory) and C5-1
   (content-hash kernel) — confirm the team prefers a factory/kernel over
   per-site methods before landing.
6. **Shape-sensitive last:** C4-1 — extract the payload base, lean on
   `test_json_schema_conformance.py` to prove the serialized shape is unchanged.

Each refactor pairs with a real-behaviour test or rides an existing gate; no
mocks/skips. Re-read each file at HEAD immediately before editing (fast-landing
shared worktree) and `git diff -- <file>` to abort on peer WIP.

## Codification candidates

None. The durable lessons this pass reconfirmed are already codified: the
RAG-under-returns-the-inline-tail / pair-with-`rg` lesson by
`aeat-rag-discovery`, the substitutability pre-filter by
`aeat-swarm-audit-cadence`, and canonical-home / relocation-atomicity by
`service-imports-via-top-level-reexports` and `aeat-architecture-boundaries`.
The findings are feature-specific remediation, not new cross-session
constraints — an empty codification section is the correct outcome.

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
