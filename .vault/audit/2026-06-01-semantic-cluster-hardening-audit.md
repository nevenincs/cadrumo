---
tags:
  - '#audit'
  - '#semantic-cluster-hardening'
date: '2026-06-01'
related:
  - "[[2026-06-01-semantic-cluster-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace semantic-cluster-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `semantic-cluster-hardening` audit: `Axis-7 semantic functionality-cluster swarm audit (delta)`

## Scope

Axis-7 (semantic functionality-cluster overlap) delta-audit over the
419-added / 1311-modified `.py` delta since the 2026-05-19 baseline. Six
parallel sonnet agents covered distinct functional families: numeric/money,
identifiers/validation, parsing/serialization, date/period/deadline,
persistence/repository/crypto, and errors/retry/http.

METHOD CAVEAT (material): the resident RAG GPU service was DOWN throughout the
sweep because the shared-venv `torch` had been downgraded to a CPU build
(CUDA unavailable). Discovery therefore degraded to `rg` only -
verification-grade, but the semantic-cluster (lexically-divergent,
same-meaning) discovery layer that RAG exists to provide did NOT run. The
findings below are `rg`-confirmed true-duplicates and enrollment gaps;
divergent classifications applied the mandatory substitutability pre-filter.
A full RAG semantic pass is PENDING torch restoration and must run before
W01.P02 is closed as complete.

## Findings

### F1 - Decimal cents-rounding triplication (TRUE-DUPLICATE, high)

Identical `value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` plus a
copied `_CENT` constant in `domain/fincas/_rounding.py:18`,
`domain/profile/inventory/__init__.py:503`, and
`domain/profile/assets/__init__.py:240`. Same constraint shape at all three.
Remediation: new canonical `core` money/Decimal primitive; the inventory and
assets sites import it. (W2 seed.)

### F2 - TOML open/parse/reraise replicated in five loaders (TRUE-DUPLICATE, high)

`domain/iva/_rates.py:44`, `domain/iva/_catalogue.py:35`,
`domain/categories/_registry.py:50`, `domain/deadlines/_recargo.py:72`, and
`domain/deadlines/_festivos.py:220` each reimplement the open + `tomllib.load`
+ catch `TOMLDecodeError`/`OSError` + reraise-domain-error triad that
`core/_toml.py:read_toml` already centralises via an `error_factory` argument.
Substitutable. Remediation: route all five through `read_toml`.

### F3 - `_to_str_dict` duplicated (TRUE-DUPLICATE, high)

Byte-identical `_to_str_dict(raw) -> dict[str, object]` in
`domain/iva/_catalogue.py:106` and `domain/categories/_registry.py:123`,
differing only in the raised error. Remediation: shared helper with
`error_factory`.

### F4 - `_ProfileId` triple-declaration (TRUE-DUPLICATE + weaker variant)

Canonical `ProfileId` in `core/identity/_profile.py`; an identical-constraint
duplicate in `domain/user_profile/_values.py:28`; and a weaker variant
(missing pattern + strip) in `application/user_profile/_aggregate.py:32`.
Remediation: delete the domain copy and import the canonical; promote the
aggregate field to `ProfileId` (its callers already pass conforming values).

### F5 - NIF control-letter table re-declared in test helpers (actionable)

`"TRWAGMYFPDXBNJZSQVHLCKE"` re-declared in `application/user_profile/_testing.py:24`
and `entrypoints/cli/test_profile_lifecycle_verbs.py:704` for NIF generation.
Remediation: expose a public `nif_check_letter(int) -> str` from
`core/identity/_tax_id.py`; both helpers call it.

### F6 - Browser viewport/timeout helpers byte-identical (TRUE-DUPLICATE, high)

`_get_default_viewport`, `_get_selector_probe_timeout_ms`, and a dead
`_get_timeout_defaults` are byte-for-byte identical across
`adapters/outbound/aeat/sede/_groi_check.py:75`, `_nif_iva_check.py:121`, and
`_renta_web_open.py:37`. Remediation: move the live helpers to the existing
`_browser_constants.py`; delete the dead one.

### F7 - LLM 429 status-dispatch duplicated (actionable)

The `if status == 429: raise_rate_limit(...)` dispatch is copy-pasted across
`adapters/outbound/llm/_providers/openai.py:126`, `gemini.py:131`, and
`local.py:93` (local also omits the 5xx band). Remediation: a
`check_http_error(response, provider_name)` helper in `_providers/base.py`.

### F8 - `FincaRepository` family not enrolled in `SqlRecordRepository[T]` (actionable)

`domain/fincas/_repository.py:47` and siblings (`:184`) reimplement the
`list_all/get/upsert/delete` scaffold that `SqlRecordRepository[T]`
(`adapters/persistence/storage/sql/repository.py:105`) already provides, with
no constraint-shape blocker. Remediation: enroll them in the base.

### F9 - Profile ledger repos vs `SecureBoundRepository` (deferred-structural)

`AssetsLedgerRepository`/`AmortizacionLedgerRepository`
(`adapters/persistence/profile/assets.py:94,184`) and
`InventoryLedgerRepository` (`profile/inventory.py:93`) duplicate the
`SecureBoundRepository` pattern but skip the `Envelope` wrapper, so migration
is a versioned data-format change, not a free consolidation. Track for a
dedicated slice. Also: `assets.py` hardcodes its namespace string instead of
reading `PROFILE_ASSETS_LEDGER_NAMESPACE` (inconsistent with `inventory.py`).

### F10 - Period-parsing local regex copies (partial-overlap)

`application/filing/reconciliation/_reconcile.py:383`,
`application/workflow/_engine.py:94` (carries a dead `YYYYMn` branch),
`application/filing/_import.py:37`, and
`application/invoices/_source_resolver.py:86` re-encode quarter/annual/month
period logic that `domain/period.py` owns. Return-shape/error-type differ.
Remediation: delegate to `parse_canonical_period` / `period_start_date`
/`period_end_date` and drop the local regexes; remove the dead branch.

### F11 - Private `core.time._now` cross-package imports (LIVE REGRESSION, high)

88 sites import the private `_now` from `aeat.core.time` across packages -
an architecture-rule violation (private cross-package import) the diagnostics
enforcement suite is meant to reject. Remediation: expose a public `now()` in
`core/time/__init__.py` and migrate callers. Not a duplication finding but a
canonical-enrollment defect surfaced by the sweep.

### Divergent / excluded (substitutability pre-filter held)

Correctly NOT actionable, with constraint-shape reasons: bare
`quantize(Decimal("0.01"))` without a rounding mode (HALF_EVEN, different
contract); the five Spanish-decimal parsers (different return/error/sign
contracts); ES-only 24-char IBAN vs any-country 15-34 (`registry/_schema.py`);
DEK-wrap and HKDF-context crypto (cryptographically distinct by design); the
`_PERIOD_RE` triplicate (documented intentional dialect split); `ddmmaaaa`
str-vs-bytes formatters; `PeriodKind` (3 members) vs registry `period_kind`
Literal (4-5 members). The 23 per-domain `*Error` bases rooting at `AeatError`
are sanctioned, not findings.

## Recommendations

Actionable cluster queue feeding the remediation Waves:

- W2 (duplication): F1 (seed), F2, F3, F6, F7 - consolidate to canonical homes
  (`core` money primitive, `core/_toml.read_toml`, shared `_to_str_dict`,
  `_browser_constants`, `_providers/base`) each with a behaviour test.
- W2/W3 (enrollment): F4, F5, F8 enrollment to existing canonicals; F11 the
  public-`now()` fix across 88 sites.
- W4: F10 period-parsing delegation; F9 as a dedicated data-format slice.
- BLOCKER before closing W01.P02: restore CUDA torch, restart the RAG service,
  and re-run the Axis-7 semantic sweep so vocabulary-divergent clusters this
  rg-only pass cannot see are surfaced and the inventory is proven complete.

## Codification candidates

None. The constraints these findings enforce (canonical placement, no
duplication, substitutability pre-filter, private-name import ban) are already
codified in the core-authority and swarm-audit-cadence rules; this audit
applies them rather than discovering a new durable rule.

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
(the directory the CLI's `vaultspec-core spec rules add` writes to today; the
planned `--scope project` flag will move authored rules under
`.vaultspec/rules/rules/project/`).

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
